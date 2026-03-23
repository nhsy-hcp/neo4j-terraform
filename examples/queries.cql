// 1. Find all resources for a specific provider
MATCH (p:TF_Provider {name: 'registry.terraform.io/hashicorp/aws'})-[:TF_HAS_RESOURCE]->(r:TF_Resource)
RETURN r.full_name LIMIT 10;

// 2. Count resources per provider
MATCH (p:TF_Provider)-[:TF_HAS_RESOURCE]->(r:TF_Resource)
RETURN p.name, count(r) AS resource_count
ORDER BY resource_count DESC;

// 3. Find all attributes of a specific resource
MATCH (r:TF_Resource {full_name: 'aws_s3_bucket'})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute)
RETURN a.name, a.type, a.required;

// 4. Find resources that have a 'tags' attribute
MATCH (r:TF_Resource)-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {name: 'tags'})
RETURN r.full_name, r.name LIMIT 20;

// 5. Find all required attributes for a resource
MATCH (r:TF_Resource {full_name: 'google_compute_instance'})-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute {required: true})
RETURN a.name, a.type;

// 6. Find resources that share an attribute name
MATCH (r1:TF_Resource)-[:TF_HAS_ATTRIBUTE]->(a:TF_Attribute)
MATCH (r2:TF_Resource)-[:TF_HAS_ATTRIBUTE]->(a2:TF_Attribute {name: a.name})
WHERE r1 <> r2 AND a.name = 'vpc_id'
RETURN r1.full_name, r2.full_name LIMIT 10;
