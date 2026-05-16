"""
Test for pip-audit Python API Integration - Strict TDD.

pip-audit HAS a Python API via:
- pip_audit._audit.Auditor
- pip_audit._service.PyPIService / OsvService
- pip_audit._dependency_source.RequirementSource

Using these internal APIs directly - NO subprocess.

"""

import tempfile
from pathlib import Path


def test_pip_audit_uses_python_api_not_subprocess():
    """
    RED: Test that PipAuditAnalyzer uses pip_audit Python API, not subprocess.

    This test verifies we're using the HONEST code-level API integration.
    """
    import inspect

    from mfcqi.analysis.tools.pip_audit_analyzer import PipAuditAnalyzer

    analyzer = PipAuditAnalyzer()

    # Get the source code of scan_requirements method
    source = inspect.getsource(analyzer.scan_requirements)

    # MUST NOT use subprocess
    assert (
        "subprocess.run" not in source
        and "subprocess.call" not in source
        and "subprocess.Popen" not in source
    ), "PipAuditAnalyzer must NOT use subprocess module"

    # MUST use pip_audit Python API
    assert "Auditor" in source or "pip_audit" in source, (
        "PipAuditAnalyzer must use pip_audit Python API"
    )


def test_pip_audit_detects_vulnerabilities():
    """
    RED: Test that pip-audit detects known vulnerabilities using requests 2.6.0.
    """
    from mfcqi.analysis.tools.pip_audit_analyzer import PipAuditAnalyzer

    requirements = """
requests==2.6.0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        req_file = Path(tmpdir) / "requirements.txt"
        req_file.write_text(requirements.strip())

        analyzer = PipAuditAnalyzer()
        results = analyzer.scan_requirements(req_file)

        # Should return list of vulnerabilities
        assert isinstance(results, list)
        assert len(results) > 0, "requests 2.6.0 should have known vulnerabilities"

        # Check structure
        vuln = results[0]
        assert "package" in vuln
        assert "version" in vuln
        assert "vulnerability_id" in vuln
        assert vuln["package"] == "requests"


def test_pip_audit_structured_scan_reports_failures(monkeypatch):
    """Structured scans should distinguish scanner failure from clean results."""
    from mfcqi.analysis.tools.pip_audit_analyzer import PipAuditAnalyzer

    with tempfile.TemporaryDirectory() as tmpdir:
        req_file = Path(tmpdir) / "requirements.txt"
        req_file.write_text("requests==2.31.0")

        analyzer = PipAuditAnalyzer()
        if analyzer.auditor is None:
            return

        def raise_scan_error(_source):
            raise RuntimeError("audit service unavailable")

        monkeypatch.setattr(analyzer.auditor, "audit", raise_scan_error)

        result = analyzer.scan_requirements_with_status(req_file)

        assert result.success is False
        assert result.vulnerabilities == []
        assert "audit service unavailable" in result.error
