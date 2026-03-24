import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_schemas import generate_tf_config, fetch_schemas


def test_generate_tf_config():
    providers = {"aws": None, "google": None, "null": None}
    config = generate_tf_config(providers)

    assert "terraform {" in config
    assert "required_providers {" in config
    assert 'aws = { source = "hashicorp/aws" }' in config
    assert 'google = { source = "hashicorp/google" }' in config
    assert 'null = { source = "hashicorp/null" }' in config


def test_generate_tf_config_with_versions():
    providers = {
        "aws": None,  # latest
        "google": "~> 5.0",  # version constraint
        "null": "= 1.0.0",  # pinned
    }
    config = generate_tf_config(providers)

    assert "terraform {" in config
    assert "required_providers {" in config
    assert 'aws = { source = "hashicorp/aws" }' in config
    assert 'google = { source = "hashicorp/google", version = "~> 5.0" }' in config
    assert 'null = { source = "hashicorp/null", version = "= 1.0.0" }' in config


def test_generate_tf_config_custom_sources():
    providers = {"github": None, "okta": "~> 4.0", "aws": None}
    config = generate_tf_config(providers)

    assert 'github = { source = "integrations/github" }' in config
    assert 'okta = { source = "okta/okta", version = "~> 4.0" }' in config
    assert 'aws = { source = "hashicorp/aws" }' in config


def test_generate_tf_config_empty():
    config = generate_tf_config({})
    assert "terraform {" in config
    assert "required_providers {" in config


def test_get_source_hashicorp_default():
    from scripts.fetch_schemas import get_source

    assert get_source("aws") == "hashicorp/aws"
    assert get_source("google") == "hashicorp/google"
    assert get_source("azurerm") == "hashicorp/azurerm"


def test_get_source_custom_providers():
    from scripts.fetch_schemas import get_source

    assert get_source("github") == "integrations/github"
    assert get_source("okta") == "okta/okta"


def test_load_config_success():
    from scripts.fetch_schemas import load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        config_data = {"aws": None, "google": "~> 5.0", "null": "= 1.0.0"}
        json.dump(config_data, f)
        config_path = Path(f.name)

    try:
        result = load_config(config_path)
        assert result == config_data
        assert result["aws"] is None
        assert result["google"] == "~> 5.0"
        assert result["null"] == "= 1.0.0"
    finally:
        config_path.unlink()


def test_load_config_missing_file():
    from scripts.fetch_schemas import load_config
    from io import StringIO

    non_existent = Path("/tmp/does_not_exist_12345.json")

    # Capture stderr and expect sys.exit(1)
    old_stderr = sys.stderr
    sys.stderr = StringIO()

    try:
        load_config(non_existent)
        assert False, "Should have called sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1
        stderr_output = sys.stderr.getvalue()
        assert "Config file not found" in stderr_output
    finally:
        sys.stderr = old_stderr


def test_load_config_invalid_json():
    from scripts.fetch_schemas import load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{ invalid json }")
        config_path = Path(f.name)

    try:
        load_config(config_path)
        assert False, "Should have raised JSONDecodeError"
    except json.JSONDecodeError:
        pass
    finally:
        config_path.unlink()


def test_load_config_empty_object():
    from scripts.fetch_schemas import load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        config_path = Path(f.name)

    try:
        load_config(config_path)
        assert False, "Should have called sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1
    finally:
        config_path.unlink()


def test_load_config_not_dict():
    from scripts.fetch_schemas import load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(["aws", "google"], f)
        config_path = Path(f.name)

    try:
        load_config(config_path)
        assert False, "Should have called sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1
    finally:
        config_path.unlink()


@patch("scripts.fetch_schemas.subprocess.run")
def test_run_terraform_not_found(mock_run):
    from scripts.fetch_schemas import run_terraform

    mock_run.side_effect = FileNotFoundError()

    try:
        run_terraform(["version"], cwd=Path("."))
        assert False, "Should have called sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1


@patch("scripts.fetch_schemas.subprocess.run")
def test_run_terraform_command_failure(mock_run):
    from scripts.fetch_schemas import run_terraform
    import subprocess

    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["terraform", "init"], stderr="Error: something went wrong"
    )

    try:
        run_terraform(["init"], cwd=Path("."))
        assert False, "Should have called sys.exit(1)"
    except SystemExit as e:
        assert e.code == 1


@patch("scripts.fetch_schemas.subprocess.run")
@patch("scripts.fetch_schemas.Path.mkdir")
@patch("scripts.fetch_schemas.Path.write_text")
@patch("scripts.fetch_schemas.Path.exists", return_value=True)
@patch("scripts.fetch_schemas.shutil.rmtree")
@patch("scripts.fetch_schemas.Path.unlink")
def test_fetch_schemas(mock_unlink, mock_rmtree, mock_exists, mock_write, mock_mkdir, mock_run):
    # Mock terraform schema output
    mock_schema_result = MagicMock()
    mock_schema_result.stdout = '{"provider_schemas": {"registry.terraform.io/hashicorp/aws": {}}}'

    # Mock terraform version output
    mock_version_result = MagicMock()
    mock_version_result.stdout = '{"provider_selections": {"registry.terraform.io/hashicorp/aws": "5.0.0"}}'

    mock_run.side_effect = [MagicMock(), mock_schema_result, mock_version_result]

    fetch_schemas(Path("scripts/providers.json"))

    # Verify terraform commands were called
    assert mock_run.call_count == 3

    # Verify file writes: main.tf, schema.json, versions.json
    assert mock_write.call_count == 3

    # Verify main.tf content
    main_tf_call = mock_write.call_args_list[0]
    main_tf_content = main_tf_call[0][0]
    assert "terraform {" in main_tf_content
    assert "required_providers {" in main_tf_content

    # Verify schema.json content is valid JSON
    schema_call = mock_write.call_args_list[1]
    schema_content = schema_call[0][0]
    schema_data = json.loads(schema_content)
    assert "provider_schemas" in schema_data
    assert "registry.terraform.io/hashicorp/aws" in schema_data["provider_schemas"]

    # Verify versions.json content
    version_call = mock_write.call_args_list[2]
    version_content = version_call[0][0]
    version_data = json.loads(version_content)
    assert "registry.terraform.io/hashicorp/aws" in version_data
    assert version_data["registry.terraform.io/hashicorp/aws"] == "5.0.0"
