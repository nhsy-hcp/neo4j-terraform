# Neo4j Terraform Provider Schema Database

This project builds a Neo4j graph database populated with the latest Terraform provider schemas (AWS, GCP, Azure, etc.). It enables complex querying of provider capabilities, resource relationships, and attribute details across the entire Terraform ecosystem.

## Project Structure

- `scripts/`: Python scripts for fetching schemas and populating the database.
  - `fetch_schemas.py`: Uses `terraform` to download provider schemas into `.cache/schema.json`.
  - `populate_graph.py`: Parses `.cache/schema.json` and loads it into Neo4j.
  - `run_query.py`: Helper to execute Cypher queries from the CLI.
- `examples/`: Sample Cypher queries for common analysis tasks.
- `Taskfile.yml`: Automation for common tasks.

## Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- [uv](https://github.com/astral-sh/uv) (for Python package management)
- [Terraform](https://www.terraform.io/) (installed locally to fetch schemas)

## Getting Started

1. **Start Neo4j**:
   ```bash
   task up
   ```
   Access Neo4j Browser at [http://localhost:7474](http://localhost:7474) (User: `neo4j`, Password: `password`).

2. **Setup and Populate**:
   ```bash
   task setup
   ```

3. **Run Examples**:
   ```bash
   task examples
   ```

## Neo4j MCP Server

This project is compatible with the [Neo4j MCP (Model Context Protocol) server](https://github.com/neo4j/mcp), which allows LLMs and other tools to interact with the Terraform schema graph.

### Prerequisites

- Running Neo4j instance (the provided `docker-compose.yml` already includes the required APOC plugin).
- **Optional:** Node.js and npm (to run via `npx`).

### Installation & Usage

You can run the MCP server via `npx` (no install required). It is recommended to run in **read-only mode** to prevent accidental modifications to the graph.

#### Run via npx
```bash
npx @neo4j/mcp --uri bolt://localhost:7687 --username neo4j --password password --neo4j-read-only true
```

### MCP Client Configuration (e.g., Claude Desktop)
Add the following to your configuration file:

```json
{
  "mcpServers": {
    "neo4j": {
      "command": "npx",
      "args": [
        "-y",
        "@neo4j/mcp",
        "--uri", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password",
        "--neo4j-read-only", "true"
      ]
    }
  }
}
```

> **Note:** This project uses a `TF_` prefix for all Neo4j labels and relationship types by default (e.g., `TF_Provider`). The MCP server will automatically discover these, but ensure your queries reflect this namespacing.

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
   # Loads .cache/schema.json and .cache/versions.json into Neo4j
   task populate
   ```

## Configuration

The population script supports several environment variables:

- `NEO4J_URI`: Default `bolt://localhost:7687`
- `NEO4J_USER`: Default `neo4j`
- `NEO4J_PASSWORD`: Default `password`
- `NEO4J_NAMESPACE`: Default `TF_` (prefix for all labels and relationship types)

## Taskfile Automation

- `task up`: Start Neo4j containers.
- `task logs`: Stream logs from docker-compose.
- `task setup`: Fetch provider schemas and populate the graph.
- `task fetch`: Fetch provider schemas and versions.
- `task populate`: Load `.cache/schema.json` and `.cache/versions.json` into Neo4j.
- `task examples`: Run example Cypher queries from `examples/queries.cql`.
- `task test`: Run the test suite.
- `task lint`: Run linting and formatting checks.
- `task format`: Format code with Ruff.
- `task clean`: Wipe local Neo4j data and .cache (requires confirmation).
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
