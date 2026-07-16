"""Test fixtures and configuration."""
from pathlib import Path
import json

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a saved CapturedPage JSON fixture."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text())


def save_fixture(name: str, data: dict) -> None:
    """Save a CapturedPage as a JSON fixture."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
