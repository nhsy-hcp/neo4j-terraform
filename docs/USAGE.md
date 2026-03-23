# Agent Instructions: Connecting to the Terraform Knowledge Graph

This repository provides a Neo4j knowledge graph of Terraform provider schemas. Use these details to connect from external projects or agents:

## Connection Parameters
- **Bolt URI**: `bolt://localhost:7687` (Primary connection for Cypher queries)
- **HTTP URI**: `http://localhost:7474` (Neo4j Browser/Management access)
- **User**: `neo4j`
- **Password**: `password`

## Knowledge Graph Context (Namespaced)
All nodes and relationships are prefixed with `TF_` to prevent collisions in shared environments.

- **Nodes**: `TF_Provider`, `TF_Resource`, `TF_DataSource`, `TF_Attribute`.
- **Relationships**: `TF_HAS_RESOURCE`, `TF_HAS_DATASOURCE`, `TF_HAS_ATTRIBUTE`.
- **Primary Use**: Querying these nodes allows the agent to retrieve exact, up-to-date Terraform schema definitions for AWS, GCP, Azure, and other providers.

## Neo4j MCP Server
This project is compatible with the [Neo4j MCP server](https://github.com/neo4j/mcp). Refer to the `README.md` for installation and configuration details (e.g., running via `npx` in read-only mode).

## Connection Best Practices
- **Protocols**: Prefer the **Bolt** protocol for all programmatic queries as it is more efficient.
- **Verification**: Ensure the database service in the `neo4j-terraform` repository is running before attempting to connect.
- **Token Optimization**: When running queries that return large datasets, pipe the output to the `.tmp/` folder (e.g., `uv run scripts/run_query.py queries.cql > .tmp/results.txt`) to avoid flooding the context window.
- **Hallucination Prevention**: Use the graph to verify resource attributes (e.g., `required`, `type`, `description`) before generating Terraform HCL code.
