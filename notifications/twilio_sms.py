"""SMS text notifications via Twilio (same account/number as the voice notifier)."""
import os
from typing import Dict
from .base import Notifier


def _build_message(incident: Dict) -> str:
    severity = incident.get("severity", "warning").upper()
    service = incident.get("service", "unknown service")
    breach_metric = incident.get("breach_metric", "N/A")
    breach_value = incident.get("breach_value", "N/A")
    incident_id = incident.get("incident_id", "N/A")
    rca = incident.get("rca", {}) or {}

    lines = [
        f"{severity} - {service}",
        f"Metric: {breach_metric} = {breach_value}",
        f"Incident: {incident_id}",
    ]
    if rca.get("affected_endpoint"):
        lines.append(f"Endpoint: {rca['affected_endpoint']}")
    if rca.get("root_cause"):
        lines.append(f"Root Cause ({rca.get('confidence', 'unknown')}): {rca['root_cause']}")
    if rca.get("suggestion"):
        lines.append(f"Suggested Action: {rca['suggestion']}")

    return "\n".join(lines)


class TwilioSMSNotifier(Notifier):
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")

    def _send(self, incident: Dict) -> None:
        oncall = incident.get("oncall_engineer") or {}
        phone = oncall.get("phone")
        service = incident.get("service", "unknown")
        breach_metric = incident.get("breach_metric", "N/A")

        if not self.account_sid or not self.auth_token or not self.from_number:
            print(f"[Twilio SMS stub] Would text {phone or 'unknown phone'}: "
                  f"{incident.get('severity', 'warning').upper()} {service} - {breach_metric} breached "
                  f"(TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER not fully set)")
            return

        if not phone:
            print(f"[Twilio SMS] No on-call phone number available for {service} - skipping message")
            return

        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(
                to=phone,
                from_=self.from_number,
                body=_build_message(incident),
            )
            print(f"[Twilio SMS] Message sent to {phone}, SID={msg.sid}")
        except Exception as e:
            print(f"[Twilio SMS] Send failed ({e}) - falling back to stub log: "
                  f"Would text {phone} - {incident.get('severity', 'warning').upper()} "
                  f"{service} - {breach_metric} breached")

    def send_warning(self, incident: Dict) -> None:
        self._send(incident)

    def send_critical(self, incident: Dict) -> None:
        self._send(incident)
