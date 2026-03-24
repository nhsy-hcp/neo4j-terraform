"""
Neo4j Terraform Provider Schema Populator

Loads Terraform provider schemas into a Neo4j knowledge graph with:
- Batched UNWIND operations for performance (10-50x faster than per-node commits)
- Recursive nested block_types support (ingress/egress, lifecycle_rule, etc.)
- Full attribute metadata (optional, computed, sensitive, required)
- Proper indexing and constraints for query performance
- Cross-resource reference edge inference
- Provider prefix-aware short name derivation

Usage:
    python populate_neo4j.py --schema .cache/schema.json --versions .cache/versions.json
    python populate_neo4j.py --schema .cache/schema.json --provider registry.terraform.io/hashicorp/aws
    python populate_neo4j.py --schema .cache/schema.json --clear

Environment Variables:
    NEO4J_URI       - Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER      - Neo4j username (default: neo4j)
    NEO4J_PASSWORD  - Neo4j password (default: password)
    NEO4J_NAMESPACE - Node/relationship label prefix (default: TF_)
"""

import json
import os
import argparse
import time
import logging
from neo4j import GraphDatabase
from neo4j.exceptions import TransientError, ServiceUnavailable

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NAMESPACE = os.getenv("NEO4J_NAMESPACE", "TF_")

# Batch size for UNWIND operations
BATCH_SIZE = 500
MAX_RETRIES = 3


class Neo4jPopulator:
    def __init__(self, uri, user, password, namespace):
        """Initialize Neo4j populator with connection verification."""
        try:
            logger.info(f"Connecting to Neo4j at {uri}")
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j")
        except ServiceUnavailable as e:
            logger.error(f"Failed to connect to Neo4j at {uri}: {e}")
            raise ConnectionError(f"Neo4j service unavailable at {uri}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to Neo4j: {e}")
            raise ConnectionError(f"Failed to connect to Neo4j at {uri}: {e}")

        self.ns = namespace
        logger.debug(f"Using namespace prefix: {namespace}")

    def close(self):
        """Close Neo4j driver connection."""
        logger.info("Closing Neo4j connection")
        self.driver.close()

    def _execute_with_retry(self, session, query, params=None, max_retries=MAX_RETRIES):
        """Execute query with exponential backoff retry for transient errors."""
        params = params or {}
        for attempt in range(max_retries):
            try:
                return session.run(query, params)
            except TransientError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Query failed after {max_retries} retries: {e}")
                    raise
                wait_time = 2**attempt
                logger.warning(f"Transient error on attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Non-transient error executing query: {e}")
                raise

    # ------------------------------------------------------------------
    # Schema + index setup
    # ------------------------------------------------------------------
    def _create_constraints_and_indexes(self, session):
        """Create all constraints and indexes upfront for performance."""
        logger.info("Creating constraints and indexes")

        constraints = [
            (
                f"{self.ns}provider_name",
                f"(p:{self.ns}Provider)",
                "p.name IS UNIQUE",
            ),
            (
                f"{self.ns}resource_name",
                f"(r:{self.ns}Resource)",
                "r.full_name IS UNIQUE",
            ),
            (
                f"{self.ns}datasource_name",
                f"(d:{self.ns}DataSource)",
                "d.full_name IS UNIQUE",
            ),
            (
                f"{self.ns}nested_block_name",
                f"(nb:{self.ns}NestedBlock)",
                "nb.full_name IS UNIQUE",
            ),
            (
                f"{self.ns}attribute_id",
                f"(a:{self.ns}Attribute)",
                "a.uid IS UNIQUE",
            ),
        ]

        for cname, node_pattern, predicate in constraints:
            try:
                self._execute_with_retry(
                    session, f"CREATE CONSTRAINT {cname} IF NOT EXISTS FOR {node_pattern} REQUIRE {predicate}"
                )
                logger.debug(f"Created constraint: {cname}")
            except Exception as e:
                logger.warning(f"Failed to create constraint {cname}: {e}")

        # Additional indexes for common lookup patterns
        indexes = [
            (f"{self.ns}attr_owner", f"(a:{self.ns}Attribute)", "a.owner"),
            (f"{self.ns}attr_required", f"(a:{self.ns}Attribute)", "a.required"),
            (f"{self.ns}resource_provider", f"(r:{self.ns}Resource)", "r.provider"),
            (f"{self.ns}datasource_provider", f"(d:{self.ns}DataSource)", "d.provider"),
        ]

        for iname, node_pattern, prop in indexes:
            try:
                self._execute_with_retry(session, f"CREATE INDEX {iname} IF NOT EXISTS FOR {node_pattern} ON ({prop})")
                logger.debug(f"Created index: {iname}")
            except Exception as e:
                logger.warning(f"Failed to create index {iname}: {e}")

        logger.info("Constraints and indexes created successfully")

    # ------------------------------------------------------------------
    # Clear existing data for a provider (or all)
    # ------------------------------------------------------------------
    def clear(self, provider_name=None):
        """Delete all namespaced nodes, or just those belonging to one provider."""
        logger.info(f"Clearing data for provider: {provider_name or 'ALL'}")

        with self.driver.session() as session:
            if provider_name:
                # Delete attributes, nested blocks, resources/datasources, then provider
                self._execute_with_retry(
                    session,
                    f"""
                    MATCH (p:{self.ns}Provider {{name: $pname}})-[*]->(child)
                    DETACH DELETE child
                    """,
                    {"pname": provider_name},
                )
                self._execute_with_retry(
                    session, f"MATCH (p:{self.ns}Provider {{name: $pname}}) DETACH DELETE p", {"pname": provider_name}
                )
                logger.info(f"Cleared provider: {provider_name}")
            else:
                for label in [
                    "Attribute",
                    "NestedBlock",
                    "Resource",
                    "DataSource",
                    "Provider",
                ]:
                    self._execute_with_retry(session, f"MATCH (n:{self.ns}{label}) DETACH DELETE n")
                    logger.debug(f"Cleared all {label} nodes")
                logger.info("Cleared all namespaced nodes")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_schema_structure(self, data):
        """Validate schema file structure before processing."""
        logger.debug("Validating schema structure")

        if "provider_schemas" not in data:
            raise ValueError("Invalid schema file: missing 'provider_schemas' key")

        if not isinstance(data["provider_schemas"], dict):
            raise ValueError("Invalid schema file: 'provider_schemas' must be a dictionary")

        if not data["provider_schemas"]:
            logger.warning("Schema file contains no provider schemas")

        logger.debug("Schema structure validation passed")
        return True

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def populate(self, schema_file, versions_file=None, provider_filter=None):
        logger.info(f"Starting population from schema file: {schema_file}")

        with open(schema_file, "r") as f:
            data = json.load(f)

        self._validate_schema_structure(data)

        versions = {}
        if versions_file and os.path.exists(versions_file):
            logger.info(f"Loading versions from: {versions_file}")
            with open(versions_file, "r") as f:
                versions = json.load(f)
        else:
            logger.warning("No versions file provided or file not found")

        provider_schemas = data.get("provider_schemas", {})
        total_providers = len(provider_schemas)

        if provider_filter:
            logger.info(f"Filtering for provider: {provider_filter}")
            total_providers = 1 if provider_filter in provider_schemas else 0

        logger.info(f"Processing {total_providers} provider(s)")

        with self.driver.session() as session:
            self._create_constraints_and_indexes(session)

            processed = 0
            for provider_name, provider_data in provider_schemas.items():
                if provider_filter and provider_name != provider_filter:
                    continue

                processed += 1
                version = versions.get(provider_name, "unknown")
                t0 = time.time()
                logger.info(f"[{processed}/{total_providers}] Processing provider: {provider_name} (v{version})")

                try:
                    self._process_provider(session, provider_name, provider_data, version)
                    elapsed = time.time() - t0
                    logger.info(f"[{processed}/{total_providers}] Completed {provider_name} in {elapsed:.1f}s")
                except Exception as e:
                    logger.error(f"Failed to process provider {provider_name}: {e}", exc_info=True)
                    raise

            # Post-processing enrichment
            logger.info("Running post-processing enrichment")
            self._add_summary_metadata(session)
            self._infer_cross_resource_references(session)
            logger.info("Population complete")

    # ------------------------------------------------------------------
    # Provider
    # ------------------------------------------------------------------
    def _process_provider(self, session, provider_name, provider_data, version):
        prefix = provider_name.split("/")[-1]  # "hashicorp/aws" -> "aws"
        logger.debug(f"Provider prefix: {prefix}")

        self._execute_with_retry(
            session,
            f"""
            MERGE (p:{self.ns}Provider {{name: $name}})
            SET p.version = $version, p.prefix = $prefix
            """,
            {"name": provider_name, "version": version, "prefix": prefix},
        )

        resources = provider_data.get("resource_schemas", {})
        data_sources = provider_data.get("data_source_schemas", {})

        logger.debug(f"Found {len(resources)} resources and {len(data_sources)} data sources")

        self._process_entities_batch(session, provider_name, prefix, resources, "Resource")
        self._process_entities_batch(session, provider_name, prefix, data_sources, "DataSource")

    # ------------------------------------------------------------------
    # Batch entity (Resource / DataSource) creation
    # ------------------------------------------------------------------
    def _process_entities_batch(self, session, provider_name, prefix, entities, label):
        if not entities:
            logger.debug(f"No {label}s to process")
            return

        logger.info(f"Processing {len(entities)} {label}s for provider {provider_name}")

        # Build entity list
        entity_list = []
        for name, schema in entities.items():
            short_name = name[len(prefix) + 1 :] if name.startswith(prefix + "_") else name
            description = schema.get("block", {}).get("description", "")
            entity_list.append(
                {
                    "full_name": name,
                    "short_name": short_name,
                    "description": description,
                }
            )

        # Batch create entities and link to provider
        total_batches = (len(entity_list) + BATCH_SIZE - 1) // BATCH_SIZE
        for i, batch in enumerate(_chunked(entity_list, BATCH_SIZE), 1):
            logger.debug(f"Processing {label} batch {i}/{total_batches} ({len(batch)} items)")
            self._execute_with_retry(
                session,
                f"""
                MATCH (p:{self.ns}Provider {{name: $provider_name}})
                UNWIND $entities AS e
                MERGE (n:{self.ns}{label} {{full_name: e.full_name}})
                ON CREATE SET n.name = e.short_name,
                              n.description = e.description,
                              n.provider = $provider_name
                ON MATCH SET  n.description = e.description,
                              n.provider = $provider_name
                MERGE (p)-[:{self.ns}HAS_{label.upper()}]->(n)
                """,
                {"provider_name": provider_name, "entities": batch},
            )

        # Now process attributes and nested blocks for each entity
        logger.debug(f"Processing attributes and nested blocks for {len(entities)} {label}s")
        for name, schema in entities.items():
            block = schema.get("block", {})
            self._process_block(session, name, label, block)

        logger.info(f"Completed processing {len(entities)} {label}s")

    # ------------------------------------------------------------------
    # Recursive block processing (attributes + nested block_types)
    # ------------------------------------------------------------------
    def _process_block(self, session, parent_name, parent_label, block, depth=0):
        """Recursively process a schema block's attributes and nested block_types."""
        # -- Attributes at this level --
        attributes = block.get("attributes", {})
        if attributes:
            self._process_attributes_batch(session, parent_name, parent_label, attributes)

        # -- Nested block_types --
        block_types = block.get("block_types", {})
        if not block_types:
            return

        logger.debug(f"Processing {len(block_types)} nested blocks at depth {depth} for {parent_name}")

        nested_list = []
        for block_name, block_data in block_types.items():
            nested_full_name = f"{parent_name}.{block_name}"
            nesting_mode = block_data.get("nesting_mode", "single")
            min_items = block_data.get("min_items", 0)
            max_items = block_data.get("max_items", 0)
            nested_list.append(
                {
                    "full_name": nested_full_name,
                    "name": block_name,
                    "nesting_mode": nesting_mode,
                    "min_items": min_items,
                    "max_items": max_items,
                }
            )

        # Batch create nested blocks and link to parent
        for batch in _chunked(nested_list, BATCH_SIZE):
            self._execute_with_retry(
                session,
                f"""
                MATCH (parent:{self.ns}{parent_label} {{full_name: $parent_name}})
                UNWIND $blocks AS b
                MERGE (nb:{self.ns}NestedBlock {{full_name: b.full_name}})
                ON CREATE SET nb.name = b.name,
                              nb.nesting_mode = b.nesting_mode,
                              nb.min_items = b.min_items,
                              nb.max_items = b.max_items
                ON MATCH SET  nb.nesting_mode = b.nesting_mode,
                              nb.min_items = b.min_items,
                              nb.max_items = b.max_items
                MERGE (parent)-[:{self.ns}HAS_BLOCK]->(nb)
                """,
                {"parent_name": parent_name, "blocks": batch},
            )

        # Recurse into each nested block
        for block_name, block_data in block_types.items():
            nested_full_name = f"{parent_name}.{block_name}"
            inner_block = block_data.get("block", {})
            if inner_block:
                self._process_block(session, nested_full_name, "NestedBlock", inner_block, depth + 1)

    # ------------------------------------------------------------------
    # Batch attribute creation
    # ------------------------------------------------------------------
    def _process_attributes_batch(self, session, owner_name, owner_label, attributes):
        """Batch-create attribute nodes with full metadata."""
        logger.debug(f"Processing {len(attributes)} attributes for {owner_name}")

        attr_list = []
        for attr_name, attr_data in attributes.items():
            attr_type_raw = attr_data.get("type", "unknown")
            attr_type = json.dumps(attr_type_raw) if isinstance(attr_type_raw, list) else str(attr_type_raw)

            attr_list.append(
                {
                    "uid": f"{owner_name}::{attr_name}",
                    "name": attr_name,
                    "type": attr_type,
                    "description": attr_data.get("description", ""),
                    "required": attr_data.get("required", False),
                    "optional": attr_data.get("optional", False),
                    "computed": attr_data.get("computed", False),
                    "sensitive": attr_data.get("sensitive", False),
                    "deprecated": attr_data.get("deprecated", False),
                }
            )

        for batch in _chunked(attr_list, BATCH_SIZE):
            self._execute_with_retry(
                session,
                f"""
                MATCH (owner:{self.ns}{owner_label} {{full_name: $owner_name}})
                UNWIND $attrs AS a
                MERGE (attr:{self.ns}Attribute {{uid: a.uid}})
                SET attr.name       = a.name,
                    attr.owner      = $owner_name,
                    attr.type       = a.type,
                    attr.description = a.description,
                    attr.required   = a.required,
                    attr.optional   = a.optional,
                    attr.computed   = a.computed,
                    attr.sensitive  = a.sensitive,
                    attr.deprecated = a.deprecated
                MERGE (owner)-[:{self.ns}HAS_ATTRIBUTE]->(attr)
                """,
                {"owner_name": owner_name, "attrs": batch},
            )

    # ------------------------------------------------------------------
    # Post-processing: summary metadata
    # ------------------------------------------------------------------
    def _add_summary_metadata(self, session):
        """Add computed counts to Resource/DataSource nodes for fast retrieval."""
        logger.info("Adding summary metadata")

        for label in ["Resource", "DataSource"]:
            # Total attribute count
            logger.debug(f"Computing attribute counts for {label}s")
            self._execute_with_retry(
                session,
                f"""
                MATCH (e:{self.ns}{label})-[:{self.ns}HAS_ATTRIBUTE]->(a:{self.ns}Attribute)
                WITH e, count(a) AS total,
                     count(CASE WHEN a.required THEN 1 END) AS req,
                     count(CASE WHEN a.optional THEN 1 END) AS opt,
                     count(CASE WHEN a.computed THEN 1 END) AS comp
                SET e.attribute_count = total,
                    e.required_count  = req,
                    e.optional_count  = opt,
                    e.computed_count  = comp
                """,
            )

            # Nested block count
            logger.debug(f"Computing nested block counts for {label}s")
            self._execute_with_retry(
                session,
                f"""
                MATCH (e:{self.ns}{label})-[:{self.ns}HAS_BLOCK]->(nb:{self.ns}NestedBlock)
                WITH e, count(nb) AS block_count
                SET e.nested_block_count = block_count
                """,
            )

        logger.info("Summary metadata added successfully")

    # ------------------------------------------------------------------
    # Post-processing: infer cross-resource references
    # ------------------------------------------------------------------
    def _infer_cross_resource_references(self, session):
        """
        Infer REFERENCES edges between resources based on attribute naming
        conventions. For example, aws_instance has `subnet_id` which likely
        references aws_subnet. This gives the graph the dependency edges
        that make it useful for LLM-driven IaC generation.
        """
        logger.info("Inferring cross-resource references")

        result = self._execute_with_retry(
            session,
            f"""
            MATCH (a:{self.ns}Attribute)<-[:{self.ns}HAS_ATTRIBUTE]-(src:{self.ns}Resource)
            WHERE a.name ENDS WITH '_id' OR a.name ENDS WITH '_ids'
                  OR a.name ENDS WITH '_arn' OR a.name ENDS WITH '_arns'
                  OR a.name ENDS WITH '_name' AND a.name <> 'name'
            WITH src, a,
                 CASE
                   WHEN a.name ENDS WITH '_ids' THEN substring(a.name, 0, size(a.name) - 4)
                   WHEN a.name ENDS WITH '_arns' THEN substring(a.name, 0, size(a.name) - 5)
                   WHEN a.name ENDS WITH '_id' THEN substring(a.name, 0, size(a.name) - 3)
                   WHEN a.name ENDS WITH '_arn' THEN substring(a.name, 0, size(a.name) - 4)
                   WHEN a.name ENDS WITH '_name' THEN substring(a.name, 0, size(a.name) - 5)
                 END AS ref_suffix
            WITH src, a, ref_suffix, src.provider AS prov
            MATCH (target:{self.ns}Resource {{provider: prov}})
            WHERE target.full_name ENDS WITH ref_suffix
                  AND target <> src
            MERGE (src)-[r:{self.ns}REFERENCES {{via: a.name}}]->(target)
            RETURN count(r) AS edges_created
            """,
        )
        record = result.single()
        count = record["edges_created"] if record else 0
        logger.info(f"Inferred {count} cross-resource reference edges")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _chunked(iterable, size):
    """Yield successive chunks of `size` from a list."""
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Populate Neo4j with Terraform provider schemas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--schema",
        default=".cache/schema.json",
        help="Path to schema.json (default: .cache/schema.json)",
    )
    parser.add_argument(
        "--versions",
        default=".cache/versions.json",
        help="Path to versions.json (default: .cache/versions.json)",
    )
    parser.add_argument(
        "--provider",
        help="Process only a specific provider (e.g. 'registry.terraform.io/hashicorp/aws')",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before populating (scoped to --provider if set)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    # Adjust logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    populator = Neo4jPopulator(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NAMESPACE)
    try:
        if args.clear:
            populator.clear(args.provider)

        if not os.path.exists(args.schema):
            logger.error(f"Schema file not found: {args.schema}")
            print(f"Schema file not found: {args.schema}")
            print("Run your schema fetch script first (e.g. fetch_schemas.py).")
            return

        populator.populate(args.schema, args.versions, args.provider)

    except Exception as e:
        logger.error(f"Population failed: {e}", exc_info=True)
        raise
    finally:
        populator.close()


if __name__ == "__main__":
    main()
