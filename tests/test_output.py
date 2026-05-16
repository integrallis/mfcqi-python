"""Tests for output formatting."""

from mfcqi.cli.utils.output import (
    format_analysis_output,
    format_json_output,
)


def test_format_json_output():
    """Test JSON output formatting."""
    analysis_result = {
        "mfcqi_score": 0.85,
        "metric_scores": {
            "cyclomatic_complexity": 0.90,
            "maintainability_index": 0.80,
        },
        "recommendations": ["Improve documentation", "Reduce complexity"],
        "model_used": "claude-3-5-sonnet",
        "diagnostics": [{"severity": "warning", "message": "Test warning"}],
        "metric_statuses": {
            "cyclomatic_complexity": {"status": "ok", "raw_value": 1.0},
            "maintainability_index": {"status": "failed", "error": "tool failed"},
        },
        "timestamp": "2025-01-01T00:00:00",
    }

    result = format_json_output(analysis_result)

    assert result["mfcqi_score"] == 0.85
    assert result["metrics"] == analysis_result["metric_scores"]
    assert result["recommendations"] == analysis_result["recommendations"]
    assert result["model_used"] == "claude-3-5-sonnet"
    assert result["diagnostics_count"] == 1
    assert result["metric_statuses"] == analysis_result["metric_statuses"]
    assert result["timestamp"] == "2025-01-01T00:00:00"
    assert "version" in result


def test_format_json_output_minimal():
    """Test JSON output with minimal data."""
    analysis_result = {}

    result = format_json_output(analysis_result)

    assert result["mfcqi_score"] == 0.0
    assert result["metrics"] == {}
    assert result["recommendations"] == []
    assert result["model_used"] == "metrics-only"
    assert result["diagnostics_count"] == 0
    assert "version" in result


def test_format_terminal_output():
    """Test terminal output formatting."""
    analysis_result = {
        "mfcqi_score": 0.85,
        "metric_scores": {
            "cyclomatic_complexity": 0.90,
            "maintainability_index": 0.80,
        },
        "recommendations": ["Improve documentation"],
        "model_used": "claude-3-5-sonnet",
    }

    result = format_analysis_output(analysis_result, "terminal")

    # Should return a Panel
    from rich.panel import Panel

    assert isinstance(result, Panel)


def test_format_terminal_output_no_recommendations():
    """Test terminal output without recommendations."""
    analysis_result = {
        "mfcqi_score": 0.75,
        "metric_scores": {
            "cyclomatic_complexity": 0.80,
        },
        "recommendations": [],
        "model_used": "metrics-only",
    }

    result = format_analysis_output(analysis_result, "terminal")

    from rich.panel import Panel

    assert isinstance(result, Panel)


def test_format_markdown_output():
    """Test markdown output formatting."""
    analysis_result = {
        "mfcqi_score": 0.85,
        "metric_scores": {
            "cyclomatic_complexity": 0.90,
            "maintainability_index": 0.80,
        },
        "recommendations": ["Improve documentation", "Reduce complexity"],
        "model_used": "claude-3-5-sonnet",
    }

    result = format_analysis_output(analysis_result, "markdown")

    assert isinstance(result, str)
    assert "MFCQI" in result or "Overall Score" in result
    assert "0.85" in result or "0.850" in result
    assert "Cyclomatic Complexity" in result or "cyclomatic" in result.lower()


def test_format_markdown_output_minimal():
    """Test markdown output with minimal data."""
    analysis_result = {
        "mfcqi_score": 0.50,
        "metric_scores": {},
        "recommendations": [],
        "model_used": "metrics-only",
    }

    result = format_analysis_output(analysis_result, "markdown")

    assert isinstance(result, str)
    assert "MFCQI" in result or "mfcqi" in result.lower()


def test_format_html_output():
    """Test HTML output formatting."""
    analysis_result = {
        "mfcqi_score": 0.85,
        "metric_scores": {
            "cyclomatic_complexity": 0.90,
            "maintainability_index": 0.80,
        },
        "recommendations": ["Improve documentation"],
        "model_used": "claude-3-5-sonnet",
    }

    result = format_analysis_output(analysis_result, "html")

    assert isinstance(result, str)
    assert "<html>" in result or "<div>" in result
    assert "0.85" in result or "0.850" in result


def test_format_html_output_minimal():
    """Test HTML output with minimal data."""
    analysis_result = {
        "mfcqi_score": 0.50,
        "metric_scores": {},
        "recommendations": [],
        "model_used": "metrics-only",
    }

    result = format_analysis_output(analysis_result, "html")

    assert isinstance(result, str)


def test_format_output_default_format():
    """Test that unknown format defaults to terminal."""
    analysis_result = {
        "mfcqi_score": 0.75,
        "metric_scores": {},
        "recommendations": [],
        "model_used": "metrics-only",
    }

    result = format_analysis_output(analysis_result, "unknown_format")

    from rich.panel import Panel

    assert isinstance(result, Panel)


def test_format_output_with_high_score():
    """Test output formatting with high MFCQI score."""
    analysis_result = {
        "mfcqi_score": 0.95,
        "metric_scores": {
            "cyclomatic_complexity": 0.98,
            "maintainability_index": 0.95,
            "documentation_coverage": 0.92,
        },
        "recommendations": [],
        "model_used": "metrics-only",
    }

    # Test all formats work with high score
    terminal_result = format_analysis_output(analysis_result, "terminal")
    markdown_result = format_analysis_output(analysis_result, "markdown")
    html_result = format_analysis_output(analysis_result, "html")

    from rich.panel import Panel

    assert isinstance(terminal_result, Panel)
    assert isinstance(markdown_result, str)
    assert isinstance(html_result, str)


def test_format_output_with_low_score():
    """Test output formatting with low MFCQI score."""
    analysis_result = {
        "mfcqi_score": 0.25,
        "metric_scores": {
            "cyclomatic_complexity": 0.30,
            "maintainability_index": 0.20,
        },
        "recommendations": [
            "Critical: Reduce cyclomatic complexity",
            "Urgent: Improve maintainability",
        ],
        "model_used": "claude-3-5-sonnet",
    }

    # Test all formats work with low score
    terminal_result = format_analysis_output(analysis_result, "terminal")
    markdown_result = format_analysis_output(analysis_result, "markdown")
    html_result = format_analysis_output(analysis_result, "html")

    from rich.panel import Panel

    assert isinstance(terminal_result, Panel)
    assert isinstance(markdown_result, str)
    assert isinstance(html_result, str)


def test_format_output_with_many_metrics():
    """Test output formatting with many metrics."""
    analysis_result = {
        "mfcqi_score": 0.70,
        "metric_scores": {
            "cyclomatic_complexity": 0.75,
            "cognitive_complexity": 0.72,
            "halstead_volume": 0.68,
            "maintainability_index": 0.71,
            "code_duplication": 0.80,
            "documentation_coverage": 0.65,
            "design_pattern_density": 0.60,
            "rfc": 0.73,
            "dit": 0.78,
            "mhf": 0.82,
        },
        "recommendations": [
            "Consider reducing cognitive complexity in main modules",
            "Improve documentation coverage for public APIs",
        ],
        "model_used": "gpt-4o",
    }

    terminal_result = format_analysis_output(analysis_result, "terminal")
    markdown_result = format_analysis_output(analysis_result, "markdown")
    html_result = format_analysis_output(analysis_result, "html")

    from rich.panel import Panel

    assert isinstance(terminal_result, Panel)
    assert isinstance(markdown_result, str)
    assert isinstance(html_result, str)
    # Check that metrics are included
    assert "cyclomatic" in markdown_result.lower() or "complexity" in markdown_result.lower()


def test_format_output_with_diagnostics():
    """Test output formatting with diagnostics included."""
    analysis_result = {
        "mfcqi_score": 0.65,
        "metric_scores": {
            "cyclomatic_complexity": 0.70,
        },
        "recommendations": ["Review complexity"],
        "model_used": "claude-3-haiku",
        "diagnostics": [
            {"severity": "error", "message": "Critical issue found", "file": "test.py", "line": 10},
            {
                "severity": "warning",
                "message": "Warning: potential issue",
                "file": "test.py",
                "line": 25,
            },
        ],
    }

    terminal_result = format_analysis_output(analysis_result, "terminal")
    markdown_result = format_analysis_output(analysis_result, "markdown")
    html_result = format_analysis_output(analysis_result, "html")

    from rich.panel import Panel

    assert isinstance(terminal_result, Panel)
    assert isinstance(markdown_result, str)
    assert isinstance(html_result, str)
