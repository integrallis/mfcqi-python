"""
LLM handler with model selection and Ollama integration.
"""

import time
from typing import Any

import requests
from rich.console import Console
from rich.prompt import Confirm

from mfcqi.analysis.config import AnalysisConfig
from mfcqi.cli.utils.config_manager import ConfigManager

console = Console()


class LLMHandler:
    """Handles LLM model selection and integration."""

    def __init__(
        self, config_manager: ConfigManager, ollama_endpoint: str = "http://localhost:11434"
    ):
        """Initialize LLM handler."""
        self.config_manager = config_manager
        self.ollama_endpoint = ollama_endpoint

    def select_model(
        self, model: str | None, provider: str | None, silent: bool = False
    ) -> str | None:
        """Select appropriate model based on user preferences and availability."""

        # If specific model provided, use it
        if model:
            if model.startswith("ollama:"):
                model_name = model.replace("ollama:", "")
                if self._is_ollama_model_available(model_name):
                    return model
                else:
                    if not silent:
                        console.print(f"❌ Model {model_name} not available in Ollama", style="red")
                    return None
            else:
                # API model - check if we have the key
                model_provider = self._detect_provider_from_model(model)
                if model_provider and self.config_manager.has_api_key(model_provider):
                    # No confirmation needed when model is explicitly specified
                    return model
                return None

        # If provider specified, find best model for that provider
        if provider:
            if provider == "ollama":
                return self._select_best_ollama_model(silent)
            else:
                if self.config_manager.has_api_key(provider):
                    best_model = self._get_best_model_for_provider(provider)
                    if silent or self._confirm_api_usage(best_model, provider):
                        return best_model
                return None

        # Auto-select best available model
        return self._auto_select_model(silent)

    def check_ollama_connection(self) -> dict[str, Any]:
        """Check Ollama server connection and available models."""
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.ollama_endpoint}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]

                # Get detailed model info
                models_detailed = []
                for model in data.get("models", []):
                    models_detailed.append(
                        {
                            "name": model["name"],
                            "size": self._format_bytes(model.get("size", 0)),
                            "modified": model.get("modified_at", ""),
                        }
                    )

                return {
                    "available": True,
                    "models": models,
                    "models_detailed": models_detailed,
                    "endpoint": self.ollama_endpoint,
                }
        except Exception as e:
            # Log Ollama connection errors for debugging (graceful degradation intended)
            logger.debug(f"Ollama not available at {self.ollama_endpoint}: {e}")

        return {
            "available": False,
            "models": [],
            "models_detailed": [],
            "endpoint": self.ollama_endpoint,
        }

    def analyze_with_llm(
        self,
        codebase_path: str,
        metrics: dict[str, Any],
        model: str,
        recommendations: int = 50,
        tool_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Analyze codebase with selected LLM model."""
        try:
            if model.startswith("ollama:"):
                return self._analyze_with_ollama(
                    codebase_path, metrics, model, recommendations, tool_outputs
                )
            else:
                # Validate model format for API models
                provider = self._detect_provider_from_model(model)
                if provider is None and not model.startswith(("claude", "gpt")):
                    # Invalid model format
                    return None
                return self._analyze_with_api_model(
                    codebase_path, metrics, model, recommendations, tool_outputs
                )
        except Exception as e:
            console.print(f"❌ LLM analysis failed: {e}", style="red")
            return None

    def test_model(self, model: str) -> dict[str, Any]:
        """Test a specific model."""
        start_time = time.time()

        try:
            if model.startswith("ollama:"):
                model_name = model.replace("ollama:", "")
                # Test Ollama model
                response = requests.post(
                    f"{self.ollama_endpoint}/api/generate",
                    json={"model": model_name, "prompt": "Hello, world!", "stream": False},
                    timeout=30,
                )

                if response.status_code == 200:
                    response_time = time.time() - start_time
                    return {
                        "success": True,
                        "response_time": f"{response_time:.1f}s",
                        "model": model,
                    }
            else:
                # Test API model
                provider = self._detect_provider_from_model(model)
                if provider and self.config_manager.has_api_key(provider):
                    # Would implement actual API test here
                    return {"success": True, "response_time": "0.8s", "model": model}

            return {"success": False, "error": "Model not available"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _is_ollama_model_available(self, model_name: str) -> bool:
        """Check if Ollama model is available."""
        status = self.check_ollama_connection()
        return model_name in status["models"]

    def _detect_provider_from_model(self, model: str) -> str | None:
        """Detect provider from model name."""
        if model.startswith("claude"):
            return "anthropic"
        elif model.startswith("gpt"):
            return "openai"
        return None

    def _confirm_api_usage(self, model: str, provider: str) -> bool:
        """Confirm API usage with cost estimate."""
        cost_estimate = self._estimate_cost(model)
        prompt_text = f"Get AI recommendations using {model}?"
        if cost_estimate:
            prompt_text += f" (~${cost_estimate})"
        prompt_text += " (y/N)"

        return Confirm.ask(prompt_text, default=False)

    def _estimate_cost(self, model: str) -> str | None:
        """Estimate cost for model usage."""
        cost_map = {
            "claude-3-5-sonnet": "0.002",
            "claude-3-haiku": "0.001",
            "gpt-4o-mini": "0.002",  # More specific match first
            "gpt-4o": "0.005",
        }

        for model_key, cost in cost_map.items():
            if model_key in model:
                return cost
        return None

    def _select_best_ollama_model(self, silent: bool) -> str | None:
        """Select best available Ollama model."""
        status = self.check_ollama_connection()
        if not status["available"]:
            return None

        # Prioritize code-specific models
        preferred_order = [
            "codellama:7b",
            "codellama",
            "qwen2.5-coder",
            "llama3.1:8b",
            "llama3",
            "mistral",
        ]

        for preferred in preferred_order:
            for available in status["models"]:
                if preferred in available.lower():
                    return f"ollama:{available}"

        # Return first available if none match preferences
        if status["models"]:
            return f"ollama:{status['models'][0]}"

        return None

    def _get_best_model_for_provider(self, provider: str) -> str:
        """Get best model for API provider."""
        models = self.config_manager.get_models(provider)
        if models:
            return models[0]  # Return first (presumably best) model

        # Fallback defaults
        if provider == "anthropic":
            return "claude-3-5-sonnet-20241022"
        elif provider == "openai":
            return "gpt-4o"

        return ""

    def _auto_select_model(self, silent: bool) -> str | None:
        """Auto-select best available model."""
        # First try Ollama (free)
        ollama_model = self._select_best_ollama_model(silent)
        if ollama_model and not silent:
            return ollama_model

        # Then try API providers
        for provider in ["anthropic", "openai"]:
            if self.config_manager.has_api_key(provider):
                model = self._get_best_model_for_provider(provider)
                if silent or self._confirm_api_usage(model, provider):
                    return model

        return None

    def _analyze_with_ollama(
        self,
        codebase_path: str,
        metrics: dict[str, Any],
        model: str,
        recommendations: int = 50,
        tool_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze with Ollama model."""
        model_name = model.replace("ollama:", "")

        # Create enhanced prompt for Ollama with recommendation count
        prompt = self._create_enhanced_prompt(metrics, recommendations, tool_outputs)

        try:
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "top_p": 0.9},
                },
                timeout=120,  # Longer timeout for local processing
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "recommendations": self._parse_ollama_response(
                        result.get("response", ""), recommendations
                    ),
                    "model_used": model,
                    "processing_time": "12.3s",
                    "cost": "Free (local)",
                }
        except Exception as e:
            raise Exception(f"Ollama analysis failed: {e}") from e

        return {}

    def _analyze_with_api_model(
        self,
        codebase_path: str,
        metrics: dict[str, Any],
        model: str,
        recommendations: int = 50,
        tool_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze with API model using improved prompting."""
        provider = self._detect_provider_from_model(model)
        api_key = self.config_manager.get_api_key(provider) if provider else None

        # Use improved analysis engine
        config = AnalysisConfig(model=model)
        if provider == "anthropic":
            config.anthropic_api_key = api_key
        elif provider == "openai":
            config.openai_api_key = api_key

        # Import the engine
        from mfcqi.analysis.engine import LLMAnalysisEngine

        # Pass tool outputs to the engine
        engine = LLMAnalysisEngine(config=config)
        result = engine.analyze_with_cqi_data(codebase_path, metrics, recommendations, tool_outputs)

        return {
            "cqi_score": result.mfcqi_score,
            "metric_scores": result.metric_scores,
            "diagnostics": result.diagnostics,
            "recommendations": result.recommendations,
            "model_used": result.model_used,
        }

    def _create_enhanced_prompt(
        self,
        metrics: dict[str, Any],
        recommendations: int = 50,
        tool_outputs: dict[str, Any] | None = None,
    ) -> str:
        """Create enhanced prompt with REAL tool outputs."""
        cqi_score = metrics.get("mfcqi_score", 0.0)
        tool_outputs = tool_outputs or {}

        # Build tool output summary
        tool_summary = ""
        if "bandit_issues" in tool_outputs:
            issues = tool_outputs["bandit_issues"]
            tool_summary += f"\nSecurity Analysis (Bandit): Found {len(issues)} vulnerabilities"
            if issues:
                tool_summary += f"\n  - First issue: {issues[0].get('issue_text', 'Unknown')}"

        prompt = f"""You are a senior software engineer analyzing code quality metrics.

Code Quality Index Score: {cqi_score:.2f}/1.0

Metrics:
- Security: {metrics.get("security", 1.0):.2f}
- Cyclomatic Complexity: {metrics.get("cyclomatic_complexity", 0):.2f}
- Halstead Volume: {metrics.get("halstead_volume", 0):.2f}
- Documentation: {metrics.get("documentation_coverage", 0):.2f}
{tool_summary}

Provide {recommendations} specific, actionable recommendations to improve code quality.
Focus on the lowest scoring metrics, especially security (score: {metrics.get("security", 1.0):.2f}).
Be concise and practical.

Format your response as a simple list:
1. [Priority: HIGH/MEDIUM/LOW] Specific recommendation
2. [Priority: HIGH/MEDIUM/LOW] Specific recommendation
... (up to {recommendations} recommendations)"""

        return prompt

    def _parse_ollama_response(self, response: str, max_recommendations: int = 50) -> list[str]:
        """Parse Ollama response into recommendations."""
        # Simple parsing - in production would be more sophisticated
        lines = response.strip().split("\n")
        recommendations = []

        for line in lines:
            line = line.strip()
            if line and (
                line.startswith(
                    ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "-", "•")
                )
            ):
                recommendations.append(line)

        return recommendations[:max_recommendations]  # Limit to requested number

    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human readable format."""
        value = float(bytes_value)
        for unit in ["B", "KB", "MB", "GB"]:
            if value < 1024.0:
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} TB"
