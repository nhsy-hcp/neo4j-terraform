from scripts.fetch_schemas import generate_tf_config, fetch_schemas
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

def test_generate_tf_config():
    providers = ["aws", "google", "null"]
    config = generate_tf_config(providers)

    assert "terraform {" in config
    assert "required_providers {" in config
    assert 'aws = { source = "hashicorp/aws" }' in config
    assert 'google = { source = "hashicorp/google" }' in config
    assert 'null = { source = "hashicorp/null" }' in config


def test_generate_tf_config_empty():
    config = generate_tf_config([])
    assert "terraform {" in config
    assert "required_providers {" in config

@patch("scripts.fetch_schemas.subprocess.run")
@patch("scripts.fetch_schemas.Path.mkdir")
@patch("scripts.fetch_schemas.Path.write_text")
@patch("scripts.fetch_schemas.Path.exists", return_value=True)
def test_fetch_schemas(mock_exists, mock_write, mock_mkdir, mock_run):
    # Mock terraform schema output
    mock_schema_result = MagicMock()
    mock_schema_result.stdout = '{"provider_schemas": {}}'
    
    # Mock terraform version output
    mock_version_result = MagicMock()
    mock_version_result.stdout = '{"provider_selections": {"hashicorp/aws": "5.0.0"}}'
    
    mock_run.side_effect = [MagicMock(), mock_schema_result, mock_version_result]
    
    fetch_schemas()
    
    assert mock_run.call_count == 3
    # Check if we wrote schema.json and versions.json
    # The first write is main.tf, then schema.json, then versions.json
    assert mock_write.call_count == 3
