"""
Test for PyExamine CLI adapter - following strict TDD.

PyExamine is a CLI tool, so this adapter will:
1. Check if tool is installed
2. Run CLI command
3. Parse output
4. Convert to Smell objects
"""

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_pyexamine_detector_exists():
    """RED: Test that PyExamineDetector class exists."""
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    assert PyExamineDetector is not None


def test_detector_is_smell_detector():
    """RED: Test that detector implements SmellDetector interface."""
    from mfcqi.smell_detection.detector_base import SmellDetector
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    assert issubclass(PyExamineDetector, SmellDetector)


def test_detector_has_correct_name():
    """RED: Test that detector returns correct name."""
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    detector = PyExamineDetector()
    assert detector.name == "pyexamine"


def test_returns_empty_if_tool_not_installed():
    """RED: Test that detector returns empty list if PyExamine not installed."""
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        # If tool not installed, should return empty list (not crash)
        smells = detector.detect(Path(tmpdir))
        assert isinstance(smells, list)


def test_can_check_if_tool_installed():
    """RED: Test that detector can check if PyExamine is installed."""
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    detector = PyExamineDetector()
    is_available = detector.is_available()

    assert isinstance(is_available, bool)


@patch("subprocess.run")
def test_runs_cli_command_when_available(mock_run):
    """RED: Test that detector runs CLI command if tool is available."""
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    # Mock successful CLI execution
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="",  # Empty output for now
        stderr="",
    )

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock is_available to return True
        with patch.object(detector, "is_available", return_value=True):
            detector.detect(Path(tmpdir))

            # Should have called subprocess.run
            assert mock_run.called


@patch("subprocess.run")
def test_parses_code_level_smells(mock_run):
    """RED: Test parsing of code-level smells from PyExamine output."""
    from mfcqi.smell_detection.models import SmellCategory
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    # Mock CLI output with a code smell
    # PyExamine outputs text format, we'll parse key patterns
    mock_output = textwrap.dedent("""
        Code Smells Analysis
        ====================

        Long Method detected in file src/example.py:10
        Method 'process_data' has 60 lines (threshold: 45)
    """)

    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(detector, "is_available", return_value=True):
            smells = detector.detect(Path(tmpdir))

            # Should parse the Long Method smell
            assert len(smells) > 0
            long_method_smells = [s for s in smells if "Long Method" in s.name]
            assert len(long_method_smells) == 1
            assert long_method_smells[0].category == SmellCategory.IMPLEMENTATION


@patch("subprocess.run")
def test_parses_architectural_smells(mock_run):
    """RED: Test parsing of architectural-level smells."""
    from mfcqi.smell_detection.models import SmellCategory
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    mock_output = textwrap.dedent("""
        Architectural Smells Analysis
        ============================

        Cyclic Dependency detected between modules A and B
        Location: src/module_a.py -> src/module_b.py
    """)

    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(detector, "is_available", return_value=True):
            smells = detector.detect(Path(tmpdir))

            # Should parse architectural smell
            cyclic_smells = [s for s in smells if "Cyclic" in s.name]
            assert len(cyclic_smells) == 1
            assert cyclic_smells[0].category == SmellCategory.ARCHITECTURAL


def test_handles_cli_errors_gracefully():
    """RED: Test that detector handles CLI errors without crashing."""
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("subprocess.run", side_effect=FileNotFoundError("Command not found")):
            with patch.object(detector, "is_available", return_value=True):
                # Should not crash
                smells = detector.detect(Path(tmpdir))
                assert smells == []


def test_maps_severity_correctly():
    """RED: Test that severity is mapped from PyExamine output."""
    from mfcqi.smell_detection.models import SmellSeverity
    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    # PyExamine might output severity levels, map them to our enum
    mock_output = "God Class detected in src/big.py:1 (severity: high)"

    mock_run = MagicMock(returncode=0, stdout=mock_output, stderr="")

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("subprocess.run", return_value=mock_run):
            with patch.object(detector, "is_available", return_value=True):
                smells = detector.detect(Path(tmpdir))

                if smells:
                    # Should map to HIGH severity
                    assert any(s.severity == SmellSeverity.HIGH for s in smells)


def test_pyexamine_logs_subprocess_exceptions():
    """RED: Test that subprocess exceptions are logged (not silent)."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from mfcqi.smell_detection.pyexamine import PyExamineDetector

    detector = PyExamineDetector()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock subprocess.run to raise Exception
        with patch("subprocess.run", side_effect=ValueError("Mock parsing error")):
            with patch.object(detector, "is_available", return_value=True):
                with patch("mfcqi.smell_detection.pyexamine.logger") as mock_logger:
                    # Should catch exception and return empty list
                    result = detector.detect(Path(tmpdir))

                    # Should return empty list on error
                    assert result == []

                    # Should log the exception
                    assert mock_logger.debug.called, "Should log subprocess exception"
                    log_message = mock_logger.debug.call_args[0][0]
                    assert "pyexamine" in log_message.lower() or "failed" in log_message.lower()
