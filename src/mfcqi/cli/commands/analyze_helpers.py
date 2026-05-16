"""Helper functions for the analyze command."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from mfcqi.calculator import MFCQICalculator
from mfcqi.cli.utils.llm_handler import LLMHandler
from mfcqi.cli.utils.output import (
    format_analysis_output,
    format_json_output,
    format_sarif_output,
)

console = Console()


def calculate_metrics(
    path: Path | Sequence[Path],
    calculator: MFCQICalculator,
    need_tool_outputs: bool,
    silent: bool,
) -> tuple[dict[str, Any], dict[str, Any], float]:
    """Calculate metrics with optional tool outputs.

    Returns:
        Tuple of (detailed_metrics, tool_outputs, elapsed_time)
    """
    import time

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        disable=silent,
    ) as progress:
        task = progress.add_task("🔍 Analyzing codebase...", total=None)
        start_time = time.time()

        paths = [path] if isinstance(path, Path) else list(path)

        if len(paths) > 1:
            detailed_metrics, tool_outputs = _calculate_metrics_for_multiple_paths(
                paths, calculator, need_tool_outputs
            )
        elif need_tool_outputs:
            progress.update(
                task,
                description="📊 Calculating metrics...",
            )
            detailed_data = calculator.get_detailed_metrics_with_tool_outputs(paths[0])
            detailed_metrics = detailed_data.get("metrics", {})
            detailed_metrics["mfcqi_score"] = detailed_data.get("mfcqi_score", 0.0)
            tool_outputs = detailed_data.get("tool_outputs", {})
        else:
            progress.update(task, description="📊 Calculating metrics...")
            detailed_metrics = calculator.get_detailed_metrics(paths[0])
            tool_outputs = {}

        elapsed = time.time() - start_time
        cqi_score = detailed_metrics.get("mfcqi_score", 0.0)

        if not silent:
            progress.update(
                task,
                description=f"✅ Metrics calculated (MFCQI Score: {cqi_score:.2f}) in {elapsed:.1f}s",
            )

    return detailed_metrics, tool_outputs, elapsed


def _calculate_metrics_for_multiple_paths(
    paths: Sequence[Path],
    calculator: MFCQICalculator,
    need_tool_outputs: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Calculate metrics for multiple paths and average shared numeric results."""
    metric_sets: list[dict[str, Any]] = []
    merged_tool_outputs: dict[str, Any] = {}

    for current_path in paths:
        if need_tool_outputs:
            detailed_data = calculator.get_detailed_metrics_with_tool_outputs(current_path)
            metrics = detailed_data.get("metrics", {})
            metrics["mfcqi_score"] = detailed_data.get("mfcqi_score", 0.0)
            _merge_tool_outputs(merged_tool_outputs, detailed_data.get("tool_outputs", {}))
        else:
            metrics = calculator.get_detailed_metrics(current_path)
        metric_sets.append(metrics)

    return _average_metric_sets(metric_sets), merged_tool_outputs


def _average_metric_sets(metric_sets: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Average numeric metric values across multiple analysis results."""
    averaged: dict[str, Any] = {}
    metric_names = {name for metrics in metric_sets for name in metrics}

    for metric_name in metric_names:
        values = [
            metrics[metric_name]
            for metrics in metric_sets
            if isinstance(metrics.get(metric_name), (int, float))
        ]
        if values:
            averaged[metric_name] = sum(values) / len(values)

    return averaged


def _merge_tool_outputs(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge tool outputs collected from separate path analyses."""
    for key, value in source.items():
        if isinstance(value, list):
            target.setdefault(key, []).extend(value)
        elif isinstance(value, (int, float)):
            target[key] = max(target.get(key, value), value)
        else:
            target[key] = value


def get_llm_recommendations(
    path: str,
    detailed_metrics: dict[str, Any],
    tool_outputs: dict[str, Any],
    llm_handler: LLMHandler,
    model: str | None,
    provider: str | None,
    recommendations: int,
    silent: bool,
) -> dict[str, Any] | None:
    """Get LLM recommendations if available.

    Returns:
        Dictionary with recommendations or None
    """
    # Determine model to use
    selected_model = llm_handler.select_model(model, provider, silent)

    if not selected_model:
        if not silent:
            console.print("i  Analysis complete (metrics-only mode - no LLM configured)")
            console.print("💡 To get AI recommendations, run: mfcqi config setup")
        return None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        disable=silent,
    ) as progress:
        task = progress.add_task("✨ Generating recommendations...", total=None)

        # Get LLM analysis
        llm_result = llm_handler.analyze_with_llm(
            path, detailed_metrics, selected_model, recommendations, tool_outputs
        )

        if llm_result:
            llm_result["model_used"] = selected_model
            if not silent:
                progress.update(task, description="✅ AI recommendations generated")

        return llm_result


def prepare_analysis_result(detailed_metrics: dict[str, Any]) -> dict[str, Any]:
    """Prepare the initial analysis result structure."""
    cqi_score = detailed_metrics.get("mfcqi_score", 0.0)

    return {
        "mfcqi_score": cqi_score,
        "metric_scores": {k: v for k, v in detailed_metrics.items() if k != "mfcqi_score"},
        "diagnostics": [],
        "recommendations": [],
        "model_used": "metrics-only",
    }


def output_results(
    analysis_result: dict[str, Any],
    output_format: str,
    output: Path | None,
    silent: bool,
) -> None:
    """Format and output analysis results."""
    # Format data
    from typing import Union

    from rich.panel import Panel

    output_data: Union[dict[str, Any], str, Panel]
    if output_format == "json":
        output_data = format_json_output(analysis_result)
    elif output_format == "sarif":
        output_data = format_sarif_output(analysis_result)
    else:
        output_data = format_analysis_output(analysis_result, output_format)

    # Write to file or console
    if output:
        if isinstance(output_data, (str, Panel)):
            output.write_text(str(output_data))
        else:
            output.write_text(json.dumps(output_data, indent=2))
        if not silent:
            console.print(f"📄 Report saved to: {output}")
    else:
        if output_format in ("json", "sarif") and isinstance(output_data, dict):
            click.echo(json.dumps(output_data, indent=2))
        else:
            console.print(output_data)


def check_minimum_score(cqi_score: float, min_score: float | None, silent: bool) -> bool:
    """Check if score meets minimum requirement."""
    if min_score is not None and cqi_score < min_score:
        if not silent:
            console.print(f"❌ MFCQI score {cqi_score:.2f} below minimum {min_score}", style="red")
        return False
    return True
