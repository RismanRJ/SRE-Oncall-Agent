import json
import os
from datetime import datetime, timedelta
from pathlib import Path

STORAGE_DIR = Path(__file__).parent / "incidents"


def ensure_dir():
    """Ensure storage directory exists."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_incident_dir(date_str: str) -> Path:
    """Get or create directory for a specific date (YYYY-MM-DD)."""
    dir_path = STORAGE_DIR / date_str
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_next_incident_id(date_str: str) -> str:
    """Get the next incident ID for a date."""
    dir_path = get_incident_dir(date_str)
    existing_files = list(dir_path.glob("INC*.json"))
    next_num = len(existing_files) + 1
    return f"INC{next_num:03d}"


def save_incident(incident_data: dict) -> str:
    """
    Save incident to disk.
    Returns the incident ID.
    """
    ensure_dir()
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    incident_id = get_next_incident_id(date_str)

    incident_data["incident_id"] = incident_id
    incident_data["timestamp"] = datetime.utcnow().isoformat()

    incident_path = get_incident_dir(date_str) / f"{incident_id}.json"
    with open(incident_path, "w") as f:
        json.dump(incident_data, f, indent=2)

    return incident_id


def get_incident(incident_id: str, date_str: str = None) -> dict:
    """Get incident by ID. If date_str not provided, search all dates."""
    if date_str:
        incident_path = get_incident_dir(date_str) / f"{incident_id}.json"
        if incident_path.exists():
            with open(incident_path, "r") as f:
                return json.load(f)
    else:
        # Search recent dates (retention is 1 day; small buffer for cleanup lag)
        today = datetime.utcnow()
        for i in range(2):
            search_date = today - timedelta(days=i)
            date_str = search_date.strftime("%Y-%m-%d")
            incident_path = STORAGE_DIR / date_str / f"{incident_id}.json"
            if incident_path.exists():
                with open(incident_path, "r") as f:
                    return json.load(f)
    return None


def list_incidents(limit: int = 50, date_str: str = None) -> list:
    """List recent incidents, optionally filtered by date."""
    incidents = []
    ensure_dir()

    if date_str:
        dir_path = STORAGE_DIR / date_str
        if dir_path.exists():
            for incident_file in sorted(dir_path.glob("INC*.json"), reverse=True):
                with open(incident_file, "r") as f:
                    incidents.append(json.load(f))
                if len(incidents) >= limit:
                    break
    else:
        # Search all recent dates (retention is 1 day; small buffer for cleanup lag)
        today = datetime.utcnow()
        for i in range(2):
            search_date = today - timedelta(days=i)
            date_str = search_date.strftime("%Y-%m-%d")
            dir_path = STORAGE_DIR / date_str
            if dir_path.exists():
                for incident_file in sorted(dir_path.glob("INC*.json"), reverse=True):
                    with open(incident_file, "r") as f:
                        incidents.append(json.load(f))
                    if len(incidents) >= limit:
                        break
            if len(incidents) >= limit:
                break

    return incidents[:limit]


def cleanup_old_incidents(days: int = 1):
    """Delete incidents older than specified days."""
    ensure_dir()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    for date_dir in STORAGE_DIR.iterdir():
        if date_dir.is_dir():
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff_date:
                    # Delete the entire directory
                    import shutil

                    shutil.rmtree(date_dir)
            except ValueError:
                # Skip directories that don't match date format
                pass
