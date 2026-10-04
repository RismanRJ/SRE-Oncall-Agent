"""
Multi-stage RCA reasoning prompts. Each stage is a constrained, JSON-only completion
that builds on the previous stage's output, so the model reasons in narrowing steps
(symptom -> correlation -> root cause) instead of one single-shot guess.
"""
import json

SYSTEM_PROMPT = (
    "You are a senior SRE analyzing a production incident. "
    "You only reason from the data given to you - never invent metrics, endpoint names, or numbers. "
    "Respond with strict JSON only. No markdown, no code fences, no prose outside the JSON object."
)


def symptom_prompt(evidence: dict) -> str:
    return f"""Service: {evidence['service']}
Severity: {evidence['severity']}
Primary breach: {evidence['breach_metric']} = {evidence['breach_value']}
All breaches: {json.dumps(evidence['all_breaches'])}
App metrics (New Relic + CloudWatch CPU/instances): {json.dumps(evidence['app_metrics'])}

Top slow transactions in the last 60 minutes, each with a "bottleneck" field already
computed from database-time vs external-call-time vs total duration
("database" | "external_call" | "application"):
{json.dumps(evidence['slow_transactions'])}

Task: Identify the SPECIFIC endpoint/transaction most responsible for the breach (name it
exactly as it appears above - do not paraphrase). State its own TP99, request volume, and
its "bottleneck" classification. Summarize the symptom in 2-3 sentences using these specifics,
and estimate the magnitude of degradation with real numbers (e.g. "TP99 is 2.8x the 1500ms
threshold, driven by an endpoint with 8500ms TP99 over 400 requests").

Respond with JSON only:
{{"summary": "2-3 sentences", "affected_endpoint": "exact transaction name or 'multiple/unclear'",
  "endpoint_tp99_ms": <number or null>, "endpoint_bottleneck": "database" | "external_call" | "application" | "unknown",
  "magnitude": "..."}}"""


def correlation_prompt(evidence: dict, symptom: dict) -> str:
    return f"""Symptom analysis from previous stage: {json.dumps(symptom)}

Shared infrastructure metrics (Aurora Postgres writer + Redis, used by this and other services):
{json.dumps(evidence['infra'])}

IMPORTANT: Only the Aurora *writer* instance's CPU, connection counts, and idle-in-transaction
count matter for causation. Reader/replica instances (e.g. analytics/BI replicas) do not serve
this app's traffic - do not cite their CPU as a cause even if it looks high. If the endpoint's
bottleneck classification from the symptom stage was "database", check whether the writer's
CPU or connection count actually explains it; if not, say the correlation is weak/absent.
Also check Redis memory/eviction/hit-rate if the app uses caching, and whether App Runner CPU/
instance count for this specific service is elevated (a CPU-bound app instance can cause
latency independent of any shared infra).

Task: Determine whether the symptom correlates with the writer database, App Runner CPU, or
Redis. Only cite a correlation if the numbers genuinely support it. Be explicit about what you
checked and ruled out, not just what you're claiming.

Respond with JSON only:
{{"correlated_signals": ["specific signal with the actual number, e.g. 'writer CPU at 82%'"],
  "ruled_out": ["signal checked but not causal, e.g. 'writer connections at 4% - not saturated'"],
  "likely_layer": "application" | "database" | "cache" | "external_dependency" | "unknown"}}"""


def root_cause_prompt(evidence: dict, symptom: dict, correlation: dict) -> str:
    return f"""Symptom analysis: {json.dumps(symptom)}
Correlation analysis: {json.dumps(correlation)}
Raw breach data: {json.dumps(evidence['all_breaches'])}
Slow transactions: {json.dumps(evidence['slow_transactions'])}
App metrics: {json.dumps(evidence['app_metrics'])}
Infra metrics (writer DB + Redis only): {json.dumps(evidence['infra'])}

Task: Write a detailed, specific root cause analysis for an SRE incident report. Name the
exact endpoint/transaction responsible. State whether the bottleneck is database, external
call, or application-layer, and back it with the actual db_time_ms/external_time_ms/tp99_ms
numbers from the slow transactions data. If a shared-infra signal was correlated, state the
specific writer-instance number that supports it - never cite reader/replica CPU as a cause.
If the evidence doesn't clearly point to one cause, say so explicitly rather than guessing.

Respond with JSON only:
{{"root_cause": "3-4 sentences, specific and evidence-based, names the exact endpoint",
  "evidence": ["6-8 concrete bullet points citing real numbers - endpoint names, ms values, CPU/connection percentages, request counts"],
  "suggestion": "specific, actionable remediation step(s) targeting the identified layer",
  "confidence": "low" | "medium" | "high"}}"""
