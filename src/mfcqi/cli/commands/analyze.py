"""
Analyze command implementation.
"""

from pathlib import Path

import click
from rich.console import Console

from mfcqi.calculator import MFCQICalculator
from mfcqi.cli.commands.analyze_helpers import (
    calculate_metrics,
    check_minimum_score,
    get_llm_recommendations,
    output_results,
    prepare_analysis_result,
)
from mfcqi.cli.utils.config_manager import ConfigManager
from mfcqi.cli.utils.llm_handler import LLMHandler

console = Console()


def _parse_analysis_paths(raw_paths: tuple[str, ...]) -> list[Path]:
    """Expand comma-separated CLI path arguments and validate each path."""
    paths: list[Path] = []
    for raw_path in raw_paths:
        for path_part in raw_path.split(","):
            path_text = path_part.strip()
            if path_text:
                path = Path(path_text)
                if not path.exists():
                    raise click.BadParameter(f"Path does not exist: {path_text}", param_hint="PATH")
                paths.append(path)

    if not paths:
        raise click.BadParameter("At least one path is required", param_hint="PATH")

    return paths


def _quality_gate_config_root(paths: list[Path]) -> Path:
    """Choose a stable location for resolving quality gate config files."""
    first_path = paths[0]
    return first_path if first_path.is_dir() else first_path.parent


@click.command()
@click.argument("paths", nargs=-1, type=str, required=True)
@click.option(
    "--model", help="Specific model to use (e.g., claude-3-5-sonnet, gpt-4o, ollama:codellama:7b)"
)
@click.option(
    "--provider", type=click.Choice(["anthropic", "openai", "ollama"]), help="LLM provider to use"
)
@click.option("--skip-llm", is_flag=True, help="Skip LLM analysis, metrics only")
@click.option("--metrics-only", is_flag=True, help="Alias for --skip-llm")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json", "html", "markdown", "sarif"]),
    default="terminal",
    help="Output format",
)
@click.option("--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--silent", is_flag=True, help="Silent mode for CI/CD (no prompts)")
@click.option("--min-score", type=float, help="Minimum MFCQI score (exit 1 if below)")
@click.option("--quality-gate", is_flag=True, help="Enable quality gates (exit 1 if gates fail)")
@click.option("--ollama-endpoint", default="http://localhost:11434", help="Ollama server endpoint")
@click.option(
    "--recommendations", type=int, default=50, help="Number of AI recommendations to generate"
)
@click.pass_context
def analyze(
    ctx: click.Context,
    paths: tuple[str, ...],
    model: str | None,
    provider: str | None,
    skip_llm: bool,
    metrics_only: bool,
    output_format: str,
    output: Path | None,
    silent: bool,
    min_score: float | None,
    quality_gate: bool,
    ollama_endpoint: str,
    recommendations: int,
) -> None:
    """Analyze codebase and generate quality recommendations."""

    # Automatically enable silent mode for JSON/SARIF output to avoid contaminating the output
    if output_format in ("json", "sarif"):
        silent = True

    # Determine if we should skip LLM
    # Skip by default UNLESS user explicitly requested via --model or --provider
    explicitly_requested_llm = model is not None or provider is not None
    should_skip_llm = (skip_llm or metrics_only) or not explicitly_requested_llm

    # Initialize components
    config_manager = ConfigManager()
    llm_handler = LLMHandler(config_manager, ollama_endpoint)

    calculator = MFCQICalculator()
    analysis_paths = _parse_analysis_paths(paths)
    analysis_target: Path | list[Path] = (
        analysis_paths[0] if len(analysis_paths) == 1 else analysis_paths
    )
    analysis_path_label = (
        str(analysis_paths[0]) if len(analysis_paths) == 1 else ", ".join(map(str, analysis_paths))
    )

    # Calculate base metrics
    try:
        detailed_metrics, tool_outputs, _elapsed = calculate_metrics(
            analysis_target,
            calculator,
            need_tool_outputs=not should_skip_llm,
            silent=silent,
        )
        cqi_score = detailed_metrics.get("mfcqi_score", 0.0)
    except Exception as e:
        console.print(f"❌ Error analyzing codebase: {e}", style="red")
        ctx.exit(1)

    # Prepare analysis result
    analysis_result = prepare_analysis_result(detailed_metrics)

    # LLM Analysis
    if not should_skip_llm:
        try:
            llm_result = get_llm_recommendations(
                analysis_path_label,
                detailed_metrics,
                tool_outputs,
                llm_handler,
                model,
                provider,
                recommendations,
                silent,
            )
            if llm_result:
                analysis_result.update(llm_result)
        except Exception as e:
            if not silent:
                console.print(f"⚠️  LLM analysis failed: {e}", style="yellow")
                console.print("📊 Continuing with metrics-only analysis...")
    elif not silent:
        console.print("📊 Analysis complete (metrics-only mode)")

    # Output results
    output_results(analysis_result, output_format, output, silent)

    # Check minimum score and exit if needed
    if not check_minimum_score(cqi_score, min_score, silent):
        ctx.exit(1)

    # Check quality gates if enabled
    if quality_gate:
        from mfcqi.quality_gates import (
            QualityGateConfig,
            QualityGateEvaluator,
            find_quality_gate_config,
        )

        # Find quality gate config
        config_path = find_quality_gate_config(_quality_gate_config_root(analysis_paths))
        if config_path:
            gate_config = QualityGateConfig.from_file(config_path)
        else:
            gate_config = QualityGateConfig.from_defaults()

        # Evaluate gates
        evaluator = QualityGateEvaluator(gate_config)
        gate_result = evaluator.evaluate(analysis_result)

        # Display results
        if not silent:
            from mfcqi.cli.utils.output import format_quality_gate_output

            format_quality_gate_output(gate_result, analysis_result)

        # Exit with failure if gates don't pass
        if not gate_result.passed:
            ctx.exit(1)
