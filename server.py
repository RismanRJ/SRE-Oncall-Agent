import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from configs.loader import load_service_config, list_service_names
from thresholds.evaluator import evaluate
from agent.graph import analyze_incident
from storage import incidents as incident_storage
from auth.users import validate_user, get_all_engineers
from auth.jwt_handler import create_token, verify_token
from oncall.schedule import get_oncall_engineer, add_rotation, get_all_rotations, delete_rotation
from metrics.fetcher import fetch_all_metrics_sync
from notifications.dispatcher import dispatch as notify_dispatch

app = FastAPI(title="SRE Oncall Agent API")

INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "dev-secret")


class WebhookRequest(BaseModel):
    service: str
    metrics: dict = None  # For testing: override default metrics


class IncidentResponse(BaseModel):
    incident_id: str
    service: str
    timestamp: str
    severity: str
    breach_metric: str
    breach_value: float


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str
    name: str
    role: str


def get_current_user(authorization: str = Header(None)) -> str:
    """Dependency to extract and verify JWT token from header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = parts[1]
    email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return email


@app.post("/webhook/check")
async def webhook_check(
    request: WebhookRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Webhook endpoint triggered by cron every 30 minutes.
    Fetches latest metrics from all configured sources.
    """
    # Prune incidents older than the retention window (1 day) on every hit - no extra infra needed
    incident_storage.cleanup_old_incidents(days=1)

    # Load service config
    try:
        service_config = load_service_config(request.service)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Fetch fresh metrics from all configured sources
    metrics = fetch_all_metrics_sync(service_config)

    # Evaluate ALL metrics against thresholds
    breaches = evaluate(service_config, metrics)

    # Get on-call engineer
    oncall_engineer = get_oncall_engineer()
    notification_config = service_config.get("notifications", {})

    # If any breaches detected
    if breaches:
        timestamp = datetime.utcnow().isoformat()

        # Sort breaches by severity (critical first)
        breaches.sort(key=lambda b: (b.severity != "critical", b.metric_name))

        # Most severe breach
        primary_breach = breaches[0]

        incident_data = {
            "service": request.service,
            "timestamp": timestamp,
            "severity": primary_breach.severity,
            "breach_metric": primary_breach.metric_name,
            "breach_value": primary_breach.metric_value,
            "all_breaches": [b.model_dump() for b in breaches],
            "metrics": metrics,
        }

        # Get RCA from agent (multi-stage reasoning: symptom -> correlation -> root cause)
        rca = analyze_incident(incident_data, service_config)

        # Add on-call engineer info to incident
        incident_with_oncall = rca.model_dump()
        incident_with_oncall["oncall_engineer"] = oncall_engineer

        # Save incident to storage
        incident_id = incident_storage.save_incident(incident_with_oncall)

        # Determine which channels to use for notifications
        notification_channels = []
        if primary_breach.severity == "critical":
            notification_channels = notification_config.get("critical", {}).get("channels", ["slack"])
        else:  # warning
            notification_channels = notification_config.get("warning", {}).get("channels", ["slack"])

        # Dispatch notifications (Slack @oncall on critical, SNS/Connect IVR stub for critical)
        # notify_dispatch(
        #     {
        #         "service": request.service,
        #         "severity": primary_breach.severity,
        #         "breach_metric": primary_breach.metric_name,
        #         "breach_value": primary_breach.metric_value,
        #         "incident_id": incident_id,
        #         "timestamp": timestamp,
        #         "rca": rca.model_dump(),
        #         "oncall_engineer": oncall_engineer,
        #     },
        #     notification_channels,
        # )

        return {
            "status": "breach_detected",
            "service": request.service,
            "incident_id": incident_id,
            "severity": primary_breach.severity,
            "breaches": [b.model_dump() for b in breaches],
            "rca": rca.model_dump(),
            "oncall_engineer": oncall_engineer,
            "notification_channels": notification_channels,
            "metrics": metrics,
        }
    else:
        return {
            "status": "healthy",
            "service": request.service,
            "message": "All metrics within thresholds",
            "oncall_engineer": oncall_engineer,
            "metrics": metrics,
        }


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login endpoint. Returns JWT token."""
    user = validate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(request.email)
    return LoginResponse(
        token=token,
        email=user["email"],
        name=user["name"],
        role=user["role"],
    )


@app.get("/auth/me")
async def get_me(current_user: str = Depends(get_current_user)):
    """Get current user info."""
    from auth.users import get_user

    user = get_user(current_user)
    return user


@app.get("/oncall/engineer")
async def get_oncall(current_user: str = Depends(get_current_user)):
    """Get current on-call engineer."""
    engineer = get_oncall_engineer()
    return engineer or {"error": "No on-call engineer assigned"}


@app.get("/oncall/rotations")
async def get_rotations(current_user: str = Depends(get_current_user)):
    """Get all on-call rotations."""
    return get_all_rotations()


@app.post("/oncall/rotation/add")
async def add_oncall_rotation(
    start_date: str,
    end_date: str,
    engineer_email: str,
    current_user: str = Depends(get_current_user),
):
    """Add new on-call rotation (admin only)."""
    from auth.users import get_user

    user = get_user(current_user)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    if add_rotation(start_date, end_date, engineer_email):
        return {"status": "added", "start_date": start_date, "end_date": end_date}
    raise HTTPException(status_code=400, detail="Invalid dates or engineer email")


@app.post("/oncall/rotation/delete")
async def remove_oncall_rotation(
    start_date: str,
    end_date: str,
    current_user: str = Depends(get_current_user),
):
    """Delete on-call rotation (admin only)."""
    from auth.users import get_user

    user = get_user(current_user)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    if delete_rotation(start_date, end_date):
        return {"status": "deleted", "start_date": start_date, "end_date": end_date}
    raise HTTPException(status_code=400, detail="Rotation not found")


@app.get("/services/list")
async def services_list(current_user: str = Depends(get_current_user)):
    """List all configured service names (one per configs/services/*.yaml)."""
    return {"services": list_service_names()}


@app.get("/services/{service}/slow-transactions")
async def slow_transactions(service: str, limit: int = 10, current_user: str = Depends(get_current_user)):
    """Top slowest transactions (by TP99) for a service's New Relic app."""
    from tools.newrelic import NewRelicClient

    service_config = load_service_config(service)
    nr_config = service_config.get("newrelic", {})
    app_name = nr_config.get("app_name")
    if not app_name:
        raise HTTPException(status_code=400, detail="Service has no New Relic app configured")

    try:
        client = NewRelicClient()
        transactions = client.get_slow_transactions(app_name, limit=limit, lookback_minutes=60)
        return {"service": service, "transactions": transactions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
