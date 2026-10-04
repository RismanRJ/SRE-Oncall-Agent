from pydantic import BaseModel
from typing import Optional


class Breach(BaseModel):
    metric_name: str
    metric_value: float
    threshold: float
    severity: str
    message: str
