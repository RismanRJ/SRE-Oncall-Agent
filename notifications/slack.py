"""Real Slack notifications via chat.postMessage, with @oncall mentions on critical alerts."""
import os
import httpx
from typing import Dict, Optional
from .base import Notifier

SLACK_API_URL = "https://slack.com/api/chat.postMessage"


class SlackNotifier(Notifier):
    def __init__(self):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.channel_id = os.getenv("SLACK_CHANNEL_ID")

    def _post(self, text: str, blocks: list) -> None:
        if not self.bot_token or not self.channel_id:
            print("Slack not configured (SLACK_BOT_TOKEN/SLACK_CHANNEL_ID missing) - skipping notification")
            return

        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"channel": self.channel_id, "text": text, "blocks": blocks}

        try:
            resp = httpx.post(SLACK_API_URL, headers=headers, json=payload, timeout=10.0)
            data = resp.json()
            if not data.get("ok"):
                print(f"Slack API error: {data.get('error')}")
        except httpx.HTTPError as e:
            print(f"Slack notification failed: {e}")

    def _build_blocks(self, incident: Dict, mention: Optional[str] = None) -> list:
        severity = incident.get("severity", "warning")
        emoji = "🔴" if severity == "critical" else "🟡"
        service = incident.get("service", "unknown")
        rca = incident.get("rca", {}) or {}

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {severity.upper()} — {service}", "emoji": True},
            },
        ]

        if mention:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"<@{mention}> you're on-call — this needs attention."},
            })

        breach_fields = [
            f"*Metric:* {incident.get('breach_metric', 'N/A')}",
            f"*Value:* {incident.get('breach_value', 'N/A')}",
            f"*Incident ID:* {incident.get('incident_id', 'N/A')}",
            f"*Timestamp:* {incident.get('timestamp', 'N/A')}",
        ]
        blocks.append({
            "type": "section",
            "fields": [{"type": "mrkdwn", "text": f} for f in breach_fields],
        })

        if rca.get("affected_endpoint") or rca.get("likely_layer"):
            blocks.append({"type": "divider"})
            layer_fields = []
            if rca.get("affected_endpoint"):
                layer_fields.append(f"*Affected Endpoint:*\n`{rca['affected_endpoint']}`")
            if rca.get("likely_layer"):
                layer_fields.append(f"*Likely Layer:*\n{rca['likely_layer']}")
            blocks.append({
                "type": "section",
                "fields": [{"type": "mrkdwn", "text": f} for f in layer_fields],
            })

        if rca.get("root_cause"):
            confidence = rca.get("confidence", "unknown")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause* (confidence: {confidence}):\n{rca['root_cause']}"},
            })

        if rca.get("evidence"):
            evidence_text = "\n".join(f"• {e}" for e in rca["evidence"])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Evidence:*\n{evidence_text}"},
            })

        if rca.get("ruled_out"):
            ruled_out_text = "\n".join(f"• {r}" for r in rca["ruled_out"])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Ruled Out:*\n{ruled_out_text}"},
            })

        if rca.get("suggestion"):
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Suggested Action:*\n{rca['suggestion']}"},
            })

        return blocks

    def send_warning(self, incident: Dict) -> None:
        service = incident.get("service", "unknown")
        breach_metric = incident.get("breach_metric", "N/A")
        text = f"WARNING — {service}: {breach_metric} breached"
        self._post(text, self._build_blocks(incident, mention=None))

    def send_critical(self, incident: Dict) -> None:
        service = incident.get("service", "unknown")
        breach_metric = incident.get("breach_metric", "N/A")
        oncall = incident.get("oncall_engineer") or {}
        slack_id = oncall.get("slack_id")

        text = f"CRITICAL — {service}: {breach_metric} breached"
        if slack_id:
            text = f"<@{slack_id}> {text}"

        self._post(text, self._build_blocks(incident, mention=slack_id))
