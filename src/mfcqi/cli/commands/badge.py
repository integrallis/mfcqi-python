"""Badge generation command for MFCQI CLI."""

import json
from pathlib import Path

import click
from rich.console import Console

from mfcqi.calculator import MFCQICalculator
from mfcqi.cli.commands.badge_templates import MARKDOWN_TEMPLATE

console = Console()


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output path for badge SVG file",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["url", "json", "markdown"]),
    default="url",
    help="Output format for badge",
)
@click.option(
    "--style",
    type=click.Choice(["flat", "flat-square", "plastic", "for-the-badge"]),
    default="flat",
    help="Badge style (for URL format)",
)
def badge(
    path: Path,
    output: Path | None,
    format: str,
    style: str,
) -> None:
    """Generate a badge for MFCQI score.

    Examples:
        # Generate shields.io URL (static badge)
        mfcqi-py badge

        # Generate JSON for shields.io endpoint
        mfcqi-py badge -f json -o badge.json

        # Generate markdown with instructions
        mfcqi-py badge -f markdown
    """
    # Calculate MFCQI score
    with console.status("[bold cyan]Calculating MFCQI score..."):
        calculator = MFCQICalculator()
        score = calculator.calculate(path)  # Returns float directly

    # Determine color based on score
    if score >= 0.80:
        color = "brightgreen"
        rating = "excellent"
    elif score >= 0.60:
        color = "green"
        rating = "good"
    elif score >= 0.40:
        color = "yellow"
        rating = "fair"
    else:
        color = "red"
        rating = "poor"

    score_text = f"{score:.2f}"

    # Generate badge based on format
    if format == "url":
        # Generate static shields.io URL
        url = f"https://img.shields.io/badge/MFCQI-{score_text}-{color}.svg?style={style}"
        console.print(f"\n[bold]Badge URL:[/bold] {url}")
        console.print("\n[dim]Add to README.md:[/dim]")
        console.print(f"```markdown\n![MFCQI Score]({url})\n```")

    elif format == "json":
        # Generate JSON for shields.io endpoint
        badge_data = {
            "schemaVersion": 1,
            "label": "MFCQI",
            "message": f"{score_text} ({rating})",
            "color": color,
            "cacheSeconds": 3600,
        }

        if output:
            output.write_text(json.dumps(badge_data, indent=2))
            console.print(f"[green]✓[/green] Badge JSON saved to {output}")
            console.print("\n[dim]Use with shields.io endpoint:[/dim]")
            console.print("https://img.shields.io/endpoint?url=<YOUR_JSON_URL>")
        else:
            print(json.dumps(badge_data, indent=2))

    elif format == "markdown":
        url = f"https://img.shields.io/badge/MFCQI-{score_text}-{color}.svg?style={style}"
        output_text = MARKDOWN_TEMPLATE.format(
            url=url, score=score, rating=rating.capitalize(), path=path
        )
        console.print(output_text)
