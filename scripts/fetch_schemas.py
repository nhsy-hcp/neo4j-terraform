import json
import shutil
import subprocess
import os
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("providers.json")
WORK_DIR = Path(".cache")

# Source registry for non-hashicorp providers
PROVIDER_SOURCES = {
    "github": "integrations/github",
    "okta": "okta/okta",
}

TF_CONFIG = """
terraform {
  required_providers {
    %s
  }
}
"""


def load_config(config_path: Path) -> dict[str, str | None]:
    """Load provider config from JSON file.

    Expected format:
    {
      "aws": null,           # latest version
      "google": "~> 5.0",    # version constrained
      "github": "= 6.2.1"   # pinned version
    }

    Returns dict of provider_name -> version_constraint (None for latest).
    """
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    if not isinstance(config, dict) or not config:
        print(f"Config must be a non-empty JSON object: {config_path}", file=sys.stderr)
        sys.exit(1)

    return config


def get_source(provider: str) -> str:
    """Resolve a provider name to its registry source."""
    return PROVIDER_SOURCES.get(provider, f"hashicorp/{provider}")


def generate_tf_config(providers: dict[str, str | None]) -> str:
    """Generate a Terraform config block from the provider dict."""
    provider_blocks = []
    for name, version in providers.items():
        source = get_source(name)
        if version:
            provider_blocks.append(f'    {name} = {{ source = "{source}", version = "{version}" }}')
        else:
            provider_blocks.append(f'    {name} = {{ source = "{source}" }}')

    return TF_CONFIG % "\n".join(provider_blocks)


def run_terraform(args: list[str], cwd: Path, capture: bool = False, **kwargs) -> subprocess.CompletedProcess:
    """Run a terraform command with consistent error handling."""
    try:
        return subprocess.run(
            ["terraform", *args],
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=True,
            **kwargs,
        )
    except FileNotFoundError:
        print("terraform is not installed or not on PATH", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        cmd_str = " ".join(["terraform", *args])
        print(f"Command failed: {cmd_str} (exit code {e.returncode})", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)


def fetch_schemas(config_path: Path):
    providers = load_config(config_path)
    print(f"Loaded {len(providers)} providers from {config_path}")

    # Clean stale state to avoid init conflicts
    tf_dir = WORK_DIR / ".terraform"
    lock_file = WORK_DIR / ".terraform.lock.hcl"
    if tf_dir.exists():
        shutil.rmtree(tf_dir)
    if lock_file.exists():
        lock_file.unlink()

    WORK_DIR.mkdir(exist_ok=True)

    tf_file = WORK_DIR / "main.tf"
    tf_file.write_text(generate_tf_config(providers))

    # Disable plugin cache so pinned versions are always fetched fresh
    print(f"Running terraform init in {WORK_DIR}...")
    env = os.environ.copy()
    env["TF_PLUGIN_CACHE_DIR"] = ""
    run_terraform(["init"], cwd=WORK_DIR, env=env)

    print("Exporting schemas to JSON...")
    result = run_terraform(["providers", "schema", "-json"], cwd=WORK_DIR, capture=True)

    # Validate the output is real JSON before saving
    try:
        schema_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"terraform schema output is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    schema_path = WORK_DIR / "schema.json"
    schema_path.write_text(json.dumps(schema_data))
    print(f"Schema saved to {schema_path}")

    print("Fetching provider versions...")
    version_result = run_terraform(["version", "-json"], cwd=WORK_DIR, capture=True)
    version_data = json.loads(version_result.stdout)
    provider_versions = version_data.get("provider_selections", {})

    versions_path = WORK_DIR / "versions.json"
    versions_path.write_text(json.dumps(provider_versions, indent=2))
    print(f"Versions saved to {versions_path}")


if __name__ == "__main__":
    config = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    fetch_schemas(config)
