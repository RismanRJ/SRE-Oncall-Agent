from abc import ABC, abstractmethod
from typing import Dict


class Notifier(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    def send_warning(self, incident: Dict) -> None:
        """Send a warning-severity notification. No @mention expected."""
        pass

    @abstractmethod
    def send_critical(self, incident: Dict) -> None:
        """Send a critical-severity notification. Should page/mention the on-call engineer."""
        pass
