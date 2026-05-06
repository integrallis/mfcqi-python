"""
Integration tests for LLM Analysis Engine with real API calls.
Tests are skipped if API keys are not present.
"""

import os
import tempfile
from pathlib import Path

import pytest

from mfcqi.analysis.engine import AnalysisResult, LLMAnalysisEngine


# Helper function for API key detection
def has_api_key():
    """Check if any LLM API key is available."""
    return os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_HOST")


@pytest.mark.skipif(not has_api_key(), reason="No LLM API key available")
def test_analyze_codebase_simple():
    """Integration test: basic codebase analysis with real LLM."""
    engine = LLMAnalysisEngine()

    # Create test codebase
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text(
            "def complex_function():\n    if True:\n        if True:\n            return True"
        )

        # Use the actual method that exists
        cqi_data = {"mfcqi_score": 0.75, "cyclomatic_complexity": 0.5, "recommendation_count": 5}
        result = engine.analyze_with_cqi_data(str(tmpdir), cqi_data, recommendation_count=5)

        assert isinstance(result, AnalysisResult)
        assert result.mfcqi_score == 0.75
        assert len(result.recommendations) > 0


@pytest.mark.skipif(not has_api_key(), reason="No LLM API key available")
def test_analyze_with_existing_cqi_results():
    """Integration test: analysis with pre-calculated MFCQI results using real LLM."""
    engine = LLMAnalysisEngine()

    # Mock MFCQI results
    cqi_results = {
        "mfcqi_score": 0.45,
        "cyclomatic_complexity": 0.6,
        "test_coverage": 0.2,
        "documentation_coverage": 0.8,
    }

    result = engine.analyze_with_cqi_data("/fake/path", cqi_results)

    assert result.mfcqi_score == 0.45
    assert len(result.recommendations) > 0
    # Whatever model the configuration resolved to is the one we should be told about.
    assert result.model_used == engine.config.model


@pytest.mark.skipif(not has_api_key(), reason="No LLM API key available")
def test_error_handling_with_real_api():
    """Integration test: verify LLM handles edge cases properly."""
    engine = LLMAnalysisEngine()

    # Test with minimal/edge case data
    cqi_data = {"mfcqi_score": 0.0}

    result = engine.analyze_with_cqi_data("/test/path", cqi_data)

    # Should handle gracefully and return result
    assert isinstance(result, AnalysisResult)
    assert result.mfcqi_score == 0.0
