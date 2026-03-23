import json
import subprocess
import os
from pathlib import Path

PROVIDERS = [
    "aws",
    "google",
    "azurerm",
    "kubernetes",
    "helm",
    "vault",
    "consul",
    "http",
    "archive",
    "github",
    "cloudinit",
    "okta",
    "null",
    "random",
    "local",
    "tls",
    "time",
]

TF_CONFIG = """
terraform {
  required_providers {
    %s
  }
}
"""


def generate_tf_config(providers):
    provider_blocks = []
    for p in providers:
        if p == "google":
            source = "hashicorp/google"
        elif p == "azurerm":
            source = "hashicorp/azurerm"
        elif p == "aws":
            source = "hashicorp/aws"
        elif p == "github":
            source = "integrations/github"
        elif p == "okta":
            source = "okta/okta"
        else:
            source = f"hashicorp/{p}"

        provider_blocks.append(f'    {p} = {{ source = "{source}" }}')

    return TF_CONFIG % "\n".join(provider_blocks)


def fetch_schemas():
    work_dir = Path(".cache")
    work_dir.mkdir(exist_ok=True)

    tf_file = work_dir / "main.tf"
    tf_file.write_text(generate_tf_config(PROVIDERS))

    print(f"Running terraform init in {work_dir}...")
    env = os.environ.copy()
    env["TF_PLUGIN_CACHE_DIR"] = ""
    subprocess.run(["terraform", "init"], cwd=work_dir, check=True, env=env)

    print("Exporting schemas to JSON...")
    result = subprocess.run(
        ["terraform", "providers", "schema", "-json"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        check=True,
    )

    Path("schema.json").write_text(result.stdout)
    print("Schema saved to schema.json")

    print("Fetching provider versions...")
    version_result = subprocess.run(
        ["terraform", "version", "-json"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    version_data = json.loads(version_result.stdout)
    provider_versions = version_data.get("provider_selections", {})

    Path("versions.json").write_text(json.dumps(provider_versions, indent=2))
    print("Versions saved to versions.json")


if __name__ == "__main__":
    fetch_schemas()
