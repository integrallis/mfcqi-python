"""
Configuration manager with secure key storage.
"""

import logging
import os
from pathlib import Path
from typing import Any

import toml

logger = logging.getLogger(__name__)

# Check if keyring should be disabled (e.g., for testing)
if os.getenv("MFCQI_DISABLE_KEYRING"):
    KEYRING_AVAILABLE = False
else:
    try:
        import keyring

        KEYRING_AVAILABLE = True
    except ImportError:
        KEYRING_AVAILABLE = False


class ConfigManager:
    """Manages MFCQI configuration with secure API key storage."""

    def __init__(self, config_path: Path | None = None):
        """Initialize configuration manager."""
        self.config_path = config_path or self._get_default_config_path()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load_config()

    def _get_default_config_path(self) -> Path:
        """Get default configuration file path."""

        # Try to get home directory, fallback to temp if it fails (Windows CI issue)
        try:
            config_dir = Path.home() / ".mfcqi"
        except (RuntimeError, KeyError):
            # Fallback to temp directory if home is not available
            import tempfile

            config_dir = Path(tempfile.gettempdir()) / ".mfcqi"

        return config_dir / "config.toml"

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                return toml.load(self.config_path)
            except Exception:
                return self._default_config()
        return self._default_config()

    def _default_config(self) -> dict[str, Any]:
        """Get default configuration."""
        return {
            "preferences": {
                "prompt_for_llm": True,
                "default_skip_llm": False,
                "show_cost_estimates": True,
            },
            "llm": {
                "default_provider": "anthropic",
                "preferred_model": "claude-3-5-sonnet-20241022",
                "max_cost_per_analysis": 0.05,
            },
            "providers": {
                "anthropic": {"models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]},
                "openai": {"models": ["gpt-4o", "gpt-4o-mini"]},
                "ollama": {
                    "endpoint": "http://localhost:11434",
                    "timeout": 120,
                    "available_models": [],
                    "recommended_models": ["codellama:7b", "llama3.1:8b", "qwen2.5-coder:7b"],
                },
            },
        }

    def save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_path, "w") as f:
            toml.dump(self._config, f)

    def get_config(self) -> dict[str, Any]:
        """Get full configuration."""
        return self._config.copy()

    def set_api_key(self, provider: str, api_key: str) -> None:
        """Securely store API key."""
        if KEYRING_AVAILABLE:
            keyring.set_password("mfcqi", f"{provider}_api_key", api_key)
        else:
            # Fallback to environment variable suggestion
            env_var = f"{provider.upper()}_API_KEY"
            raise RuntimeError(
                f"Keyring not available. Please set environment variable: export {env_var}=your_key_here"
            )

    def get_api_key(self, provider: str) -> str | None:
        """Get API key securely."""
        # Try keyring first
        if KEYRING_AVAILABLE:
            try:
                key = keyring.get_password("mfcqi", f"{provider}_api_key")
                if key:
                    return key
            except Exception as e:
                # Log keyring errors for debugging (graceful degradation intended)
                logger.debug(
                    f"Keyring error for {provider}: {e}. Falling back to environment variable."
                )

        # Fallback to environment variables
        env_var = f"{provider.upper()}_API_KEY"
        return os.getenv(env_var)

    def has_api_key(self, provider: str) -> bool:
        """Check if API key is available."""
        return self.get_api_key(provider) is not None

    def remove_api_key(self, provider: str) -> None:
        """Remove API key."""
        if KEYRING_AVAILABLE:
            import contextlib

            with contextlib.suppress(Exception):
                keyring.delete_password("mfcqi", f"{provider}_api_key")

    def get_models(self, provider: str) -> list[str]:
        """Get available models for provider."""
        result = self._config.get("providers", {}).get(provider, {}).get("models", [])
        return list(result) if result else []

    def set_ollama_config(self, endpoint: str, models: list[str]) -> None:
        """Set Ollama configuration."""
        if "providers" not in self._config:
            self._config["providers"] = {}
        if "ollama" not in self._config["providers"]:
            self._config["providers"]["ollama"] = {}

        self._config["providers"]["ollama"].update(
            {"endpoint": endpoint, "available_models": models}
        )
        self.save_config()

    def get_ollama_endpoint(self) -> str:
        """Get Ollama endpoint."""
        result = (
            self._config.get("providers", {})
            .get("ollama", {})
            .get("endpoint", "http://localhost:11434")
        )
        return str(result)

    def should_prompt_for_llm(self) -> bool:
        """Check if should prompt for LLM usage."""
        result = self._config.get("preferences", {}).get("prompt_for_llm", True)
        return bool(result)

    def get_preferred_model(self) -> str:
        """Get preferred model."""
        result = self._config.get("llm", {}).get("preferred_model", "claude-3-5-sonnet-20241022")
        return str(result)

    def get_max_cost(self) -> float:
        """Get maximum cost per analysis."""
        result = self._config.get("llm", {}).get("max_cost_per_analysis", 0.05)
        return float(result)
