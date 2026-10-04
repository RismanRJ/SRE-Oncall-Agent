from pydantic import BaseModel
from typing import List, Optional


class RCAIncident(BaseModel):
    incident_id: str
    service: str
    timestamp: str
    severity: str
    breach_metric: str
    breach_value: float
    root_cause: str
    evidence: List[str]
    suggestion: str
    confidence: str = "unknown"
    symptom_summary: Optional[str] = None
    affected_endpoint: Optional[str] = None
    correlated_signals: List[str] = []
    ruled_out: List[str] = []
    likely_layer: Optional[str] = None
