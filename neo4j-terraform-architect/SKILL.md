---
name: neo4j-terraform-architect
description: Use the Neo4j knowledge graph as the source of truth for Terraform resource schemas, data source configurations, and attribute details. Trigger this skill whenever the user asks for resource attributes, needs to generate Terraform HCL, or wants to explore the relationship between cloud providers and their components. Use this skill even if the user just asks "how do I use [resource]" or "what are the required fields for [resource]," and prioritize the information in the Neo4j database over general knowledge.
---

# Neo4j Terraform Architect

A skill for bridging the gap between stored Terraform provider metadata in Neo4j and Infrastructure as Code (IaC) development.

## Core Mandate
ALWAYS use the `mcp-neo4j-cypher` tool to query the local knowledge graph for exact schemas before generating Terraform code or answering questions about resource attributes.

### Knowledge Graph Schema
The database uses these labels:
- `TF_Provider`: `name` (e.g., "registry.terraform.io/hashicorp/aws"), `version`
- `TF_Resource`: `name`, `full_name`
- `TF_DataSource`: `name`, `full_name`
- `TF_Attribute`: `name`, `owner`, `description`, `type`, `required` (boolean)

Relationships:
- `(:TF_Provider)-[:TF_HAS_RESOURCE]->(:TF_Resource)`
- `(:TF_Provider)-[:TF_HAS_DATASOURCE]->(:TF_DataSource)`
- `(:TF_Resource)-[:TF_HAS_ATTRIBUTE]->(:TF_Attribute)`
- `(:TF_DataSource)-[:TF_HAS_ATTRIBUTE]->(:TF_Attribute)`

## Workflows

### 1. Schema Discovery
When a user asks "What can I do with [resource]?" or "What are the attributes for [resource]?", use a Cypher query like this:
```cypher
MATCH (r:TF_Resource {full_name: "aws_s3_bucket"})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute)
RETURN a.name, a.type, a.required, a.description
ORDER BY a.required DESC, a.name ASC
```

### 2. Required Attributes Only
If the user asks for a minimal configuration, filter for `required: true`:
```cypher
MATCH (r:TF_Resource {full_name: "azurerm_linux_virtual_machine"})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {required: true})
RETURN a.name, a.type, a.description
```

### 3. Cross-Provider Attribute Search
If the user is looking for a feature across providers (e.g., "logging"):
```cypher
MATCH (a:TF_Attribute)
WHERE a.name CONTAINS "logging" OR a.description CONTAINS "logging"
MATCH (owner)-[:TF_HAS_ATTRIBUTE]->(a)
RETURN DISTINCT owner.full_name, a.name, a.description
```

### 4. HCL Generation
When generating code, use the exact attribute names and types found in the database. If an attribute type is complex (e.g., nested blocks), and the database doesn't have the sub-attributes, proactively check if there's a related `TF_Attribute` where the `owner` matches the complex type's name.

## Output Standards
- **Precise Attributes**: Never guess attribute names; use what's in the graph.
- **Provider Context**: Mention the provider version found in the graph (from `TF_Provider` node).
- **HCL Blocks**: Ensure the generated HCL is valid and includes comments derived from the attribute descriptions in the database.
