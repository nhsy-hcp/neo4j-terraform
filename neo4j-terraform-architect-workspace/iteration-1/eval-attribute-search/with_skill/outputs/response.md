# AWS Resources with "Logging" Related Attributes

Based on the Neo4j database (AWS provider version `6.37.0`), the following AWS resources have attributes related to "logging" in their name or description:

1. **aws_cloudfront_distribution**: `logging_v1_enabled`
2. **aws_cloudtrail**: `enable_logging`
3. **aws_db_proxy**: `debug_logging`
4. **aws_lambda_function**: `logging_config`
5. **aws_redshift_cluster**: `enable_logging`
6. **aws_chatbot_slack_channel_configuration**: `logging_level`
7. **aws_chatbot_teams_channel_configuration**: `logging_level`
8. **aws_transfer_connector**: `logging_role`
9. **aws_transfer_server**: `logging_role`
10. **aws_workspacesweb_portal**: `user_access_logging_settings_arn`
11. **aws_imagebuilder_infrastructure_configuration**: `logging`
12. **aws_ivschat_room**: `logging_configuration_identifiers`

### Cypher Query Used:
```cypher
MATCH (a:TF_Attribute)
WHERE toLower(a.name) CONTAINS "logging" OR toLower(a.description) CONTAINS "logging"
MATCH (owner)-[:TF_HAS_ATTRIBUTE]->(a)
WHERE (owner:TF_Resource OR owner:TF_DataSource)
AND owner.full_name STARTS WITH "aws_"
RETURN DISTINCT owner.full_name, a.name, a.description
LIMIT 20
```
