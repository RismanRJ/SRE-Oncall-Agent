"""
RCA reasoning pipeline: gather fixed evidence -> 3-stage LLM reasoning
(symptom -> correlation -> root cause) -> structured RCAIncident.
"""
import json
import re
from typing import Dict, Optional
from agent.providers.factory import get_provider
from agent.evidence import gather_evidence, evidence_for_reasoning
from agent import prompts
from agent.schema import RCAIncident


def _parse_json(raw: str) -> Optional[dict]:
    """Best-effort JSON parse: try direct parse, then extract the first {...} block."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _run_stage(provider, prompt: str, fallback: dict) -> dict:
    try:
        raw = provider.complete(prompt, system=prompts.SYSTEM_PROMPT, json_mode=True)
        parsed = _parse_json(raw)
        return parsed if parsed is not None else fallback
    except Exception as e:
        print(f"RCA reasoning stage failed: {e}")
        return fallback


def analyze_incident(incident_data: Dict, service_config: Dict = None) -> RCAIncident:
    """
    Run the multi-stage RCA reasoning pipeline for a detected breach.

    Args:
        incident_data: dict with service, timestamp, severity, breach_metric, breach_value,
                        all_breaches, metrics (as built by server.py's webhook_check)
        service_config: the breaching service's YAML config (for New Relic app_name lookup)

    Returns:
        RCAIncident with root_cause, evidence, suggestion, confidence, and reasoning trace.
    """
    provider = get_provider()
    full_evidence = gather_evidence(incident_data, service_config or {})
    evidence = evidence_for_reasoning(full_evidence)  # reader CPU stripped before it reaches the LLM

    # Stage 1: Symptom analysis - identify the specific endpoint responsible
    symptom = _run_stage(
        provider,
        prompts.symptom_prompt(evidence),
        fallback={
            "summary": f"{evidence['breach_metric']} breached at {evidence['breach_value']}",
            "affected_endpoint": "unknown",
            "endpoint_tp99_ms": None,
            "endpoint_bottleneck": "unknown",
            "magnitude": "unknown",
        },
    )

    # Stage 2: Correlation against writer DB / Redis / App Runner CPU only
    correlation = _run_stage(
        provider,
        prompts.correlation_prompt(evidence, symptom),
        fallback={"correlated_signals": [], "ruled_out": [], "likely_layer": "unknown"},
    )

    # Stage 3: Root cause synthesis
    rca_analysis = _run_stage(
        provider,
        prompts.root_cause_prompt(evidence, symptom, correlation),
        fallback={
            "root_cause": "Unable to determine root cause - LLM reasoning failed. Manual investigation required.",
            "evidence": [f"{evidence['breach_metric']} = {evidence['breach_value']}"],
            "suggestion": "Check service logs and shared infrastructure (Aurora writer, Redis) manually.",
            "confidence": "low",
        },
    )

    return RCAIncident(
        incident_id=incident_data.get("incident_id", "INC000"),
        service=incident_data.get("service"),
        timestamp=incident_data.get("timestamp"),
        severity=incident_data.get("severity"),
        breach_metric=incident_data.get("breach_metric"),
        breach_value=incident_data.get("breach_value"),
        root_cause=rca_analysis.get("root_cause", "Unknown"),
        evidence=rca_analysis.get("evidence", []),
        suggestion=rca_analysis.get("suggestion", "Manual investigation required."),
        confidence=rca_analysis.get("confidence", "unknown"),
        symptom_summary=symptom.get("summary"),
        affected_endpoint=symptom.get("affected_endpoint"),
        correlated_signals=correlation.get("correlated_signals", []),
        ruled_out=correlation.get("ruled_out", []),
        likely_layer=correlation.get("likely_layer"),
    )
