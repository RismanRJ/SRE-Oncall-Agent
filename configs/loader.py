import yaml
from pathlib import Path
from typing import List

CONFIG_DIR = Path(__file__).parent / "services"


def load_service_config(service_name: str) -> dict:
    """Load YAML config for a service. Raises FileNotFoundError if not found."""
    config_path = CONFIG_DIR / f"{service_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Service config not found: {config_path}")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def list_service_names() -> List[str]:
    """Return all configured service names (one per YAML file in configs/services/)."""
    return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))
