"""
Configuration management for LLM analysis.
"""

import os
from typing import Any

from pydantic import BaseModel

DEFAULT_MODEL = "claude-sonnet-4-5"


def _resolve_litellm_model(model: str) -> str:
    """Return the model name annotated with the explicit LiteLLM provider prefix.

    LiteLLM no longer auto-detects the provider for a bare ``claude-*`` /
    ``gpt-*`` name and raises ``BadRequestError`` instead. This helper ensures
    every name handed to ``litellm.completion`` carries the right
    ``anthropic/`` / ``openai/`` / ``ollama/`` namespace.
    """
    if "/" in model:
        return model
    if model.startswith("ollama:"):
        return "ollama/" + model[len("ollama:") :]
    if model.startswith("claude"):
        return f"anthropic/{model}"
    if model.startswith(("gpt", "o1", "o3", "o4")):
        return f"openai/{model}"
    return model


class AnalysisConfig(BaseModel):
    """Configuration for LLM analysis."""

    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 8000
    timeout: int = 60
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        """Initialize configuration with environment variables."""
        # Load from environment if not provided
        if "model" not in kwargs:
            kwargs["model"] = os.getenv("CQI_LLM_MODEL", DEFAULT_MODEL)

        if "openai_api_key" not in kwargs:
            kwargs["openai_api_key"] = os.getenv("OPENAI_API_KEY")

        if "anthropic_api_key" not in kwargs:
            kwargs["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")

        super().__init__(**kwargs)

    def get_api_key_for_model(self, model: str) -> str | None:
        """Get appropriate API key for the given model.

        Accepts both bare names (``claude-sonnet-4-5``) and provider-prefixed
        names (``anthropic/claude-sonnet-4-5``).
        """
        bare = model.split("/", 1)[1] if "/" in model else model
        if bare.startswith("claude"):
            return self.anthropic_api_key
        if bare.startswith(("gpt", "o1", "o3", "o4")):
            return self.openai_api_key
        return None

    def validate_config(self) -> None:
        """Validate configuration."""
        api_key = self.get_api_key_for_model(self.model)
        if not api_key:
            raise ValueError(f"No API key found for model {self.model}")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "AnalysisConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)

    def get_supported_models(self) -> list[str]:
        """Get list of supported models."""
        return [
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-opus-4-7",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-5",
            "gpt-5-mini",
        ]

    @classmethod
    def from_environment(cls) -> "AnalysisConfig":
        """Create configuration from environment with model priority."""
        # Check available API keys and select appropriate model
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        # Priority: Claude > GPT-4o > default
        if anthropic_key:
            model = DEFAULT_MODEL
        elif openai_key:
            model = "gpt-4o"
        else:
            model = DEFAULT_MODEL

        return cls(model=model)

    def get_litellm_config(self) -> dict[str, Any]:
        """Get configuration dictionary for LiteLLM.

        The ``model`` field is normalized through :func:`_resolve_litellm_model`
        so it carries an explicit ``anthropic/``, ``openai/``, or ``ollama/``
        prefix — LiteLLM rejects bare model names with ``BadRequestError``.
        Includes the provider API key if available so callers do not need to
        rely on environment variables being set in the current shell session.
        """
        cfg: dict[str, Any] = {
            "model": _resolve_litellm_model(self.model),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }
        api_key = self.get_api_key_for_model(self.model)
        if api_key:
            cfg["api_key"] = api_key
        return cfg
