"""Routes incident notifications to configured channels based on severity, per service YAML."""
from typing import Dict, List
from .slack import SlackNotifier
from .aws_critical import AWSCriticalNotifier
from .twilio_voice import TwilioVoiceNotifier
from .twilio_sms import TwilioSMSNotifier

_NOTIFIERS = {
    "slack": SlackNotifier(),
    "sns": AWSCriticalNotifier(),
    "voice_call": TwilioVoiceNotifier(),
    "sms": TwilioSMSNotifier(),
}


def dispatch(incident: Dict, channels: List[str]) -> None:
    """
    Send incident notifications to the given channels.

    Args:
        incident: dict with service, severity, breach_metric, breach_value, incident_id,
                  timestamp, rca (dict), oncall_engineer (dict)
        channels: list like ["slack", "sns", "voice_call"] (from service YAML notifications config)
    """
    severity = incident.get("severity", "warning")
    sent = set()

    for channel in channels:
        notifier = _NOTIFIERS.get(channel)
        if not notifier or id(notifier) in sent:
            continue
        sent.add(id(notifier))

        try:
            if severity == "critical":
                notifier.send_critical(incident)
            else:
                notifier.send_warning(incident)
        except Exception as e:
            print(f"Notification dispatch failed for channel {channel}: {e}")
