"""On-call schedule management (flexible date ranges)."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

SCHEDULE_FILE = Path(__file__).parent.parent / "storage" / "oncall_schedule.json"


def ensure_schedule_file():
    """Ensure schedule file exists with default rotation."""
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SCHEDULE_FILE.exists():
        # Initialize with default weekly rotation (converted to date ranges)
        today = datetime.utcnow().date()
        monday = today - timedelta(days=today.weekday())  # Start of this week

        default_schedule = {
            "rotations": [
                {
                    "start_date": (monday).isoformat(),
                    "end_date": (monday + timedelta(days=6)).isoformat(),
                    "engineer_email": "bob@company.com"
                },
            ]
        }
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(default_schedule, f, indent=2)


def load_schedule() -> dict:
    """Load current on-call schedule."""
    ensure_schedule_file()
    with open(SCHEDULE_FILE, "r") as f:
        return json.load(f)


def save_schedule(schedule: dict):
    """Save on-call schedule."""
    ensure_schedule_file()
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)


def get_oncall_engineer(date: datetime = None) -> Optional[dict]:
    """
    Get on-call engineer for a given date.
    Returns dict with engineer email, name, phone, etc.
    """
    if date is None:
        date = datetime.utcnow()

    date_obj = date.date() if isinstance(date, datetime) else date
    schedule = load_schedule()

    # Find rotation that covers this date
    for rotation in schedule.get("rotations", []):
        start = datetime.fromisoformat(rotation["start_date"]).date()
        end = datetime.fromisoformat(rotation["end_date"]).date()

        if start <= date_obj <= end:
            engineer_email = rotation["engineer_email"]
            from auth.users import get_user
            return get_user(engineer_email)

    return None


def add_rotation(start_date: str, end_date: str, engineer_email: str) -> bool:
    """
    Add a new rotation period.

    Args:
        start_date: ISO format date string (YYYY-MM-DD)
        end_date: ISO format date string (YYYY-MM-DD)
        engineer_email: Engineer's email

    Returns:
        True if added successfully, False otherwise
    """
    try:
        # Validate dates
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()

        if start > end:
            return False

        schedule = load_schedule()

        # Add new rotation
        new_rotation = {
            "start_date": start_date,
            "end_date": end_date,
            "engineer_email": engineer_email
        }

        # Check for overlaps and remove if needed
        schedule["rotations"] = [
            rot for rot in schedule.get("rotations", [])
            if not (
                (datetime.fromisoformat(rot["start_date"]).date() <= end and
                 datetime.fromisoformat(rot["end_date"]).date() >= start)
            )
        ]

        schedule["rotations"].append(new_rotation)
        schedule["rotations"].sort(key=lambda x: x["start_date"])

        save_schedule(schedule)
        return True
    except ValueError:
        return False


def get_all_rotations() -> List[Dict]:
    """Get all scheduled rotations."""
    schedule = load_schedule()
    rotations = schedule.get("rotations", [])

    # Enhance with engineer names
    from auth.users import get_user
    for rotation in rotations:
        user = get_user(rotation["engineer_email"])
        if user:
            rotation["engineer_name"] = user.get("name")
        else:
            rotation["engineer_name"] = "Unknown"

    return sorted(rotations, key=lambda x: x["start_date"])


def delete_rotation(start_date: str, end_date: str) -> bool:
    """Delete a rotation period."""
    schedule = load_schedule()
    initial_count = len(schedule.get("rotations", []))

    schedule["rotations"] = [
        rot for rot in schedule.get("rotations", [])
        if not (rot["start_date"] == start_date and rot["end_date"] == end_date)
    ]

    save_schedule(schedule)
    return len(schedule["rotations"]) < initial_count
