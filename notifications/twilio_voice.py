"""
Outbound voice call notifications via Twilio, for critical incidents.
Speaks the incident summary using inline TwiML (no webhook/public URL needed).
"""
import os
from typing import Dict
from .base import Notifier


def _build_twiml(incident: Dict) -> str:
    service = incident.get("service", "unknown service")
    breach_metric = incident.get("breach_metric", "a metric")
    breach_value = incident.get("breach_value", "an abnormal value")
    rca = incident.get("rca", {}) or {}
    root_cause = rca.get("root_cause", "Root cause not yet determined.")

    message = (
        f"Critical alert. Service {service} has breached {breach_metric} "
        f"at {breach_value}. "
        f"Root cause analysis: {root_cause} "
        f"Please check Slack and the dashboard for full details. "
        f"This message will now repeat. "
    )
    # <Say> twice so a slow-to-answer engineer doesn't miss the start
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say>{message}</Say>"
        f"<Say>{message}</Say>"
        "</Response>"
    )


class TwilioVoiceNotifier(Notifier):
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")

    def send_warning(self, incident: Dict) -> None:
        # Warnings don't page via voice call - Slack only.
        pass

    def send_critical(self, incident: Dict) -> None:
        service = incident.get("service", "unknown")
        breach_metric = incident.get("breach_metric", "N/A")
        oncall = incident.get("oncall_engineer") or {}
        phone = oncall.get("phone")

        if not self.account_sid or not self.auth_token or not self.from_number:
            print(f"[Twilio voice stub] Would call {phone or 'unknown phone'}: "
                  f"CRITICAL {service} - {breach_metric} breached "
                  f"(TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER not fully set)")
            return

        if not phone:
            print(f"[Twilio voice] No on-call phone number available for {service} - skipping call")
            return

        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            call = client.calls.create(
                to=phone,
                from_=self.from_number,
                twiml=_build_twiml(incident),
            )
            print(f"[Twilio voice] Call initiated to {phone}, SID={call.sid}")
        except Exception as e:
            print(f"[Twilio voice] Call failed ({e}) - falling back to stub log: "
                  f"Would call {phone} - CRITICAL {service} - {breach_metric} breached")
