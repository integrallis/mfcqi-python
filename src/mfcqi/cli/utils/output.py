"""
Beautiful output formatting with Rich animations.
"""

from typing import Any, Union

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import track
from rich.table import Table
from rich.text import Text

from mfcqi import __version__

console = Console()


def format_analysis_output(
    analysis_result: dict[str, Any], output_format: str = "terminal"
) -> str | Panel:
    """Format analysis results for different output formats."""

    if output_format == "terminal":
        return _format_terminal_output(analysis_result)
    elif output_format == "markdown":
        return _format_markdown_output(analysis_result)
    elif output_format == "html":
        return _format_html_output(analysis_result)
    else:
        return _format_terminal_output(analysis_result)


def format_json_output(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """Format analysis results as JSON."""
    return {
        "mfcqi_score": analysis_result.get("mfcqi_score", 0.0),
        "metrics": analysis_result.get("metric_scores", {}),
        "recommendations": analysis_result.get("recommendations", []),
        "model_used": analysis_result.get("model_used", "metrics-only"),
        "metric_statuses": analysis_result.get("metric_statuses", {}),
        "diagnostics_count": len(analysis_result.get("diagnostics", [])),
        "timestamp": analysis_result.get("timestamp"),
        "version": __version__,
    }


def format_sarif_output(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """Format analysis results as SARIF 2.1.0 JSON."""
    mfcqi_score = analysis_result.get("mfcqi_score", 0.0)
    metric_scores = analysis_result.get("metric_scores", {})
    recommendations = analysis_result.get("recommendations", [])

    # Create SARIF structure
    sarif = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "MFCQI",
                        "version": __version__,
                        "informationUri": "https://github.com/bsbodden/mfcqi",
                        "semanticVersion": __version__,
                        "rules": _create_sarif_rules(metric_scores),
                    }
                },
                "results": _create_sarif_results(mfcqi_score, metric_scores, recommendations),
            }
        ],
    }

    return sarif


def _create_sarif_rules(metric_scores: dict[str, Any]) -> list[dict[str, Any]]:
    """Create SARIF rules for each metric."""
    rules = []

    # Rule descriptions for each metric
    rule_descriptions = {
        "cyclomatic_complexity": {
            "name": "Cyclomatic Complexity",
            "shortDescription": "Measures code complexity based on decision points",
            "fullDescription": "Cyclomatic complexity measures the number of linearly independent paths through code. Lower is better.",
        },
        "cognitive_complexity": {
            "name": "Cognitive Complexity",
            "shortDescription": "Measures code understandability",
            "fullDescription": "Cognitive complexity measures how difficult code is to understand, focusing on nested structures and control flow.",
        },
        "maintainability_index": {
            "name": "Maintainability Index",
            "shortDescription": "Composite maintainability metric",
            "fullDescription": "Maintainability Index combines Halstead Volume, Cyclomatic Complexity, and lines of code into a single metric.",
        },
        "halstead_volume": {
            "name": "Halstead Volume",
            "shortDescription": "Measures program vocabulary and length",
            "fullDescription": "Halstead Volume measures the size of the implementation based on the number of operations and operands.",
        },
        "code_duplication": {
            "name": "Code Duplication",
            "shortDescription": "Detects duplicate code blocks",
            "fullDescription": "Code duplication measures the percentage of code that is duplicated across the codebase.",
        },
        "documentation_coverage": {
            "name": "Documentation Coverage",
            "shortDescription": "Measures documentation completeness",
            "fullDescription": "Documentation coverage measures the percentage of code that has proper documentation.",
        },
        "security": {
            "name": "Security Score",
            "shortDescription": "Security vulnerability assessment",
            "fullDescription": "Security score based on static analysis findings from Bandit, secrets detection, and dependency scanning.",
        },
        "design_pattern_density": {
            "name": "Design Pattern Density",
            "shortDescription": "Measures design pattern usage",
            "fullDescription": "Design pattern density measures the presence and proper usage of common design patterns.",
        },
    }

    for metric_name in metric_scores:
        if metric_name == "mfcqi_score":
            continue

        desc = rule_descriptions.get(
            metric_name,
            {
                "name": metric_name.replace("_", " ").title(),
                "shortDescription": f"Measures {metric_name.replace('_', ' ')}",
                "fullDescription": f"Code quality metric: {metric_name.replace('_', ' ')}",
            },
        )

        rules.append(
            {
                "id": metric_name,
                "name": desc["name"],
                "shortDescription": {"text": desc["shortDescription"]},
                "fullDescription": {"text": desc["fullDescription"]},
                "helpUri": "https://github.com/bsbodden/mfcqi",
                "properties": {"tags": ["code-quality", "metrics"]},
            }
        )

    # Add overall MFCQI rule
    rules.append(
        {
            "id": "mfcqi_score",
            "name": "MFCQI Overall Score",
            "shortDescription": {"text": "Multi-Factor Code Quality Index"},
            "fullDescription": {
                "text": "Composite code quality score combining multiple evidence-based metrics using geometric mean."
            },
            "helpUri": "https://github.com/bsbodden/mfcqi",
            "properties": {"tags": ["code-quality", "composite"]},
        }
    )

    return rules


def _create_sarif_results(
    mfcqi_score: float, metric_scores: dict[str, Any], recommendations: list[str]
) -> list[dict[str, Any]]:
    """Create SARIF results from metrics and recommendations."""
    results = []

    # Add overall MFCQI result
    results.append(
        {
            "ruleId": "mfcqi_score",
            "level": _score_to_sarif_level(mfcqi_score),
            "message": {
                "text": f"Overall code quality score: {mfcqi_score:.3f}/1.0 ({_score_to_rating(mfcqi_score)})"
            },
            "properties": {"score": mfcqi_score},
        }
    )

    # Add results for each metric
    for metric_name, score in metric_scores.items():
        if metric_name == "mfcqi_score":
            continue

        if isinstance(score, (int, float)):
            results.append(
                {
                    "ruleId": metric_name,
                    "level": _score_to_sarif_level(score),
                    "message": {
                        "text": f"{_get_metric_display_name(metric_name)}: {score:.2f} ({_get_metric_rating(score)})"
                    },
                    "properties": {"score": score},
                }
            )

    # Add recommendations as informational results
    for i, recommendation in enumerate(recommendations, 1):
        results.append(
            {
                "ruleId": "mfcqi_score",
                "level": "note",
                "message": {"text": f"Recommendation {i}: {recommendation.strip()}"},
                "properties": {"type": "recommendation"},
            }
        )

    return results


def _score_to_sarif_level(score: float) -> str:
    """Convert MFCQI score to SARIF level."""
    if score >= 0.8:
        return "none"  # Excellent
    elif score >= 0.6:
        return "note"  # Good
    elif score >= 0.4:
        return "warning"  # Needs work
    else:
        return "error"  # Poor


def _score_to_rating(score: float) -> str:
    """Convert score to text rating."""
    if score >= 0.8:
        return "Excellent"
    elif score >= 0.6:
        return "Good"
    elif score >= 0.4:
        return "Needs Work"
    else:
        return "Poor"


def _format_terminal_output(analysis_result: dict[str, Any]) -> Panel:
    """Format beautiful terminal output with Rich."""
    elements: list[Union[Text, Table]] = []

    # Add MFCQI score display
    _add_score_display(analysis_result, elements)

    # Add metrics breakdown
    _add_metrics_breakdown(analysis_result, elements)

    # Add recommendations or metrics-only message
    _add_recommendations_section(analysis_result, elements)

    # Create and return panel
    content_group = Group(*elements)
    return Panel(
        content_group, title="✨ MFCQI Analysis Results", border_style="bright_blue", padding=(1, 2)
    )


def _add_score_display(analysis_result: dict[str, Any], elements: list[Union[Text, Table]]) -> None:
    """Add MFCQI score display to elements."""
    mfcqi_score = analysis_result.get("mfcqi_score", 0.0)
    score_color = _get_score_color(mfcqi_score)
    score_emoji = _get_score_emoji(mfcqi_score)
    elements.append(
        Text(f"{score_emoji} MFCQI Score: {mfcqi_score:.3f}", style=f"bold {score_color}")
    )


def _add_metrics_breakdown(
    analysis_result: dict[str, Any], elements: list[Union[Text, Table]]
) -> None:
    """Add metrics breakdown table to elements."""
    metrics = analysis_result.get("metric_scores", {})
    if not metrics:
        return

    elements.append(Text())  # Empty line
    elements.append(Text("📊 Metrics Breakdown:", style="bold cyan"))

    # Create metrics table
    metrics_table = Table(show_header=True, header_style="bold blue", box=None, padding=(0, 1))
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Score", justify="right")
    metrics_table.add_column("Rating", justify="center")

    for metric_name, score in metrics.items():
        if metric_name != "mfcqi_score":
            _add_metric_row(metrics_table, metric_name, score)

    elements.append(metrics_table)


def _add_metric_row(table: Table, metric_name: str, score: Any) -> None:
    """Add a single metric row to the table."""
    display_name = _get_metric_display_name(metric_name)
    score_str = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)
    rating = _get_metric_rating(score) if isinstance(score, (int, float)) else "N/A"
    table.add_row(display_name, score_str, rating)


def _add_recommendations_section(
    analysis_result: dict[str, Any], elements: list[Union[Text, Table]]
) -> None:
    """Add recommendations section or metrics-only message."""
    recommendations = analysis_result.get("recommendations", [])
    model_used = analysis_result.get("model_used", "metrics-only")

    if recommendations and model_used != "metrics-only":
        _add_ai_recommendations(recommendations, model_used, analysis_result, elements)
    elif model_used == "metrics-only":
        _add_metrics_only_message(elements)


def _add_ai_recommendations(
    recommendations: list[str],
    model_used: str,
    analysis_result: dict[str, Any],
    elements: list[Union[Text, Table]],
) -> None:
    """Add AI recommendations section."""
    elements.append(Text())  # Empty line
    elements.append(Text(f"🤖 AI Recommendations ({model_used}):", style="bold green"))

    for i, rec in enumerate(recommendations, 1):
        formatted_rec = _format_single_recommendation(rec, i)
        elements.append(formatted_rec)

    # Show model info for local processing
    if model_used.startswith("ollama:"):
        elements.append(Text())  # Empty line
        elements.append(
            Text(f"⚡ Local processing: {analysis_result.get('processing_time', 'N/A')}")
        )


def _format_single_recommendation(rec: str, index: int) -> Text:
    """Format a single recommendation with priority indicators."""
    # Clean up recommendation text
    clean_rec = rec.strip()
    if clean_rec.startswith(f"{index}."):
        clean_rec = clean_rec[2:].strip()
    elif any(clean_rec.startswith(prefix) for prefix in ["•", "-", "*"]):
        clean_rec = clean_rec[1:].strip()

    # Determine priority emoji
    priority_emoji = _get_priority_emoji(clean_rec)
    clean_rec = _remove_priority_markers(clean_rec)

    # Return formatted text
    if clean_rec:
        return Text(f"  {index}. {priority_emoji} {clean_rec}")
    else:
        return Text(f"  {index}. {priority_emoji} {rec}")


def _get_priority_emoji(text: str) -> str:
    """Get priority emoji based on text content."""
    if "[HIGH]" in text or "[Priority: HIGH]" in text:
        return "🔴"
    elif "[MEDIUM]" in text or "[Priority: MEDIUM]" in text:
        return "🟡"
    elif "[LOW]" in text or "[Priority: LOW]" in text:
        return "🟢"
    else:
        return "🟡"  # Default to medium


def _remove_priority_markers(text: str) -> str:
    """Remove priority markers from text."""
    markers = [
        "[HIGH]",
        "[Priority: HIGH]",
        "[MEDIUM]",
        "[Priority: MEDIUM]",
        "[LOW]",
        "[Priority: LOW]",
    ]
    for marker in markers:
        text = text.replace(marker, "")
    return text.strip()


def _add_metrics_only_message(elements: list[Union[Text, Table]]) -> None:
    """Add metrics-only mode message."""
    elements.append(Text())  # Empty line
    elements.append(Text("i  Analysis complete (metrics-only mode)", style="dim"))
    elements.append(Text("💡 To get AI recommendations, run: mfcqi config setup", style="cyan"))


def _format_markdown_output(analysis_result: dict[str, Any]) -> str:
    """Format as Markdown."""
    mfcqi_score = analysis_result.get("mfcqi_score", 0.0)
    recommendations = analysis_result.get("recommendations", [])
    model_used = analysis_result.get("model_used", "metrics-only")

    lines = [
        "# MFCQI Analysis Report",
        "",
        f"**Overall Score:** {mfcqi_score:.2f}/1.0 {_get_score_emoji(mfcqi_score)}",
        "",
        "## Metrics Breakdown",
        "",
    ]

    # Add metrics table
    metrics = analysis_result.get("metric_scores", {})
    if metrics:
        lines.extend(["| Metric | Score | Rating |", "|--------|-------|--------|"])

        for metric_name, score in metrics.items():
            if metric_name != "mfcqi_score":
                display_name = _get_metric_display_name(metric_name)
                score_str = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)
                rating = _get_metric_rating(score) if isinstance(score, (int, float)) else "N/A"
                lines.append(f"| {display_name} | {score_str} | {rating} |")

    # Add recommendations
    if recommendations:
        lines.extend(["", f"## AI Recommendations ({model_used})", ""])

        for i, rec in enumerate(recommendations, 1):
            clean_rec = rec.strip()
            if clean_rec.startswith(f"{i}."):
                clean_rec = clean_rec[2:].strip()

            lines.append(f"{i}. {clean_rec}")

    return "\n".join(lines)


def _format_html_output(analysis_result: dict[str, Any]) -> str:
    """Format as HTML."""
    mfcqi_score = analysis_result.get("mfcqi_score", 0.0)
    recommendations = analysis_result.get("recommendations", [])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>MFCQI Analysis Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .score {{ font-size: 24px; font-weight: bold; color: {_get_score_color_hex(mfcqi_score)}; }}
            .metric {{ margin: 10px 0; }}
            .recommendations {{ margin-top: 20px; }}
            .recommendation {{ margin: 8px 0; padding: 8px; background: #f5f5f5; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>🔍 MFCQI Analysis Report</h1>
        <div class="score">Overall Score: {mfcqi_score:.2f}/1.0 {_get_score_emoji(mfcqi_score)}</div>

        <h2>📊 Metrics</h2>
    """

    # Add metrics
    metrics = analysis_result.get("metric_scores", {})
    for metric_name, score in metrics.items():
        if metric_name != "cqi_score":
            display_name = metric_name.replace("_", " ").title()
            score_str = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)
            html += f'<div class="metric"><strong>{display_name}:</strong> {score_str}</div>'

    # Add recommendations
    if recommendations:
        html += '<h2>🤖 AI Recommendations</h2><div class="recommendations">'
        for i, rec in enumerate(recommendations, 1):
            html += f'<div class="recommendation">{i}. {rec}</div>'
        html += "</div>"

    html += "</body></html>"
    return html


def _get_score_color(score: float) -> str:
    """Get Rich color for score."""
    if score >= 0.8:
        return "green"
    elif score >= 0.6:
        return "yellow"
    else:
        return "red"


def _get_score_color_hex(score: float) -> str:
    """Get hex color for score."""
    if score >= 0.8:
        return "#00aa00"
    elif score >= 0.6:
        return "#ffaa00"
    else:
        return "#aa0000"


def _get_score_emoji(score: float) -> str:
    """Get emoji for score."""
    if score >= 0.9:
        return "🏆"
    elif score >= 0.8:
        return "⭐"
    elif score >= 0.7:
        return "✅"
    elif score >= 0.6:
        return "⚠️"
    else:
        return "❌"


def _get_metric_display_name(metric_name: str) -> str:
    """Get human-friendly display name for metrics."""
    metric_names = {
        "cyclomatic_complexity": "Cyclomatic Complexity",
        "cognitive_complexity": "Cognitive Complexity",
        "halstead_volume": "Halstead Volume",
        "maintainability_index": "Maintainability Index",
        "code_duplication": "Code Duplication",
        "documentation_coverage": "Documentation Coverage",
        "security": "Security Score",
        "design_pattern_density": "Design Pattern Density",
        # OO Metrics with full names
        "rfc": "RFC (Response for Class)",
        "dit": "DIT (Depth of Inheritance)",
        "mhf": "MHF (Method Hiding Factor)",
        "coupling": "Coupling Between Objects",
        "cohesion": "Class Cohesion",
    }
    return metric_names.get(metric_name, metric_name.replace("_", " ").title())


def _get_metric_rating(score: float) -> str:
    """Get text rating for metric score."""
    if score >= 0.8:
        return "⭐ Excellent"
    elif score >= 0.6:
        return "✅ Good"
    elif score >= 0.4:
        return "⚠️ Needs Work"
    else:
        return "❌ Poor"


def show_startup_banner() -> None:
    """Show beautiful startup banner."""
    banner = """
╔═══════════════════════════════════════╗
║          🔍 MFCQI Analysis Tool         ║
║     Code Quality Index with AI        ║
╚═══════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")


def show_analysis_progress(total_steps: int = 5) -> None:
    """Show analysis progress with animations."""
    steps = [
        "🔍 Scanning codebase structure",
        "📊 Calculating complexity metrics",
        "📝 Checking documentation",
        "🎯 Computing MFCQI score",
    ]

    for step in track(steps[:total_steps], description="[cyan]Analyzing..."):
        # Simulate processing time
        import time

        time.sleep(0.3)
        console.print(f"  ✅ {step}", style="dim green")


def format_quality_gate_output(gate_result: Any, analysis_result: dict[str, Any]) -> None:
    """
    Format and display quality gate results.

    Args:
        gate_result: QualityGateResult object
        analysis_result: Analysis result dict with scores
    """
    from rich.panel import Panel
    from rich.text import Text

    # Create header
    if gate_result.passed:
        header = Text("Quality Gate: PASSED ✅", style="bold green")
        border_style = "green"
    else:
        header = Text("Quality Gate: FAILED ❌", style="bold red")
        border_style = "red"

    lines = [header, Text()]

    # Overall score check
    mfcqi_score = analysis_result.get("mfcqi_score", 0.0)
    if gate_result.overall_result:
        lines.append(Text(f"✅ Overall MFCQI Score: {mfcqi_score:.3f}", style="green"))
    else:
        lines.append(Text(f"❌ Overall MFCQI Score: {mfcqi_score:.3f}", style="red"))

    # Metric checks
    if gate_result.metric_results:
        lines.append(Text())
        lines.append(Text("Individual Metrics:", style="bold cyan"))

        for metric_result in gate_result.metric_results:
            metric_name = _get_metric_display_name(metric_result["metric"])
            actual = metric_result["actual"]
            threshold = metric_result["threshold"]
            passed = metric_result["passed"]

            if passed:
                lines.append(
                    Text(
                        f"  ✅ {metric_name}: {actual:.2f} (threshold: {threshold:.2f})",
                        style="green",
                    )
                )
            else:
                lines.append(
                    Text(
                        f"  ❌ {metric_name}: {actual:.2f} (threshold: {threshold:.2f})",
                        style="red",
                    )
                )

    # Summary
    lines.append(Text())
    lines.append(
        Text(
            f"Summary: {gate_result.passed_count} passed, {gate_result.failed_count} failed",
            style="bold",
        )
    )

    # Display panel
    from rich.console import Group

    panel = Panel(Group(*lines), border_style=border_style, padding=(1, 2))
    console.print(panel)
