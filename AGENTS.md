# Agent Instructions

This document provides foundational mandates and expert procedural guidance for AI agents working in this project.

## Project Vision

This project creates a graph representation of the Terraform provider ecosystem in Neo4j. It's intended to be used as a knowledge base for LLMs and developers for:
- Resource schema discovery.
- Cross-provider attribute analysis.
- Terraform HCL generation and validation.

## Architectural Standards

- **Namespacing:** All Neo4j labels and relationship types must be prefixed. The default is `TF_` (e.g., `TF_Provider`, `TF_HAS_ATTRIBUTE`).
- **Data Ingestion:** Always follow the `fetch` -> `populate` cycle. Never manually inject data without updating the corresponding scripts.
- **Python Tooling:** Use `uv` for all dependency management. Scripts should be run via `uv run`.
- **Automation:** Prefer `task` (Taskfile.yml) for all high-level operations.

## Connection Details

When connecting to the Neo4j knowledge graph from external projects or agents:

- **Bolt URI**: `bolt://localhost:7687` (Primary connection for Cypher queries)
- **HTTP URI**: `http://localhost:7474` (Neo4j Browser/Management access)
- **User**: `neo4j`
- **Password**: `password`

### Knowledge Graph Schema (Namespaced)
All nodes and relationships are prefixed with `TF_` to prevent collisions:

- **Nodes**: `TF_Provider`, `TF_Resource`, `TF_DataSource`, `TF_Attribute`
- **Relationships**: `TF_HAS_RESOURCE`, `TF_HAS_DATASOURCE`, `TF_HAS_ATTRIBUTE`

### Connection Best Practices
- **Protocols**: Prefer the **Bolt** protocol for all programmatic queries as it is more efficient.
- **Verification**: Ensure the database service is running (`task up`) before attempting to connect.
- **Token Optimization**: When running queries that return large datasets, pipe the output to the `.tmp/` folder to avoid flooding the context window.
- **Hallucination Prevention**: Use the graph to verify resource attributes (e.g., `required`, `type`, `description`) before generating Terraform HCL code.

For detailed connection information, see [docs/USAGE.md](docs/USAGE.md).

## Common Operations

### Complete Setup
To fetch schemas and populate the graph in one step:
1. Ensure Neo4j is running (`task up`).
2. Run `task setup`.

### Fetching New Schemas
1. Modify `scripts/providers.json` to add new provider configurations.
2. Run `task fetch`.

### Populating the Database
1. Ensure `.cache/schema.json` and `.cache/versions.json` are present.
2. Run `task populate`.

### Running Queries
- Use `scripts/run_query.py` to execute Cypher queries.
- Prefer adding new queries to `examples/queries.cql` first.

### Token Optimization
To manage the context window efficiently, avoid large, redundant outputs:
1. **Piping Outputs:** Pipe large Neo4j tool or script outputs to the `.tmp/` folder (e.g., `uv run scripts/run_query.py <query> > .tmp/query_results.json`).
2. **Selective Reading:** Once piped, use `read_file` with `offset` and `limit` to inspect only the required parts of the results.
3. **Searching Large JSON:** When inspecting `.cache/schema.json` (which can be very large), use `jq` to extract specific paths or keys instead of reading or `grep`ing the whole file. (e.g., `jq '.provider_schemas["registry.terraform.io/hashicorp/aws"].resource_schemas.aws_s3_bucket' .cache/schema.json`).

## Expert Skills

This project includes specialized AI agent skills for advanced operations:

- **neo4j-terraform-architect:** Specialized skill for exploring the schema and generating HCL. Use this whenever the user needs deep schema knowledge, cross-provider analysis, or Terraform code generation.
  - Location: `.agents/skills/skill-creator/neo4j-terraform-architect.skill`
  - Capabilities: Schema exploration, attribute discovery, HCL generation, validation
  - Evaluation: The skill includes a comprehensive evaluation framework in `neo4j-terraform-architect-workspace/`

### Using Skills
Skills are automatically loaded by compatible AI agents (e.g., Claude Desktop with MCP). To manually invoke a skill:
1. Ensure the skill is properly packaged (see `.agents/skills/skill-creator/scripts/package_skill.py`).
2. Reference the skill in your agent configuration.
3. The skill will provide specialized context and capabilities for Terraform schema operations.

## Maintenance

### Tests
All core parsing and population logic must be tested with `pytest`. Maintain a minimum of **80% code coverage** for all scripts.

Run tests:
```bash
task test
```

### Linting and Formatting
Maintain high code quality with `ruff`. The project uses a line length of 120 characters (configured in `.ruff.toml`).

```bash
task lint    # Run all checks
task format  # Auto-format code
```

All code must be formatted with `ruff format` before committing.

### E2E Testing
To verify the complete fetch workflow with a real provider:
1. Create a test config: `echo '{"random": null}' > .tmp/test_provider.json`
2. Run fetch: `uv run python scripts/fetch_schemas.py .tmp/test_provider.json`
3. Verify outputs exist: `.cache/schema.json` and `.cache/versions.json`
4. Check logs for successful terraform init and schema export

This validates:
- Terraform integration works correctly
- Provider resolution and version fetching
- JSON schema export and validation
- File I/O operations

## Development Workflow

1. **Discovery:** Thoroughly explore the codebase and relevant documentation (`docs/`, `README.md`, `AGENTS.md`) before making changes.
2. **Planning:** For complex tasks, save a concise plan to the `.plans/` folder.
3. **Implementation:** Make changes in small, logical steps. Run local tests frequently.
4. **Verification:** Run `task lint` and `task test` before proposing changes.
5. **Documentation:** Update relevant documentation (README.md, docs/USAGE.md) when changing functionality.

## Additional Resources

- **README.md**: User-facing documentation and quick start guide
- **docs/USAGE.md**: Detailed connection information for external agents
- **examples/queries.cql**: Sample Cypher queries for common analysis tasks
- **Taskfile.yml**: Complete list of available automation tasks