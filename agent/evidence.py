"""
Deterministic evidence gathering for RCA. Always uses fixed, parameterized tool calls
(never LLM-constructed queries). Pulls the breaching app's own metrics/slow transactions
plus shared infrastructure (Aurora + Redis) state, since most services depend on them.
"""
from typing import Dict
from configs.loader import load_service_config
from metrics.fetcher import fetch_all_metrics
from tools.newrelic import NewRelicClient

SHARED_INFRA_SERVICES = ["aurora-primary", "redis-cache-1", "redis-cache-2"]


def gather_evidence(incident_data: Dict, service_config: Dict) -> Dict:
    """
    Build a fixed evidence bundle for RCA reasoning.

    Args:
        incident_data: dict with service, severity, breach_metric, breach_value, all_breaches, metrics
        service_config: the breaching service's YAML config

    Returns:
        dict with service, severity, breach info, app_metrics, slow_transactions, infra
    """
    service_name = incident_data.get("service")
    app_metrics = incident_data.get("metrics", {})

    nr_config = service_config.get("newrelic", {})
    app_name = nr_config.get("app_name")

    slow_transactions = []
    if app_name:
        try:
            client = NewRelicClient()
            slow_transactions = client.get_slow_transactions(app_name, limit=5, lookback_minutes=60)
        except Exception as e:
            slow_transactions = [{"error": str(e)}]

    infra_metrics = {}
    for infra_svc in SHARED_INFRA_SERVICES:
        if infra_svc == service_name:
            continue  # don't re-fetch if the breaching service IS the infra itself
        try:
            infra_cfg = load_service_config(infra_svc)
            infra_metrics[infra_svc] = fetch_all_metrics(infra_cfg)
        except Exception as e:
            infra_metrics[infra_svc] = {"error": str(e)}

    return {
        "service": service_name,
        "severity": incident_data.get("severity"),
        "breach_metric": incident_data.get("breach_metric"),
        "breach_value": incident_data.get("breach_value"),
        "all_breaches": incident_data.get("all_breaches", []),
        "app_metrics": app_metrics,
        "slow_transactions": slow_transactions,
        "infra": infra_metrics,
    }


def evidence_for_reasoning(evidence: Dict) -> Dict:
    """
    Trim evidence before handing it to the LLM: drop per-reader CPU breakdowns.
    Reader instances (e.g. metabase, analytics replicas) don't serve the app's own
    traffic, so their CPU is noise for causation - only the writer's CPU/connections
    and the cluster-wide instance count are relevant to app-facing latency.
    """
    trimmed_infra = {}
    for svc_name, svc_metrics in (evidence.get("infra") or {}).items():
        if not isinstance(svc_metrics, dict):
            trimmed_infra[svc_name] = svc_metrics
            continue
        db = svc_metrics.get("database")
        if isinstance(db, dict) and "readers" in db:
            db = {k: v for k, v in db.items() if k != "readers"}
            svc_metrics = {**svc_metrics, "database": db}
        trimmed_infra[svc_name] = svc_metrics

    return {**evidence, "infra": trimmed_infra}
