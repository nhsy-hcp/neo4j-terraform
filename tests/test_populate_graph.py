import pytest
from unittest.mock import MagicMock, patch
from scripts.populate_graph import Neo4jPopulator
import json


@pytest.fixture
def mock_neo4j():
    with patch("scripts.populate_graph.GraphDatabase.driver") as mock_driver:
        mock_instance = MagicMock()
        mock_instance.verify_connectivity = MagicMock()
        mock_driver.return_value = mock_instance
        yield mock_driver


def test_populator_init(mock_neo4j):
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    mock_neo4j.assert_called_once_with("bolt://localhost:7687", auth=("user", "pass"))
    assert populator.ns == "TF_"
    populator.close()
    populator.driver.close.assert_called_once()


def test_populator_init_connection_failure(mock_neo4j):
    """Test that connection failures are properly handled."""
    from neo4j.exceptions import ServiceUnavailable

    mock_neo4j.return_value.verify_connectivity.side_effect = ServiceUnavailable("Connection failed")

    with pytest.raises(ConnectionError, match="Neo4j service unavailable"):
        Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")


def test_validate_schema_structure(mock_neo4j):
    """Test schema validation."""
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")

    # Valid schema
    valid_schema = {"provider_schemas": {"aws": {}}}
    assert populator._validate_schema_structure(valid_schema) is True

    # Missing provider_schemas key
    with pytest.raises(ValueError, match="missing 'provider_schemas' key"):
        populator._validate_schema_structure({})

    # Invalid type for provider_schemas
    with pytest.raises(ValueError, match="must be a dictionary"):
        populator._validate_schema_structure({"provider_schemas": []})

    populator.close()


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
                        "block": {
                            "attributes": {"bucket": {"type": "string", "description": "Bucket name", "required": True}}
                        }
                    }
                },
                "data_source_schemas": {},
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
    assert any("CREATE CONSTRAINT" in str(call) for call in session.run.call_args_list)
    # Check if provider was merged
    assert any("MERGE (p:TF_Provider" in str(call) for call in session.run.call_args_list)
    # Check if resource was processed (using UNWIND batch operation)
    assert any("UNWIND $entities" in str(call) for call in session.run.call_args_list)

    populator.close()


def test_clear_all_data(mock_neo4j):
    """Test clearing all data."""
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    session = MagicMock()
    populator.driver.session.return_value.__enter__.return_value = session

    populator.clear()

    # Should delete all label types
    assert session.run.call_count >= 5  # One for each label type
    populator.close()


def test_clear_specific_provider(mock_neo4j):
    """Test clearing data for a specific provider."""
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    session = MagicMock()
    populator.driver.session.return_value.__enter__.return_value = session

    populator.clear("hashicorp/aws")

    # Should call run twice (delete children, then provider)
    assert session.run.call_count == 2
    populator.close()


def test_execute_with_retry_success(mock_neo4j):
    """Test successful query execution."""
    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    session = MagicMock()

    populator._execute_with_retry(session, "MATCH (n) RETURN n", {})

    assert session.run.call_count == 1
    populator.close()


def test_execute_with_retry_transient_error(mock_neo4j):
    """Test retry logic for transient errors."""
    from neo4j.exceptions import TransientError

    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    session = MagicMock()

    # Fail twice, then succeed
    session.run.side_effect = [TransientError("Transient error 1"), TransientError("Transient error 2"), MagicMock()]

    populator._execute_with_retry(session, "MATCH (n) RETURN n", {}, max_retries=3)

    assert session.run.call_count == 3
    populator.close()


def test_execute_with_retry_max_retries_exceeded(mock_neo4j):
    """Test that max retries are respected."""
    from neo4j.exceptions import TransientError

    populator = Neo4jPopulator("bolt://localhost:7687", "user", "pass", "TF_")
    session = MagicMock()

    session.run.side_effect = TransientError("Persistent error")

    with pytest.raises(TransientError):
        populator._execute_with_retry(session, "MATCH (n) RETURN n", {}, max_retries=3)

    assert session.run.call_count == 3
    populator.close()
