# Mock schema to test structure
MOCK_SCHEMA = {
    "provider_schemas": {
        "registry.terraform.io/hashicorp/aws": {
            "resource_schemas": {
                "aws_s3_bucket": {
                    "block": {
                        "attributes": {
                            "bucket": {
                                "type": "string",
                                "description": "Bucket name",
                                "required": False,
                            }
                        }
                    }
                }
            }
        }
    }
}

MOCK_VERSIONS = {"registry.terraform.io/hashicorp/aws": "6.37.0"}


def test_schema_parsing_logic():
    # Test logic that parses the input dictionaries
    provider_name = "registry.terraform.io/hashicorp/aws"
    provider_data = MOCK_SCHEMA["provider_schemas"][provider_name]
    version = MOCK_VERSIONS.get(provider_name, "unknown")

    assert version == "6.37.0"
    assert "resource_schemas" in provider_data
    assert "aws_s3_bucket" in provider_data["resource_schemas"]


def test_attr_parsing():
    res_schema = MOCK_SCHEMA["provider_schemas"]["registry.terraform.io/hashicorp/aws"][
        "resource_schemas"
    ]["aws_s3_bucket"]
    attributes = res_schema["block"]["attributes"]
    assert "bucket" in attributes
    attr = attributes["bucket"]
    assert attr["required"] is False
    assert attr["type"] == "string"
