"""Model management commands for the Ollama HTTP API.

Subcommands:

* ``list`` — tabulate installed Ollama models.
* ``pull`` — stream a model download via ``POST /api/pull`` and print
  status / progress lines.
* ``benchmark`` — measure cold-start and warm-response latency using
  LiteLLM's ``ollama/<name>`` completion routing.
* ``recommend`` — pattern-match installed models or print download
  guidance.
* ``test`` — run a single test completion against a named model.
"""

import builtins
import json
import time
from collections.abc import Iterable

import click
import litellm
import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from mfcqi.cli.utils.config_manager import ConfigManager
from mfcqi.cli.utils.llm_handler import LLMHandler

console = Console()


@click.group()
def models() -> None:
    """Model management for local and remote LLMs."""
    pass


@models.command()
@click.option("--endpoint", default="http://localhost:11434", help="Ollama endpoint")
def list(endpoint: str) -> None:
    """List available models with beautiful formatting."""
    llm_handler = LLMHandler(ConfigManager(), endpoint)

    with console.status("[cyan]🔍 Discovering models...", spinner="dots"):
        time.sleep(0.5)  # Brief pause for visual effect
        status = llm_handler.check_ollama_connection()

    if not status["available"]:
        console.print(Panel("❌ Ollama not available at " + endpoint, style="red"))
        console.print("\n💡 To install Ollama:")
        console.print("   • Visit: https://ollama.ai")
        console.print("   • Run: ollama serve")
        return

    # Create beautiful models table
    table = Table(
        title=f"🏠 Ollama Models ({endpoint})", show_header=True, header_style="bold cyan"
    )
    table.add_column("Model", style="bright_white", no_wrap=True)
    table.add_column("Size", style="dim", justify="right")
    table.add_column("Status", style="green")
    table.add_column("MFCQI Rating", style="yellow")

    model_ratings = {
        "codellama": "⭐⭐⭐⭐⭐ BEST for code",
        "code": "⭐⭐⭐⭐⭐ BEST for code",
        "llama3": "⭐⭐⭐⭐☆ Good general",
        "mistral": "⭐⭐⭐⭐☆ Good general",
        "qwen": "⭐⭐⭐⭐☆ Good for code",
        "mixtral": "⭐⭐⭐⭐⭐ High quality",
    }

    for model_info in status["models_detailed"]:
        model_name = model_info["name"]
        size = model_info.get("size", "Unknown")

        # Determine rating
        rating = "⭐⭐⭐☆☆ General"
        for key, value in model_ratings.items():
            if key in model_name.lower():
                rating = value
                break

        table.add_row(model_name, size, "✅ Downloaded", rating)

    console.print(table)

    # Show recommendations
    recommended = [
        m for m in status["models"] if any(rec in m.lower() for rec in ["codellama", "code"])
    ]
    if recommended:
        console.print(f"\n📋 [bold green]Recommended for MFCQI:[/bold green] {recommended[0]}")


@models.command()
@click.argument("model_name")
@click.option("--endpoint", default="http://localhost:11434", help="Ollama endpoint")
@click.pass_context
def pull(ctx: click.Context, model_name: str, endpoint: str) -> None:
    """Download an Ollama model.

    Streams ``POST {endpoint}/api/pull`` and prints each status transition,
    plus per-line ``MB / MB (P%)`` progress when ``completed`` / ``total``
    fields are present. Stream-level errors are reported on stderr and the
    process exits with code 2.

    Direct ``requests`` is used here rather than LiteLLM because model
    download is an Ollama management endpoint, not a completion call.
    """
    try:
        response = requests.post(
            f"{endpoint}/api/pull",
            json={"name": model_name, "stream": True},
            stream=True,
            timeout=(10, 3600),  # 10s connect, 1h read for large models
        )
    except requests.RequestException as exc:
        click.echo(f"Failed to reach Ollama at {endpoint}: {exc}", err=True)
        ctx.exit(2)

    if not response.ok:
        click.echo(f"Ollama returned HTTP {response.status_code} for /api/pull", err=True)
        ctx.exit(2)

    exit_code = _stream_pull_status(response.iter_lines(decode_unicode=True))
    if exit_code != 0:
        ctx.exit(exit_code)


def _stream_pull_status(lines: Iterable[str]) -> int:
    """Consume the JSONL stream from /api/pull, returning the exit code."""
    last_status = None
    for raw in lines:
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            click.echo(f"Failed to parse pull response line: {raw!r}", err=True)
            return 2

        if "error" in payload:
            click.echo(f"Ollama error: {payload['error']}", err=True)
            return 2

        status = payload.get("status", "")
        if status != last_status:
            click.echo(status)
            last_status = status
        elif "completed" in payload and "total" in payload:
            completed = int(payload["completed"])
            total = int(payload["total"])
            if total > 0:
                pct = (100.0 * completed) / total
                click.echo(
                    f"  {status} — {completed // (1024 * 1024)} / {total // (1024 * 1024)} MB ({pct:.1f}%)"
                )
    return 0


@models.command()
@click.argument("model_name", required=False)
@click.option("--endpoint", default="http://localhost:11434", help="Ollama endpoint")
@click.option(
    "--prompt",
    default="Write one short sentence about Python.",
    help="Benchmark prompt sent to the model.",
)
@click.option(
    "--warm-runs",
    default=3,
    type=int,
    help="Number of warm runs to average after the cold-start measurement.",
)
@click.pass_context
def benchmark(
    ctx: click.Context, model_name: str, endpoint: str, prompt: str, warm_runs: int
) -> None:
    """Benchmark model latency.

    Issues one cold-start completion followed by ``--warm-runs`` warm
    completions through LiteLLM's ``ollama/<name>`` routing and prints the
    measured wall-clock latency for each phase.
    """
    llm_handler = LLMHandler(ConfigManager(), endpoint)
    status = llm_handler.check_ollama_connection()

    if not status["available"]:
        console.print("❌ Ollama not available", style="red")
        ctx.exit(2)

    targets = [model_name] if model_name else status["models"]
    if not targets:
        console.print(
            "📋 No models installed. Install one with: ollama pull codellama:7b", style="yellow"
        )
        return

    for target in targets:
        console.print(f"\n🧪 [bold cyan]Benchmarking {target}[/bold cyan]")
        try:
            cold = _measure_completion_latency(endpoint, target, prompt)
        except Exception as exc:  # LiteLLM raises various provider-specific exceptions.
            console.print(f"  ❌ Cold-start request failed: {exc}", style="red")
            continue

        warm_latencies: builtins.list[float] = []
        for _ in range(max(0, warm_runs)):
            try:
                warm_latencies.append(_measure_completion_latency(endpoint, target, prompt))
            except Exception as exc:
                console.print(f"  ⚠️  Warm request failed: {exc}", style="yellow")

        results_table = Table(title=f"Benchmark Results: {target}", show_header=True)
        results_table.add_column("Phase", style="cyan")
        results_table.add_column("Latency", style="bright_white")
        results_table.add_row("❄️  Cold start", f"{cold:.2f}s")
        if warm_latencies:
            avg = sum(warm_latencies) / len(warm_latencies)
            best = min(warm_latencies)
            worst = max(warm_latencies)
            results_table.add_row(
                f"🔥 Warm x {len(warm_latencies)}",
                f"avg {avg:.2f}s   min {best:.2f}s   max {worst:.2f}s",
            )
        console.print(results_table)


def _measure_completion_latency(endpoint: str, model: str, prompt: str) -> float:
    """Issue a single completion through LiteLLM and return its wall-clock latency.

    Routes via the ``ollama/<model>`` namespace so the same code path serves
    every Ollama model the user has pulled. The Ollama HTTP endpoint is
    passed through the LiteLLM ``api_base`` parameter.
    """
    # LiteLLM accepts either "ollama/" or already-prefixed names; normalize to the prefix form.
    routed = model if model.startswith(("ollama/", "ollama:")) else f"ollama/{model}"
    routed = routed.replace("ollama:", "ollama/")
    started = time.monotonic()
    response = litellm.completion(
        model=routed,
        messages=[{"role": "user", "content": prompt}],
        api_base=endpoint,
        stream=False,
    )
    # Touch the response payload so the elapsed time reflects model output, not just dispatch.
    _ = response.choices[0].message.content
    return time.monotonic() - started


@models.command()
@click.option("--endpoint", default="http://localhost:11434", help="Ollama endpoint")
def recommend(endpoint: str) -> None:
    """Show animated recommendations for best models."""
    llm_handler = LLMHandler(ConfigManager(), endpoint)
    _run_animation_sequence()
    status = llm_handler.check_ollama_connection()

    console.print("\n🎯 [bold green]MFCQI Model Recommendations[/bold green]")

    if status["available"] and status["models"]:
        _display_available_models(status["models"])
    else:
        _display_download_recommendations()


def _run_animation_sequence() -> None:
    """Run the animated analysis sequence."""
    with Live(Spinner("dots", text="🤖 Analyzing your setup..."), console=console):
        time.sleep(2)
    with Live(Spinner("arrow3", text="📊 Evaluating model performance..."), console=console):
        time.sleep(1.5)


def _display_available_models(models: builtins.list[str]) -> None:
    """Display recommendations for available models."""
    recommendations = _build_recommendations(models)
    if recommendations:
        console.print(Panel("\n".join(recommendations), title="Your Available Models"))
    else:
        console.print("📋 No specialized models found. Consider: ollama pull codellama:7b")


def _build_recommendations(models: builtins.list[str]) -> builtins.list[str]:
    """Build recommendation list from available models."""
    recommendations = []

    # Find code-specific models
    code_model = _find_model_by_patterns(models, ["codellama", "code"])
    if code_model:
        recommendations.append(
            f"🥇 [bold green]PRIMARY:[/bold green] {code_model} - Optimized for code analysis"
        )

    # Find general models
    general_model = _find_model_by_patterns(models, ["llama3", "mistral"])
    if general_model:
        recommendations.append(
            f"🥈 [yellow]ALTERNATIVE:[/yellow] {general_model} - Good general purpose"
        )

    # Find high-end models
    high_end_model = _find_model_by_patterns(models, ["mixtral", "20b"])
    if high_end_model:
        recommendations.append(f"🥉 [blue]HIGH-END:[/blue] {high_end_model} - Best quality, slower")

    return recommendations


def _find_model_by_patterns(models: builtins.list[str], patterns: builtins.list[str]) -> str | None:
    """Find first model matching any of the patterns."""
    for model in models:
        if any(pattern in model.lower() for pattern in patterns):
            return model
    return None


def _display_download_recommendations() -> None:
    """Display recommendations for downloading models."""
    console.print(
        Panel(
            "📥 [bold cyan]Recommended Downloads:[/bold cyan]\n\n"
            "• [green]codellama:7b[/green] - Best for code analysis (3.8GB)\n"
            "• [yellow]llama3.1:8b[/yellow] - Good general purpose (4.7GB)\n"
            "• [blue]qwen2.5-coder:7b[/blue] - Alternative code specialist (4.1GB)\n\n"
            "💡 Start with: [cyan]ollama pull codellama:7b[/cyan]",
            title="Install Ollama Models",
        )
    )


@models.command()
@click.argument("model_name")
@click.option("--endpoint", default="http://localhost:11434", help="Ollama endpoint")
def test(model_name: str, endpoint: str) -> None:
    """Test a specific model with real diagnostics."""
    from mfcqi.cli.utils.config_manager import ConfigManager
    from mfcqi.cli.utils.llm_handler import LLMHandler

    console.print(f"🔬 [bold cyan]Testing {model_name}[/bold cyan]\n")

    config_manager = ConfigManager()
    llm_handler = LLMHandler(config_manager, endpoint)

    # Normalize model name for Ollama
    if not model_name.startswith("ollama:"):
        # Check if it's an Ollama model
        ollama_info = llm_handler.check_ollama_connection()
        if ollama_info["available"] and model_name in ollama_info["models"]:
            model_name = f"ollama:{model_name}"

    # Test the model using the existing test_model method
    with console.status("[cyan]🔍 Testing model...", spinner="dots"):
        try:
            result = llm_handler.test_model(model_name)

            if result["success"]:
                console.print("✅ Model is functional", style="green")
                console.print(f"⚡ Response time: {result['response_time']}", style="cyan")

                # Categorize performance
                response_time = float(result["response_time"].rstrip("s"))
                if response_time < 2.0:
                    console.print("📊 Performance: Excellent (< 2s)", style="green")
                elif response_time < 5.0:
                    console.print("📊 Performance: Good (2-5s)", style="yellow")
                else:
                    console.print("📊 Performance: Slow (> 5s)", style="red")

                console.print(
                    f"\n✅ [bold green]{model_name} is ready for MFCQI analysis[/bold green]"
                )
            else:
                console.print(
                    f"❌ Model test failed: {result.get('error', 'Unknown error')}", style="red"
                )

        except Exception as e:
            console.print(f"❌ Test failed: {e}", style="red")
            # Try to provide helpful error messages
            if "ollama" in model_name.lower():
                ollama_info = llm_handler.check_ollama_connection()
                if not ollama_info["available"]:
                    console.print(
                        "\n💡 Tip: Make sure Ollama is running with: ollama serve", style="yellow"
                    )
                elif ollama_info["models"]:
                    console.print(
                        f"\nAvailable models: {', '.join(ollama_info['models'])}", style="cyan"
                    )
                else:
                    console.print(
                        "\n💡 Tip: Pull a model with: ollama pull <model-name>", style="yellow"
                    )
