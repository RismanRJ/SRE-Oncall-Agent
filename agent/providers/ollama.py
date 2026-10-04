import os
import httpx
from .base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama2")

    def complete(self, prompt: str, system: str = None, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        try:
            resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=120.0)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except httpx.HTTPError as e:
            raise Exception(f"Ollama request failed: {str(e)}")
