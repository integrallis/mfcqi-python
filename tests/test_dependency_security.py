"""
Tests for Dependency Security metric using pip-audit.
"""

import tempfile
from pathlib import Path


def test_metric_exists():
    """Test that DependencySecurityMetric class exists."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()
    assert metric is not None
    assert metric.get_name() == "Dependency Security"


def test_no_dependencies_perfect_score():
    """Test that codebase with no dependencies scores 1.0."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Python file but no requirements
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def foo(): pass")

        raw_score = metric.extract(Path(tmpdir))
        normalized = metric.normalize(raw_score)
        assert raw_score == 0.0
        assert normalized == 1.0


def test_no_vulnerabilities_perfect_score():
    """Test that up-to-date dependencies score 1.0."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create requirements with safe packages
        req_file = Path(tmpdir) / "requirements.txt"
        req_file.write_text(
            """
# These should have no known vulnerabilities
click>=8.1.0
rich>=13.0.0
"""
        )

        raw_score = metric.extract(Path(tmpdir))
        normalized = metric.normalize(raw_score)
        assert raw_score == 0.0
        assert normalized == 1.0


def test_vulnerabilities_reduce_score():
    """Test that vulnerabilities reduce the score."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create requirements with known vulnerable version
        req_file = Path(tmpdir) / "requirements.txt"
        req_file.write_text(
            """
# Old urllib3 with known CVE
urllib3==1.24.1
"""
        )

        raw_score = metric.extract(Path(tmpdir))
        normalized = metric.normalize(raw_score)

        # Should have detected vulnerabilities
        assert raw_score > 0.0
        # Score should be reduced
        assert normalized < 1.0


def test_critical_vulnerability_severe_penalty():
    """Test that critical vulnerabilities cause severe penalty."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()

    # Simulate 1 critical vulnerability (weight=10)
    raw_score = 10.0
    normalized = metric.normalize(raw_score)

    # Should drop score significantly
    assert normalized < 0.2  # Severe penalty for critical vuln


def test_multiple_vulnerabilities_weighted():
    """Test that multiple vulnerabilities are weighted correctly."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()

    # Test different weighted scores
    assert metric.normalize(0.0) == 1.0  # No vulns = perfect
    assert metric.normalize(5.0) < 0.5  # Moderate vulns
    assert metric.normalize(10.0) < 0.2  # High vulns
    assert metric.normalize(20.0) < 0.05  # Critical vulns


def test_scan_failures_are_recorded_separately():
    """Test dependency scanner failures are distinguishable from vulnerabilities."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()

    with tempfile.TemporaryDirectory() as tmpdir:
        setup_file = Path(tmpdir) / "setup.py"
        setup_file.write_text("from setuptools import setup\nsetup(name='example')\n")

        raw_score = metric.extract(Path(tmpdir))

        assert raw_score == 0.0
        assert metric.last_scan_errors
        assert metric.last_scan_errors[0]["file"] == str(setup_file)
        assert "Unsupported dependency file format" in metric.last_scan_errors[0]["error"]


def test_metric_weight():
    """Test that weight is 0.75 based on research."""
    from mfcqi.metrics.dependency_security import DependencySecurityMetric

    metric = DependencySecurityMetric()
    assert metric.get_weight() == 0.75
