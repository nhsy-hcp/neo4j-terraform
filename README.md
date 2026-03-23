# Neo4j Terraform Provider Schema Database

This project builds a Neo4j graph database populated with the latest Terraform provider schemas (AWS, GCP, Azure, etc.). It enables complex querying of provider capabilities, resource relationships, and attribute details across the entire Terraform ecosystem.

## Project Structure

- `scripts/`: Python scripts for fetching schemas and populating the database.
  - `fetch_schemas.py`: Uses `terraform` to download provider schemas into `schema.json`.
  - `populate_graph.py`: Parses `schema.json` and loads it into Neo4j.
  - `run_query.py`: Helper to execute Cypher queries from the CLI.
- `examples/`: Sample Cypher queries for common analysis tasks.
- `conductor/`: Project management and refactor plans.
- `Taskfile.yml`: Automation for common tasks.

## Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- [uv](https://github.com/astral-sh/uv) (for Python package management)
- [Terraform](https://www.terraform.io/) (installed locally to fetch schemas)

## Getting Started

The easiest way to get started is to use the `task up` command, which handles environment setup and database population.

1. **Setup and Populate**:
   ```bash
   task up
   ```
   Access Neo4j Browser at [http://localhost:7474](http://localhost:7474) (User: `neo4j`, Password: `password`).

2. **Run Examples**:
   ```bash
   task examples
   ```

### Manual Steps

If you prefer running steps manually:

1. **Start Neo4j**:
   ```bash
   docker-compose up -d
   ```

2. **Setup Python Environment**:
   ```bash
   uv sync
   ```

3. **Fetch Provider Schemas**:
   ```bash
   # Downloads schemas for a predefined list of providers
   task fetch
   ```

4. **Populate the Graph Database**:
   ```bash
   # Loads schema.json and versions.json into Neo4j
   task populate
   ```

## Configuration

The population script supports several environment variables:

- `NEO4J_URI`: Default `bolt://localhost:7687`
- `NEO4J_USER`: Default `neo4j`
- `NEO4J_PASSWORD`: Default `password`
- `NEO4J_NAMESPACE`: Default `TF_` (prefix for all labels and relationship types)

## Taskfile Automation

- `task up`: Start Neo4j, fetch schemas, and populate the graph.
- `task fetch`: Fetch provider schemas and versions.
- `task populate`: Load `schema.json` and `versions.json` into Neo4j.
- `task examples`: Run example Cypher queries from `examples/queries.cql`.
- `task test`: Run the test suite.
- `task lint`: Run linting and formatting checks.
- `task format`: Format code with Ruff.
- `task clean:data`: Wipe local Neo4j data (requires confirmation).
- `task down`: Stop Neo4j containers.

## Example Queries

Check [examples/queries.cql](examples/queries.cql) for useful Cypher queries.

### Basic Resource Count per Provider:
```cypher
MATCH (p:TF_Provider)-[:TF_HAS_RESOURCE]->(r:TF_Resource)
RETURN p.name, count(r) AS resource_count
ORDER BY resource_count DESC;
```

### Find all Resources with a `tags` attribute:
```cypher
MATCH (r:TF_Resource)-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {name: 'tags'})
RETURN r.full_name LIMIT 10;
```

### List Required Attributes for a specific Resource:
```cypher
MATCH (r:TF_Resource {full_name: 'aws_instance'})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {required: true})
RETURN a.name, a.type, a.description;
```
