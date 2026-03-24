import json
from neo4j import GraphDatabase
import os
import argparse

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
# Namespace prefix for nodes and relationships
NAMESPACE = os.getenv("NEO4J_NAMESPACE", "TF_")


class Neo4jPopulator:
    def __init__(self, uri, user, password, namespace):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.ns = namespace

    def close(self):
        self.driver.close()

    def populate(self, schema_file, versions_file=None, provider_filter=None):
        with open(schema_file, "r") as f:
            data = json.load(f)

        versions = {}
        if versions_file and os.path.exists(versions_file):
            with open(versions_file, "r") as f:
                versions = json.load(f)

        with self.driver.session() as session:
            # Create constraints with namespace
            session.run(
                f"CREATE CONSTRAINT {self.ns}provider_name IF NOT EXISTS FOR (p:{self.ns}Provider) REQUIRE p.name IS UNIQUE"
            )
            session.run(
                f"CREATE CONSTRAINT {self.ns}resource_name IF NOT EXISTS FOR (r:{self.ns}Resource) REQUIRE r.full_name IS UNIQUE"
            )

            provider_schemas = data.get("provider_schemas", {})
            for provider_name, provider_data in provider_schemas.items():
                if provider_filter and provider_name != provider_filter:
                    continue

                print(f"Processing provider: {provider_name}")
                version = versions.get(provider_name, "unknown")
                self._process_provider(session, provider_name, provider_data, version)

    def _process_provider(self, session, provider_name, provider_data, version):
        # Create Provider node with version
        session.run(
            f"MERGE (p:{self.ns}Provider {{name: $name}}) SET p.version = $version",
            name=provider_name,
            version=version,
        )

        # Process Resources
        resources = provider_data.get("resource_schemas", {})
        for res_name, res_schema in resources.items():
            self._process_entity(session, provider_name, res_name, res_schema, "Resource")

        # Process Data Sources
        data_sources = provider_data.get("data_source_schemas", {})
        for ds_name, ds_schema in data_sources.items():
            self._process_entity(session, provider_name, ds_name, ds_schema, "DataSource")

    def _process_entity(self, session, provider_name, entity_name, entity_schema, label):
        # Create Resource/DataSource node and link to Provider
        session.run(
            f"""
            MATCH (p:{self.ns}Provider {{name: $provider_name}})
            MERGE (e:{self.ns}{label} {{full_name: $entity_name}})
            ON CREATE SET e.name = $name
            MERGE (p)-[:{self.ns}HAS_{label.upper()}]->(e)
            """,
            provider_name=provider_name,
            entity_name=entity_name,
            name=entity_name.split("_", 1)[-1] if "_" in entity_name else entity_name,
        )

        # Process Attributes (top-level)
        block = entity_schema.get("block", {})
        attributes = block.get("attributes", {})
        for attr_name, attr_data in attributes.items():
            session.run(
                f"""
                MATCH (e:{self.ns}{label} {{full_name: $entity_name}})
                MERGE (a:{self.ns}Attribute {{name: $attr_name, owner: $entity_name}})
                SET a.type = $attr_type, a.description = $description, a.required = $required
                MERGE (e)-[:{self.ns}HAS_ATTRIBUTE]->(a)
                """,
                entity_name=entity_name,
                attr_name=attr_name,
                attr_type=str(attr_data.get("type", "unknown")),
                description=attr_data.get("description", ""),
                required=attr_data.get("required", False),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate Neo4j with Terraform schema.")
    parser.add_argument("--schema", default=".cache/schema.json", help="Path to schema.json")
    parser.add_argument("--versions", default=".cache/versions.json", help="Path to versions.json")
    parser.add_argument(
        "--provider",
        help="Update only a specific provider (e.g., 'registry.terraform.io/hashicorp/aws')",
    )

    args = parser.parse_args()

    populator = Neo4jPopulator(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NAMESPACE)
    try:
        if os.path.exists(args.schema):
            populator.populate(args.schema, args.versions, args.provider)
        else:
            print(f"{args.schema} not found. Run fetch_schemas.py first.")
    finally:
        populator.close()
