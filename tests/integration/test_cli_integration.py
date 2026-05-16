"""
Integration tests for CLI with different LLM providers.
"""

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from mfcqi.cli.main import cli


class TestCLIIntegration:
    """Test CLI integration with different configurations."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create a simple test codebase
        test_file = self.temp_dir / "test_code.py"
        test_file.write_text("""
def simple_function():
    '''A simple function.'''
    return 42

def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x + y + z
            else:
                return x + y
        else:
            return x
    else:
        return 0
""")

    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "MFCQI - Benchmark Analysis Reporting Utility" in result.output

    def test_analyze_help(self):
        """Test analyze command help."""
        result = self.runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze codebase" in result.output

    def test_config_help(self):
        """Test config command help."""
        result = self.runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "Configuration management" in result.output

    def test_models_help(self):
        """Test models command help."""
        result = self.runner.invoke(cli, ["models", "--help"])
        assert result.exit_code == 0
        assert "Model management" in result.output

    def test_analyze_metrics_only(self):
        """Test analyze command with metrics-only mode."""
        result = self.runner.invoke(cli, ["analyze", str(self.temp_dir), "--skip-llm"])
        assert result.exit_code == 0
        # Should complete without requiring API keys

    def test_analyze_json_output(self):
        """Test analyze command with JSON output."""
        result = self.runner.invoke(
            cli, ["analyze", str(self.temp_dir), "--skip-llm", "--format", "json"]
        )
        assert result.exit_code == 0
        # Should produce valid JSON output

    def test_analyze_comma_separated_paths_json_output(self):
        """Test analyze supports comma-separated path arguments."""
        first_file = self.temp_dir / "first.py"
        second_file = self.temp_dir / "second.py"
        first_file.write_text("def first():\n    return 1\n")
        second_file.write_text("def second():\n    return 2\n")

        result = self.runner.invoke(
            cli,
            [
                "analyze",
                f"{first_file},{second_file}",
                "--skip-llm",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "mfcqi_score" in output
        assert "metrics" in output

    def test_analyze_space_separated_paths_json_output(self):
        """Test analyze supports multiple path arguments."""
        first_file = self.temp_dir / "first.py"
        second_file = self.temp_dir / "second.py"
        first_file.write_text("def first():\n    return 1\n")
        second_file.write_text("def second():\n    return 2\n")

        result = self.runner.invoke(
            cli,
            [
                "analyze",
                str(first_file),
                str(second_file),
                "--skip-llm",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "mfcqi_score" in output
        assert "metrics" in output

    def test_analyze_with_output_file(self):
        """Test analyze command with output file."""
        output_file = self.temp_dir / "report.json"
        result = self.runner.invoke(
            cli,
            [
                "analyze",
                str(self.temp_dir),
                "--skip-llm",
                "--format",
                "json",
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()

    def test_analyze_with_min_score_pass(self):
        """Test analyze command with min-score that passes."""
        result = self.runner.invoke(
            cli,
            ["analyze", str(self.temp_dir), "--skip-llm", "--min-score", "0.1"],
        )
        assert result.exit_code == 0

    def test_analyze_with_min_score_fail(self):
        """Test analyze command with min-score that fails."""
        result = self.runner.invoke(
            cli,
            ["analyze", str(self.temp_dir), "--skip-llm", "--min-score", "0.99"],
        )
        assert result.exit_code == 1

    def test_analyze_nonexistent_path(self):
        """Test analyze command with nonexistent path."""
        result = self.runner.invoke(
            cli,
            ["analyze", "/nonexistent/path/that/does/not/exist", "--skip-llm"],
        )
        # Click validates path existence and returns exit code 2
        assert result.exit_code == 2
        assert "does not exist" in result.output.lower() or "error" in result.output.lower()

    def test_config_status(self):
        """Test config status command."""
        result = self.runner.invoke(cli, ["config", "status"])
        assert result.exit_code == 0
        # Should show configuration status

    def test_models_list(self):
        """Test models list command."""
        result = self.runner.invoke(cli, ["models", "list"])
        # Should handle gracefully even if Ollama not available
        assert result.exit_code == 0

    # Real behavior tests for analyze.py coverage (minimal mocking)

    def test_analyze_with_invalid_python_syntax(self):
        """Test analyze handles real syntax errors in Python files."""
        # Create file with actual syntax error
        broken_code = """
def incomplete_function(
    # Missing closing parenthesis and body
"""
        (self.temp_dir / "broken.py").write_text(broken_code)

        result = self.runner.invoke(
            cli,
            ["analyze", str(self.temp_dir), "--skip-llm"],
        )
        # Should handle syntax errors gracefully
        # May succeed with partial analysis or fail gracefully
        assert result.exit_code in [0, 1]

    def test_analyze_empty_directory_no_python_files(self):
        """Test analyze with directory containing no Python files."""
        # Create directory with only non-Python files
        (self.temp_dir / "README.md").write_text("# Documentation")
        (self.temp_dir / "data.json").write_text('{"key": "value"}')

        result = self.runner.invoke(
            cli,
            ["analyze", str(self.temp_dir), "--skip-llm"],
        )
        # Should complete (may have low/zero score but shouldn't crash)
        assert result.exit_code in [0, 1]

    def test_analyze_with_llm_success(self):
        """Test analyze WITHOUT --skip-llm using real codebase."""
        from unittest.mock import Mock, patch

        # Create REAL codebase with actual security issue
        vulnerable_code = """
import subprocess

def vulnerable_function(user_input):
    # Real security vulnerability
    subprocess.call(user_input, shell=True)

def complex_function(a, b, c, d):
    # Real complexity issue
    if a:
        if b:
            if c:
                if d:
                    return 1
    return 0
"""
        (self.temp_dir / "vulnerable.py").write_text(vulnerable_code)

        # Only mock the external LLM API
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content="""---
## [HIGH] Shell Injection Vulnerability
**Description:** Using shell=True with user input creates security risk.
---"""
                        )
                    )
                ]
            )

            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir)],  # NO --skip-llm
            )

            # Real metrics calculated, LLM integrated
            assert result.exit_code == 0

    def test_analyze_with_llm_returns_empty(self):
        """Test analyze when LLM returns empty response."""
        from unittest.mock import Mock, patch

        # Real codebase
        (self.temp_dir / "simple.py").write_text("def foo(): return 42")

        # Mock LLM to return empty
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = Mock(choices=[Mock(message=Mock(content=""))])

            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir)],
            )

            # Should handle gracefully
            assert result.exit_code == 0

    def test_analyze_with_llm_api_error(self):
        """Test analyze when LLM API fails (not silent mode)."""
        from unittest.mock import patch

        # Real codebase
        (self.temp_dir / "app.py").write_text("x = 1 + 1")

        # Mock LLM to raise realistic exception
        with patch("litellm.completion", side_effect=Exception("API rate limit exceeded")):
            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir)],  # NOT --silent
            )

            # Should continue with metrics-only
            assert result.exit_code == 0
            # Should show warning (unless output is suppressed another way)

    def test_analyze_with_llm_error_silent_mode(self):
        """Test analyze when LLM fails in silent mode."""
        from unittest.mock import patch

        # Real codebase
        (self.temp_dir / "app.py").write_text("y = 2 * 2")

        # Mock LLM to fail
        with patch("litellm.completion", side_effect=Exception("Network error")):
            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir), "--silent"],
            )

            # Should complete silently
            assert result.exit_code == 0
            # Silent mode: no error output

    def test_analyze_with_llm_and_min_score_fail(self):
        """Test analyze with LLM but score below minimum threshold."""
        from unittest.mock import Mock, patch

        # Create minimal file (will have low score)
        (self.temp_dir / "minimal.py").write_text("x = 1")

        # Mock LLM with recommendations
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content="""---
## [MEDIUM] Add More Code
**Description:** File is too minimal.
---"""
                        )
                    )
                ]
            )

            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir), "--min-score", "0.99"],
            )

            # Should fail due to min-score check
            assert result.exit_code == 1

    def test_analyze_calculate_metrics_exception(self):
        """Test analyze when calculate_metrics raises exception (lines 88-90)."""
        from unittest.mock import patch

        # Real codebase
        (self.temp_dir / "code.py").write_text("def foo(): return 42")

        # Mock calculate_metrics to raise exception
        with patch(
            "mfcqi.cli.commands.analyze.calculate_metrics",
            side_effect=Exception("Calculator internal error"),
        ):
            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir)],
            )

            # Should exit with code 1 and show error message
            assert result.exit_code == 1
            assert "Error analyzing codebase" in result.output

    def test_analyze_llm_exception_with_output(self):
        """Test analyze when LLM fails with error output (lines 110-113)."""
        from unittest.mock import patch

        # Real codebase
        (self.temp_dir / "code.py").write_text("def bar(): return 1")

        # Mock get_llm_recommendations to raise exception (NOT silent mode)
        with patch(
            "mfcqi.cli.commands.analyze.get_llm_recommendations",
            side_effect=Exception("LLM service unavailable"),
        ):
            result = self.runner.invoke(
                cli,
                ["analyze", str(self.temp_dir), "--model", "gpt-4o"],  # Explicitly request LLM
            )

            # Should continue with metrics-only (exit code 0)
            assert result.exit_code == 0
            # Should show warning and continuation message
            assert "LLM analysis failed" in result.output
            assert "Continuing with metrics-only analysis" in result.output

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
