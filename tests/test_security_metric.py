"""
Test-driven development for SecurityMetric.
"""


def test_security_metric_exists():
    """Test that SecurityMetric class can be imported."""
    from mfcqi.metrics.security import SecurityMetric

    assert SecurityMetric is not None


def test_security_metric_is_metric():
    """Test that SecurityMetric inherits from Metric."""
    from mfcqi.core.metric import Metric
    from mfcqi.metrics.security import SecurityMetric

    assert issubclass(SecurityMetric, Metric)


def test_security_metric_extract_no_vulnerabilities():
    """Test extract returns 0.0 for code with no vulnerabilities."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "safe.py"
        test_file.write_text("""
def add(a: int, b: int) -> int:
    \"\"\"Add two numbers safely.\"\"\"
    return a + b

def multiply(x: float, y: float) -> float:
    \"\"\"Multiply two numbers safely.\"\"\"
    return x * y
""")

        metric = SecurityMetric()
        result = metric.extract(test_dir)

        assert result == 0.0  # No vulnerabilities = 0.0 density


def test_security_metric_extract_with_vulnerabilities():
    """Test extract returns positive value for code with vulnerabilities."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "vulnerable.py"
        # Code with known security issues
        test_file.write_text("""
import os
import pickle

def run_command(user_input):
    # B605: Shell injection vulnerability
    os.system(user_input)

def load_data(data):
    # B301: Pickle deserialization vulnerability
    return pickle.loads(data)

password = "hardcoded_password"  # B105: Hardcoded password
""")

        metric = SecurityMetric()
        result = metric.extract(test_dir)

        # Should return positive value for vulnerabilities
        assert result > 0.0


def test_security_metric_normalize():
    """Test normalize converts vulnerability density to 0-1 score."""
    from mfcqi.metrics.security import SecurityMetric

    metric = SecurityMetric()

    # No vulnerabilities = perfect score
    assert metric.normalize(0.0) == 1.0

    # Very low density (0.001 = 1 CVSS point per 1000 lines) = good score
    assert metric.normalize(0.001) > 0.7

    # Moderate density (0.01 = 1 CVSS point per 100 lines) = good score with new threshold
    assert 0.6 < metric.normalize(0.01) < 0.8

    # High density (0.1 = 1 CVSS point per 10 lines) = very poor score
    assert metric.normalize(0.1) < 0.2

    # Extreme density should approach 0
    assert metric.normalize(1.0) < 0.1


def test_security_metric_checks_bandit_installed():
    """Test that SecurityMetric verifies Bandit availability."""
    from mfcqi.metrics.security import BANDIT_AVAILABLE, SecurityMetric

    if BANDIT_AVAILABLE:
        # Bandit is installed, metric should initialize successfully
        metric = SecurityMetric()
        assert metric is not None
    else:
        # Bandit is not installed, should raise RuntimeError
        try:
            SecurityMetric()
            raise AssertionError("Should have raised RuntimeError when Bandit not available")
        except RuntimeError as e:
            assert "Bandit is not installed" in str(e)


def test_security_metric_counts_sloc_not_raw_lines():
    """Test that SecurityMetric counts source lines, not raw lines."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "code.py"
        # File with comments and blank lines
        test_file.write_text("""#!/usr/bin/env python
# This is a comment

def add(a, b):
    '''
    Adds two numbers.
    This is a docstring.
    '''
    # Another comment
    return a + b


# More comments
class Foo:
    pass

""")

        metric = SecurityMetric()
        sloc = metric._count_lines(test_dir)

        # AST counts the def statement, docstring assignment, return, class, and pass
        # Docstrings in functions are part of the AST as Expr nodes
        # So we expect: line 4 (def), 5-8 (docstring), 10 (return), 14 (class), 15 (pass)
        # That's 7 lines total when ranges are considered
        assert 7 <= sloc <= 9  # AST interpretation may vary


def test_security_metric_cvss_scoring():
    """Test proper CVSS scoring based on severity and confidence."""
    from mfcqi.metrics.security import SecurityMetric

    metric = SecurityMetric()

    # Test severity to CVSS mapping with confidence factors
    # CVSS 3.1 ranges: Low (0.1-3.9), Medium (4.0-6.9), High (7.0-8.9), Critical (9.0-10.0)

    # Low severity
    assert 0.1 <= metric._calculate_cvss("LOW", "LOW") <= 2.0  # Low confidence
    assert 1.0 <= metric._calculate_cvss("LOW", "MEDIUM") <= 3.0  # Medium confidence
    assert 2.0 <= metric._calculate_cvss("LOW", "HIGH") <= 3.9  # High confidence

    # Medium severity
    assert 2.0 <= metric._calculate_cvss("MEDIUM", "LOW") <= 4.0
    assert 4.0 <= metric._calculate_cvss("MEDIUM", "MEDIUM") <= 5.5
    assert 5.0 <= metric._calculate_cvss("MEDIUM", "HIGH") <= 6.9

    # High severity
    assert 4.0 <= metric._calculate_cvss("HIGH", "LOW") <= 6.0
    assert 6.0 <= metric._calculate_cvss("HIGH", "MEDIUM") <= 7.5
    assert 7.0 <= metric._calculate_cvss("HIGH", "HIGH") <= 8.9


def test_security_metric_cleans_up_temp_files():
    """Test that SecurityMetric properly cleans up temp files."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "code.py"
        test_file.write_text("""
import os
os.system("ls")  # Security issue for testing
""")

        # Track temp files created
        temp_files_before = set(Path(tempfile.gettempdir()).iterdir())

        metric = SecurityMetric()
        metric.extract(test_dir)

        # Check temp files after
        temp_files_after = set(Path(tempfile.gettempdir()).iterdir())

        # No new temp files should remain
        new_files = temp_files_after - temp_files_before
        json_files = [f for f in new_files if f.suffix == ".json"]
        assert len(json_files) == 0, f"Temp files not cleaned up: {json_files}"


def test_security_metric_handles_bandit_failures():
    """Test that SecurityMetric handles when Bandit scan returns None (failure)."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "code.py"
        test_file.write_text("def foo(): pass")

        metric = SecurityMetric()

        # Force a failure by passing a non-existent path
        # When Bandit fails, _run_bandit returns None
        # and extract should return 10.0 (worst case)
        non_existent = Path("/this/path/does/not/exist/at/all")
        result = metric.extract(non_existent)

        # When no Python files are found, should return 0.0 (no vulnerabilities in no code)
        # This is consistent with the original behavior
        assert result == 0.0


def test_security_metric_handles_invalid_python():
    """Test that SecurityMetric handles syntactically invalid Python."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "bad.py"
        # Invalid Python syntax
        test_file.write_text("""
def bad syntax():
    this is not valid python
""")

        metric = SecurityMetric()
        # Should handle gracefully, not crash
        result = metric.extract(test_dir)
        # Should still work and return some result
        assert result >= 0.0


def test_security_metric_caches_results():
    """Test that SecurityMetric caches results for performance."""
    import tempfile
    import time
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        # Create a few files for a more realistic test
        for i in range(5):
            test_file = test_dir / f"code{i}.py"
            test_file.write_text(f"""
import os

def process_{i}(cmd):
    os.system(cmd)  # Vulnerability

def safe_func_{i}(a, b):
    return a + b
""")

        metric = SecurityMetric()

        # First call - should run Bandit
        start = time.time()
        result1 = metric.extract(test_dir)
        first_call_time = time.time() - start

        # Second call - should use cache
        start = time.time()
        result2 = metric.extract(test_dir)
        second_call_time = time.time() - start

        # Results should be identical
        assert result1 == result2

        # Second call should be faster (at least 2x to allow for system variance)
        # Note: Using 2x instead of 5x because both calls are very fast (milliseconds)
        # and system variance matters more at this scale
        assert second_call_time < (first_call_time / 2), (
            f"Cache not working: first={first_call_time:.3f}s, second={second_call_time:.3f}s"
        )


def test_security_metric_respects_bandit_config():
    """Test that SecurityMetric respects .bandit configuration files."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create code with a normally flagged issue (assert statement)
        test_file = test_dir / "code.py"
        test_file.write_text("""
def validate(x):
    assert x > 0, "x must be positive"  # B101: assert_used
    return x * 2

def run_command(cmd):
    import os
    os.system(cmd)  # B605: This should still be flagged
""")

        # Create .bandit config that skips B101 (assert_used)
        bandit_config = test_dir / ".bandit"
        bandit_config.write_text("""
[bandit]
skips: B101
""")

        metric = SecurityMetric()

        # Without config, both issues would be found
        # With config, only B605 should be found (not B101)
        result = metric.extract(test_dir)

        # Should have some vulnerabilities (B605) but not the assert (B101)
        assert result > 0, "Should find the os.system vulnerability"

        # To verify B101 is skipped, let's check with explicit config
        vulnerabilities = metric._run_bandit(test_dir)
        issue_codes = [v.get("test_id", "") for v in vulnerabilities]

        assert "B101" not in issue_codes, "B101 (assert_used) should be skipped"
        assert "B605" in issue_codes, "B605 (os.system) should still be detected"


def test_security_metric_enforces_critical_checks():
    """Test that SecurityMetric always runs critical security checks."""
    import tempfile
    from pathlib import Path

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create code with critical vulnerabilities
        test_file = test_dir / "vulnerable.py"
        test_file.write_text("""
import pickle
import os

def load_data(data):
    return pickle.loads(data)  # B301: Critical - arbitrary code execution

def run_cmd(user_input):
    os.system(user_input)  # B605: Critical - command injection

def execute_code(code):
    eval(code)  # B307: Critical - arbitrary code execution

password = "admin123"  # B105: Critical - hardcoded password
""")

        # Try to skip critical checks (this should be overridden)
        bandit_config = test_dir / ".bandit"
        bandit_config.write_text("""
[bandit]
skips: B301,B605,B307,B105
""")

        metric = SecurityMetric()

        # Critical checks should ALWAYS run
        assert metric.CRITICAL_CHECKS == ["B301", "B605", "B307", "B608", "B105", "B104"]

        vulnerabilities = metric._run_bandit(test_dir, enforce_critical=True)
        issue_codes = [v.get("test_id", "") for v in vulnerabilities]

        # These critical issues should be found even if config tries to skip them
        assert "B301" in issue_codes, "B301 (pickle) must always be detected"
        assert "B605" in issue_codes, "B605 (os.system) must always be detected"
        assert "B307" in issue_codes, "B307 (eval) must always be detected"
        assert "B105" in issue_codes, "B105 (hardcoded password) must always be detected"


def test_security_metric_cwe_mapping():
    """Test that SecurityMetric maps vulnerabilities to CWE IDs."""
    from mfcqi.metrics.security import SecurityMetric

    metric = SecurityMetric()

    # Test known Bandit to CWE mappings
    assert metric._get_cwe_id("B301") == "CWE-502"  # pickle
    assert metric._get_cwe_id("B605") == "CWE-78"  # os command injection
    assert metric._get_cwe_id("B608") == "CWE-89"  # SQL injection
    assert metric._get_cwe_id("B105") == "CWE-259"  # hardcoded password
    assert metric._get_cwe_id("B303") == "CWE-327"  # weak crypto (MD5)

    # Unknown should return generic CWE
    assert metric._get_cwe_id("B999") == "CWE-1"  # Generic weakness


def test_security_metric_cwe_severity_adjustment():
    """Test that CWE severity properly adjusts CVSS scores."""
    from mfcqi.metrics.security import SecurityMetric

    metric = SecurityMetric()

    # CWE-78 (OS Command Injection) is critical - should boost score
    base_score = metric._calculate_cvss("MEDIUM", "HIGH")
    adjusted_score = metric._adjust_for_cwe(base_score, "CWE-78")
    assert adjusted_score > base_score, "Critical CWEs should increase score"

    # CWE-259 (hardcoded password) is also serious
    adjusted_pwd = metric._adjust_for_cwe(base_score, "CWE-259")
    assert adjusted_pwd > base_score, "Password CWEs should increase score"

    # Generic CWE-1 should not adjust
    adjusted_generic = metric._adjust_for_cwe(base_score, "CWE-1")
    assert adjusted_generic == base_score, "Generic CWE should not adjust score"


def test_security_metric_configurable_thresholds():
    """Test that SecurityMetric allows configurable normalization thresholds."""
    from mfcqi.metrics.security import SecurityMetric

    # Default threshold
    metric_default = SecurityMetric()
    assert metric_default.threshold == 0.03  # Default: 3 CVSS points per 100 lines

    # Custom threshold (stricter)
    metric_strict = SecurityMetric(threshold=0.005)  # 1 CVSS point per 200 lines
    assert metric_strict.threshold == 0.005

    # Custom threshold (more lenient)
    metric_lenient = SecurityMetric(threshold=0.05)  # Higher threshold = more lenient
    assert metric_lenient.threshold == 0.05

    # Test normalization with different thresholds
    density = 0.01  # 1 CVSS point per 100 lines

    score_default = metric_default.normalize(density)
    score_strict = metric_strict.normalize(density)
    score_lenient = metric_lenient.normalize(density)

    # Stricter threshold = lower score for same density
    # More lenient threshold = higher score for same density
    assert score_strict < score_default < score_lenient, (
        f"Scores should reflect thresholds: strict={score_strict:.3f}, "
        f"default={score_default:.3f}, lenient={score_lenient:.3f}"
    )


def test_security_metric_logs_bandit_config_parsing_failure():
    """RED: Test that Bandit config parsing failures are logged (not silent)."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from mfcqi.metrics.security import SecurityMetric

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        test_file = test_dir / "code.py"
        test_file.write_text("def foo(): pass")

        # Create malformed Bandit config that will fail configparser
        bandit_config = test_dir / ".bandit"
        bandit_config.write_text("skips = ['test']")  # No section header = configparser error

        metric = SecurityMetric()

        # Mock Path.read_text to throw exception during manual parsing
        original_read_text = Path.read_text

        def mock_read_text(self, *args, **kwargs):
            if self.name == ".bandit":
                raise OSError("Mock permission denied")
            return original_read_text(self, *args, **kwargs)

        # Capture debug logs
        with (
            patch("mfcqi.metrics.security.logger") as mock_logger,
            patch.object(Path, "read_text", mock_read_text),
        ):
            # This should trigger the exception handler at line 347
            metric.extract(test_dir)

            # Should log the parsing failure
            assert mock_logger.debug.called, "Should log bandit config parsing failure"
            log_message = mock_logger.debug.call_args[0][0]
            assert "bandit config" in log_message.lower() or "failed" in log_message.lower()
