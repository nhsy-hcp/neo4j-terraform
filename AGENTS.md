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

## Common Operations

### Fetching New Schemas
1. Modify `scripts/fetch_schemas.py` if a new provider is needed.
2. Run `task fetch`.

### Populating the Database
1. Ensure `schema.json` and `versions.json` are present.
2. Run `task populate`.

### Running Queries
- Use `scripts/run_query.py` to execute Cypher queries.
- Prefer adding new queries to `examples/queries.cql` first.

## Expert Skills

- **neo4j-terraform-architect:** Specialized skill for exploring the schema and generating HCL. Use this whenever the user needs deep schema knowledge.

## Maintenance

- **Tests:** All core parsing and population logic must be tested with `pytest`.
- **Linting:** Maintain high code quality with `ruff`. Use `task lint` and `task format` before committing.
