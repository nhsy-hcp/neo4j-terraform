# Neo4j Terraform Provider Schema Database

This project builds a Neo4j graph database populated with the latest Terraform provider schemas (AWS, GCP, Azure, etc.).

## Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- [uv](https://github.com/astral-sh/uv) (for Python package management)
- [Terraform](https://www.terraform.io/) (installed locally to fetch schemas)

## Getting Started

1. **Start Neo4j**:
   ```bash
   docker-compose up -d
   ```
   Access Neo4j Browser at [http://localhost:7474](http://localhost:7474) (User: `neo4j`, Password: `password`).

2. **Setup Python Environment**:
   ```bash
   uv sync
   ```

3. **Fetch Provider Schemas**:
   ```bash
   uv run scripts/fetch_schemas.py
   ```
   This script will create a temporary Terraform configuration, initialize it, and export the provider schemas to `schema.json`.

4. **Populate the Graph Database**:
   ```bash
   uv run scripts/populate_graph.py
   ```
   This script will read `schema.json` and use the Neo4j driver to populate the database with `Provider`, `Resource`, `DataSource`, and `Attribute` nodes.

## Example Queries

Check [examples/queries.cql](examples/queries.cql) for useful Cypher queries.

### Basic Resource Count per Provider:
```cypher
MATCH (p:Provider)-[:HAS_RESOURCE]->(r:Resource)
RETURN p.name, count(r) AS resource_count
ORDER BY resource_count DESC;
```

### Find all Resources with a `tags` attribute:
```cypher
MATCH (r:Resource)-[:HAS_ATTRIBUTE]->(a:Attribute {name: 'tags'})
RETURN r.full_name LIMIT 10;
```
