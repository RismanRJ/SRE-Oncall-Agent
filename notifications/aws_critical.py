"""
AWS SNS (SMS) notifications for critical incidents.
Stub until SNS topic is provisioned - logs the exact call that will run
once SNS_TOPIC_ARN is set.

Config key (set in .env when provisioned):
  SNS_TOPIC_ARN

Voice calls are handled separately by notifications/twilio_voice.py
(Amazon Connect isn't available in ap-south-1, so voice IVR moved to Twilio).
"""
import os
from typing import Dict
from .base import Notifier


class AWSCriticalNotifier(Notifier):
    def __init__(self):
        self.sns_topic_arn = os.getenv("SNS_TOPIC_ARN")

    def send_warning(self, incident: Dict) -> None:
        # Warnings don't page via SMS - Slack only.
        pass

    def send_critical(self, incident: Dict) -> None:
        service = incident.get("service", "unknown")
        breach_metric = incident.get("breach_metric", "N/A")
        oncall = incident.get("oncall_engineer") or {}
        phone = oncall.get("phone")

        if not self.sns_topic_arn:
            print(f"[AWS SNS stub] Would publish SMS to SNS_TOPIC_ARN (not set): "
                  f"CRITICAL {service} - {breach_metric} breached. On-call: {phone}")
        else:
            try:
                self._send_sns(incident)
            except Exception as e:
                print(f"[AWS SNS stub] Real publish failed ({e}) - falling back to stub log: "
                      f"CRITICAL {service} - {breach_metric} breached. On-call: {phone}")

    def _send_sns(self, incident: Dict) -> None:
        """
        Real implementation (once SNS_TOPIC_ARN is set):

        import boto3
        sns = boto3.client("sns", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        sns.publish(
            TopicArn=self.sns_topic_arn,
            Message=f"CRITICAL {incident['service']}: {incident['breach_metric']} breached "
                    f"at {incident['breach_value']}",
            Subject=f"[CRITICAL] {incident['service']}",
        )
        """
        import boto3
        sns = boto3.client("sns", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        sns.publish(
            TopicArn=self.sns_topic_arn,
            Message=f"CRITICAL {incident['service']}: {incident['breach_metric']} breached "
                    f"at {incident['breach_value']}",
            Subject=f"[CRITICAL] {incident['service']}",
        )
