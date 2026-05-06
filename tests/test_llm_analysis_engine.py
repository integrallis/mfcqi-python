"""
Test for LLM Analysis Engine - following strict TDD.
This test MUST fail first because the code doesn't exist yet.
"""

import json
from unittest.mock import Mock, patch


def test_llm_analysis_engine_exists():
    """RED: Test that LLMAnalysisEngine class exists."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    assert LLMAnalysisEngine is not None


def test_llm_analysis_engine_initialization():
    """RED: Test that LLMAnalysisEngine can be initialized."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine()
    assert engine is not None


def test_llm_analysis_engine_default_model():
    """RED: Test that LLMAnalysisEngine has default model."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine()
    assert engine.model_name == "claude-sonnet-4-5"


def test_llm_analysis_engine_custom_model():
    """RED: Test that LLMAnalysisEngine accepts custom model."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine(model="gpt-4o")
    assert engine.model_name == "gpt-4o"


def test_analysis_result_model_exists():
    """RED: Test that AnalysisResult model exists."""
    from mfcqi.analysis.engine import AnalysisResult

    assert AnalysisResult is not None


def test_analysis_result_creation():
    """RED: Test AnalysisResult model creation."""
    from mfcqi.analysis.diagnostics import DiagnosticsCollection, create_diagnostic
    from mfcqi.analysis.engine import AnalysisResult

    diagnostic = create_diagnostic("test.py", 10, "Test message")
    collection = DiagnosticsCollection(file_path="test.py", diagnostics=[diagnostic])

    result = AnalysisResult(
        mfcqi_score=0.75,
        metric_scores={"complexity": 0.8},
        diagnostics=[collection],
        recommendations=["Improve test coverage"],
        model_used="claude-sonnet-4-5",
    )

    assert result.mfcqi_score == 0.75
    assert result.metric_scores["complexity"] == 0.8
    assert len(result.diagnostics) == 1
    assert len(result.recommendations) == 1
    assert result.model_used == "claude-sonnet-4-5"


# Note: Tests that require real API calls have been moved to tests/integration/test_llm_analysis.py
# These will be skipped automatically when API keys are not present


def test_llm_request_method_exists():
    """RED: Test that _make_llm_request method exists."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine()
    assert hasattr(engine, "_make_llm_request")


@patch("litellm.completion")
def test_make_llm_request_integration(mock_completion):
    """Test LiteLLM integration."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    # Mock LiteLLM response - now returns markdown string
    mock_completion.return_value.choices = [
        Mock(
            message=Mock(
                content="""---
## [WARNING] Reduce Complexity
**Description:** High complexity detected
---"""
            )
        )
    ]

    engine = LLMAnalysisEngine()

    prompt = "Analyze this code quality data"
    result = engine._make_llm_request(prompt)

    assert isinstance(result, str)
    assert "WARNING" in result


def test_parse_recommendations():
    """Test parsing of LLM markdown recommendations."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine()

    # Test markdown response parsing
    response = """---
## [WARNING] Reduce Complexity
**Description:** The function has high cyclomatic complexity
---
## [ERROR] Add Tests
**Description:** No test coverage for this module
---"""

    max_recommendations = 5
    recommendations = engine._parse_recommendations(response, max_recommendations)

    assert len(recommendations) == 2
    assert "[WARNING]" in recommendations[0]
    assert "[ERROR]" in recommendations[1]


def test_jinja2_template_rendering():
    """Test that Jinja2 templates are properly loaded and used."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine()

    # Verify templates are loaded
    assert engine.main_template is not None
    assert engine.fallback_template is not None

    # Test that templates can be rendered
    context = {
        "codebase_path": "/test/path",
        "total_files": 10,
        "total_lines": 1000,
        "mfcqi_score": 0.42,
        "metrics": {"test_coverage": 0.0},
        "critical_metrics": [],
        "tool_outputs": {},
        "recommendation_count": 5,
    }

    # Should render without errors
    prompt = engine.main_template.render(**context)
    assert isinstance(prompt, str)
    assert "0.42" in prompt


def test_analysis_result_json_serialization():
    """RED: Test AnalysisResult JSON serialization."""
    from mfcqi.analysis.diagnostics import DiagnosticsCollection, create_diagnostic
    from mfcqi.analysis.engine import AnalysisResult

    diagnostic = create_diagnostic("test.py", 10, "Test message")
    collection = DiagnosticsCollection(file_path="test.py", diagnostics=[diagnostic])

    result = AnalysisResult(
        mfcqi_score=0.75,
        metric_scores={"complexity": 0.8},
        diagnostics=[collection],
        recommendations=["Improve test coverage"],
        model_used="claude-sonnet-4-5",
    )

    json_str = result.model_dump_json()
    parsed = json.loads(json_str)

    assert parsed["mfcqi_score"] == 0.75
    assert parsed["metric_scores"]["complexity"] == 0.8
    assert len(parsed["diagnostics"]) == 1
    assert len(parsed["recommendations"]) == 1


# Note: Error handling test moved to integration tests since it requires engine initialization


def test_model_configuration_from_env():
    """RED: Test model configuration from environment variables."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    with patch.dict("os.environ", {"CQI_LLM_MODEL": "gpt-4o"}):
        engine = LLMAnalysisEngine()
        assert engine.model_name == "gpt-4o"


def test_config_initialization():
    """Test that engine properly initializes with config."""
    from mfcqi.analysis.config import AnalysisConfig
    from mfcqi.analysis.engine import LLMAnalysisEngine

    # Test with custom config
    config = AnalysisConfig()
    engine = LLMAnalysisEngine(config=config)
    assert engine.model_name == config.model  # Should use config's model

    # Test without config
    engine2 = LLMAnalysisEngine()
    assert engine2.model_name is not None  # Should have a default model


# Removed test_recommendation_model_exists - Recommendation model no longer exists in refactored engine


# Removed test_recommendation_creation - Recommendation model no longer exists in refactored engine
def test_recommendations_are_strings():
    """Test that recommendations are returned as formatted strings."""
    from mfcqi.analysis.engine import LLMAnalysisEngine

    engine = LLMAnalysisEngine()

    # Parse a sample response
    response = """---
## [HIGH] Fix Security Issue
**Description:** SQL injection vulnerability detected
---"""

    max_recommendations = 5
    recommendations = engine._parse_recommendations(response, max_recommendations)

    assert len(recommendations) == 1
    assert isinstance(recommendations[0], str)
    assert recommendations[0].startswith("[HIGH]")
