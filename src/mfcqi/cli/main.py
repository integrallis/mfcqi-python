"""
Main CLI entry point for MFCQI (Benchmark Analysis Reporting Utility).
"""

import warnings

import click
from click import Context

from mfcqi import __version__
from mfcqi.cli.commands.analyze import analyze
from mfcqi.cli.commands.badge import badge
from mfcqi.cli.commands.config import config
from mfcqi.cli.commands.models import models

# Suppress unhelpful warnings from dependencies
warnings.filterwarnings("ignore", category=SyntaxWarning, module="<unknown>")
warnings.filterwarnings("ignore", message="invalid escape sequence")


@click.group()
@click.version_option(version=__version__, prog_name="mfcqi-py")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def cli(ctx: Context, debug: bool) -> None:
    """MFCQI - Benchmark Analysis Reporting Utility for code quality."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


# Add command groups
cli.add_command(analyze)
cli.add_command(badge)
cli.add_command(config)
cli.add_command(models)


def main() -> None:
    """Entry point for the CLI script."""
    cli()


if __name__ == "__main__":
    main()
