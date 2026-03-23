from scripts.fetch_schemas import generate_tf_config


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
    # Should contain nothing in the block
    assert (
        "    \n" in config or "      \n" in config
    )  # exact spacing depends on implementation
