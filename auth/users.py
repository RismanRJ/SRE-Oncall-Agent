"""Hardcoded user credentials and roles for MVP."""

USERS_DB = {
    "admin@example.com": {
        "password": "change-me-admin",
        "name": "Admin User",
        "role": "admin",
        "phone": "+1-555-0100",
        "slack_id": "U000ADMIN",
    },
    "alice@example.com": {
        "password": "change-me-alice",
        "name": "Alice Engineer",
        "role": "engineer",
        "phone": "+1-555-0101",
        "slack_id": "U000ALICE",
    },
    "bob@example.com": {
        "password": "change-me-bob",
        "name": "Bob Engineer",
        "role": "engineer",
        "phone": "+1-555-0102",
        "slack_id": "U000BOB",
    },
    "carol@example.com": {
        "password": "change-me-carol",
        "name": "Carol Engineer",
        "role": "engineer",
        "phone": "+1-555-0103",
        "slack_id": "U000CAROL",
    },
}


def validate_user(email: str, password: str) -> dict:
    """Validate credentials. Return user dict or None."""
    user = USERS_DB.get(email)
    if user and user["password"] == password:
        return {"email": email, **{k: v for k, v in user.items() if k != "password"}}
    return None


def get_all_engineers() -> list:
    """Get all engineers (non-admin)."""
    return [
        {"email": email, "name": data["name"], "role": data["role"], "phone": data["phone"]}
        for email, data in USERS_DB.items()
        if data["role"] == "engineer"
    ]


def get_user(email: str) -> dict:
    """Get user by email (without password)."""
    user = USERS_DB.get(email)
    if user:
        return {"email": email, **{k: v for k, v in user.items() if k != "password"}}
    return None
