# Required Attributes for `aws_s3_bucket`

Based on the Neo4j database (AWS provider version `6.37.0`), the only required attribute for the `aws_s3_bucket` resource is:

- **bucket** (type: `string`): The name of the bucket.

### Cypher Query Used:
```cypher
MATCH (r:TF_Resource {full_name: "aws_s3_bucket"})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {required: true})
RETURN a.name, a.type, a.required, a.description
ORDER BY a.name ASC
```
