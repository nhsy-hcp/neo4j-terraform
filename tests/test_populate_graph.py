import pytest
from unittest.mock import MagicMock, patch
from scripts.populate_graph import Neo4jPopulator
import json
import os

@pytest.fixture
def mock_neo4j():
    with patch("scripts.populate_graph.GraphDatabase.driver") as mock_driver:
        yield mock_driver

def test_populator_init(mock_neo4j):
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    mock_neo4j.assert_called_once_with("bolt://localhost:7687", auth=("user", "pass"))
    assert populator.ns == "TF_"
    populator.close()
    populator.driver.close.assert_called_once()

def test_populate_process_entity(mock_neo4j):
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    session = MagicMock()
    
    entity_schema = {
        "block": {
            "attributes": {
                "name": {
                    "type": "string",
                    "description": "The name",
                    "required": True
                }
            }
        }
    }
    
    populator._process_entity(session, "hashicorp/aws", "aws_instance", entity_schema, "Resource")
    
    # Check if session.run was called for the entity and the attribute
    assert session.run.call_count == 2
    
    # Verify entity creation call
    call_args_list = session.run.call_args_list
    entity_call = call_args_list[0]
    assert "MERGE (e:TF_Resource {full_name: $entity_name})" in entity_call[0][0]
    assert entity_call[1]["entity_name"] == "aws_instance"
    assert entity_call[1]["name"] == "instance"

    # Verify attribute creation call
    attr_call = call_args_list[1]
    assert "MERGE (a:TF_Attribute {name: $attr_name, owner: $entity_name})" in attr_call[0][0]
    assert attr_call[1]["attr_name"] == "name"
    assert attr_call[1]["attr_type"] == "string"
    assert attr_call[1]["required"] is True

def test_populate_full_flow(mock_neo4j, tmp_path):
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    schema_file = cache_dir / "schema.json"
    versions_file = cache_dir / "versions.json"
    
    schema_data = {
        "provider_schemas": {
            "hashicorp/aws": {
                "resource_schemas": {
                    "aws_s3_bucket": {
                        "block": {"attributes": {}}
                    }
                },
                "data_source_schemas": {}
            }
        }
    }
    versions_data = {"hashicorp/aws": "1.0.0"}
    
    schema_file.write_text(json.dumps(schema_data))
    versions_file.write_text(json.dumps(versions_data))
    
    populator = Neo4jPopulator("uri", "user", "pass", "TF_")
    session = MagicMock()
    populator.driver.session.return_value.__enter__.return_value = session
    
    populator.populate(str(schema_file), str(versions_file))
    
    # Check if constraints were created
    assert any("CREATE CONSTRAINT" in call[0][0] for call in session.run.call_args_list)
    # Check if provider was merged
    assert any("MERGE (p:TF_Provider" in call[0][0] for call in session.run.call_args_list)
    # Check if resource was merged
    assert any("MERGE (e:TF_Resource" in call[0][0] for call in session.run.call_args_list)
