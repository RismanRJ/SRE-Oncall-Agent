import os
from .base import LLMProvider
from .ollama import OllamaProvider


def get_provider() -> LLMProvider:
    """Factory function to get the configured LLM provider."""
    provider_name = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider_name == "ollama":
        return OllamaProvider()
    # TODO: Add bedrock, anthropic, etc. as they are implemented
    # elif provider_name == "anthropic":
    #     return AnthropicProvider()
    # elif provider_name == "bedrock":
    #     return BedrockProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
