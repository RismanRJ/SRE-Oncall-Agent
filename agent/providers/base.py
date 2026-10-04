from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str, system: str = None, json_mode: bool = False) -> str:
        """
        Run a single completion against the model.

        Args:
            prompt: User prompt text.
            system: Optional system prompt.
            json_mode: If True, instruct the model to return JSON only.

        Returns:
            Raw text response from the model.
        """
        pass
