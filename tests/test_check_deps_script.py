"""Tests for the dependency conflict checker script."""

from pathlib import Path


def test_check_deps_script_does_not_use_shell_true():
    """The dependency checker should not invoke network calls through a shell."""
    source = Path("scripts/check_deps.py").read_text(encoding="utf-8")

    assert "shell=True" not in source
