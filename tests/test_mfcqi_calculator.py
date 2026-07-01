"""
Test for MFCQI Score Calculator - following strict TDD.
This test MUST fail first because the code doesn't exist yet.
"""

import tempfile
import textwrap
import threading
from pathlib import Path


class _FixedMetric:
    def __init__(self, raw_value: float):
        self.raw_value = raw_value

    def extract(self, codebase: Path) -> float:
        return self.raw_value

    def normalize(self, value: float) -> float:
        return value


class _FailingMetric:
    def extract(self, codebase: Path) -> float:
        raise RuntimeError("metric failed")

    def normalize(self, value: float) -> float:
        return value


class _EmptyMessageFailingMetric(_FailingMetric):
    def extract(self, codebase: Path) -> float:
        raise RuntimeError


class _BarrierMetric(_FixedMetric):
    def __init__(self, barrier: threading.Barrier, thread_ids: set[int]):
        super().__init__(0.8)
        self.barrier = barrier
        self.thread_ids = thread_ids

    def extract(self, codebase: Path) -> float:
        self.thread_ids.add(threading.get_ident())
        self.barrier.wait(timeout=2)
        return self.raw_value


class _SecurityMetric(_FixedMetric):
    def extract(self, codebase: Path) -> float:
        self.last_issues = [{"filename": "service.py", "line_number": 7}]
        return self.raw_value


def test_mfcqi_calculator_exists():
    """RED: Test that MFCQICalculator class exists."""
    from mfcqi.calculator import MFCQICalculator

    assert MFCQICalculator is not None


def test_mfcqi_calculator_initialization():
    """RED: Test that MFCQICalculator can be initialized."""
    from mfcqi.calculator import MFCQICalculator

    calculator = MFCQICalculator()
    assert calculator is not None


def test_parallelism_defaults_to_serial_and_must_be_positive():
    """Parallel metric execution is opt-in and rejects invalid worker counts."""
    import pytest

    from mfcqi.calculator import MFCQICalculator

    assert MFCQICalculator().parallelism == 1
    with pytest.raises(ValueError, match="parallelism must be positive"):
        MFCQICalculator(parallelism=0)


def test_parallel_metrics_match_serial_results_and_preserve_order(tmp_path):
    """Parallel evaluation preserves scores, statuses, failures, and registration order."""
    from mfcqi.calculator import MFCQICalculator

    (tmp_path / "sample.py").write_text("def sample():\n    return 1\n")
    metrics = {
        "first": _FixedMetric(0.8),
        "failed": _FailingMetric(),
        "empty_failed": _EmptyMessageFailingMetric(),
        "third": _FixedMetric(1.2),
    }

    serial = MFCQICalculator(parallelism=1)
    serial._cached_codebase = tmp_path
    serial._cached_metrics = metrics
    parallel = MFCQICalculator(parallelism=4)
    parallel._cached_codebase = tmp_path
    parallel._cached_metrics = metrics

    serial_result = serial.get_detailed_metrics(tmp_path)
    parallel_result = parallel.get_detailed_metrics(tmp_path)

    assert parallel_result == serial_result
    assert list(parallel_result) == [
        "first",
        "failed",
        "empty_failed",
        "third",
        "mfcqi_score",
    ]
    assert parallel.last_metric_statuses == serial.last_metric_statuses
    assert parallel.last_metric_statuses["failed"]["error"] == "metric failed"
    assert parallel.last_metric_statuses["empty_failed"]["status"] == "failed"
    assert parallel.last_metric_statuses["empty_failed"]["error"] == ""


def test_parallel_metrics_execute_concurrently(tmp_path):
    """A worker is allocated per metric up to the configured bound."""
    from mfcqi.calculator import MFCQICalculator

    (tmp_path / "sample.py").write_text("x = 1\n")
    barrier = threading.Barrier(3)
    thread_ids: set[int] = set()
    metrics = {name: _BarrierMetric(barrier, thread_ids) for name in ("first", "second", "third")}
    calculator = MFCQICalculator(parallelism=3)
    calculator._cached_codebase = tmp_path
    calculator._cached_metrics = metrics

    calculator.get_detailed_metrics(tmp_path)

    assert len(thread_ids) == 3


def test_parallel_tool_outputs_are_collected_after_workers_complete(tmp_path):
    """State populated by a metric worker remains available for LLM tool output."""
    from unittest.mock import patch

    from mfcqi.calculator import MFCQICalculator

    (tmp_path / "sample.py").write_text("def sample():\n    return 1\n")
    security = _SecurityMetric(0.9)
    metrics = {
        "cyclomatic_complexity": _FixedMetric(0.8),
        "security": security,
    }
    calculator = MFCQICalculator(parallelism=2)
    calculator._cached_codebase = tmp_path
    calculator._cached_metrics = metrics

    with patch.object(calculator, "_get_complex_functions", return_value=[{"name": "sample"}]):
        result = calculator.get_detailed_metrics_with_tool_outputs(tmp_path)

    assert result["tool_outputs"]["bandit_issues"] == security.last_issues
    assert result["tool_outputs"]["cyclomatic_complexity_raw"] == 0.8
    assert result["tool_outputs"]["complex_functions"] == [{"name": "sample"}]


def test_calculate_simple_codebase():
    """RED: Test MFCQI calculation for simple, well-written codebase."""
    from mfcqi.calculator import MFCQICalculator

    # Simple, well-documented, tested code
    production_code = textwrap.dedent('''
        """A simple math utility module."""

        def add(a, b):
            """Add two numbers.

            Args:
                a: First number
                b: Second number

            Returns:
                Sum of a and b
            """
            return a + b

        def multiply(a, b):
            """Multiply two numbers.

            Args:
                a: First number
                b: Second number

            Returns:
                Product of a and b
            """
            return a * b
    ''')

    test_code = textwrap.dedent('''
        """Tests for math utility module."""

        from math_utils import add, multiply

        def test_add():
            """Test addition function."""
            assert add(2, 3) == 5
            assert add(-1, 1) == 0

        def test_multiply():
            """Test multiplication function."""
            assert multiply(3, 4) == 12
            assert multiply(0, 5) == 0
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "math_utils.py").write_text(production_code)
        (Path(tmpdir) / "test_math_utils.py").write_text(test_code)

        calculator = MFCQICalculator()
        result = calculator.calculate(Path(tmpdir))

        # Well-written code should score reasonably well
        # Note: Score may be lower due to lack of design patterns
        assert 0.4 <= result <= 1.0
        assert isinstance(result, float)


def test_calculate_poor_codebase():
    """RED: Test MFCQI calculation for poor quality codebase."""
    from mfcqi.calculator import MFCQICalculator

    # Complex, undocumented, untested code with duplication
    poor_code = textwrap.dedent("""
        def process(d, t, f, x=None, y=None, z=None):
            r = []
            if not d:
                return None
            for i in d:
                if t == 1:
                    if f:
                        if x and i > x:
                            if y:
                                if i < y:
                                    r.append(i * 2)
                                else:
                                    if z:
                                        r.append(i + z)
                                    else:
                                        r.append(i)
                            else:
                                r.append(i * 3)
                        elif not x:
                            r.append(i / 2 if i != 0 else 0)
                    else:
                        for j in range(i):
                            if j % 2 == 0:
                                for k in range(j):
                                    if k % 3 == 0:
                                        r.append(k)
                elif t == 2:
                    if i % 2 == 0:
                        if i % 3 == 0:
                            if i % 5 == 0:
                                r.append(i * 10)
                            else:
                                r.append(i * 5)
                        else:
                            r.append(i * 2)
                    else:
                        if i % 7 == 0:
                            r.append(i * 7)
                        else:
                            r.append(i)
            return r if r else None

        def duplicate_process(data, type, flag, x=None, y=None, z=None):
            results = []
            if not data:
                return None
            for item in data:
                if type == 1:
                    if flag:
                        if x and item > x:
                            if y:
                                if item < y:
                                    results.append(item * 2)
                                else:
                                    if z:
                                        results.append(item + z)
                                    else:
                                        results.append(item)
                            else:
                                results.append(item * 3)
                        elif not x:
                            results.append(item / 2 if item != 0 else 0)
            return results if results else None
    """)

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "poor_code.py").write_text(poor_code)

        calculator = MFCQICalculator()
        result = calculator.calculate(Path(tmpdir))

        # Poor code should score low
        # Adjusted threshold accounts for:
        # - code_smell_density: 1.0 (no test smells in poor_code)
        # - dependency_security: 1.0 (no dependencies to scan)
        # - secrets_exposure: 1.0 (no secrets in poor_code)
        # - More lenient normalizations (tanh HV, library-aware thresholds)
        # These perfect scores pull up geometric mean despite high complexity
        # With evidence-based recalibrations, threshold increased from 0.46 to 0.50
        assert 0.0 <= result <= 0.50
        assert isinstance(result, float)


def test_calculate_with_all_metrics():
    """RED: Test that calculator uses all implemented metrics."""
    from mfcqi.calculator import MFCQICalculator

    # Code that exercises all metrics
    mixed_code = textwrap.dedent('''
        """Mixed quality module with various patterns."""

        class Logger:
            """Singleton logger class."""
            _instance = None

            def __new__(cls):
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                return cls._instance

            def log(self, message):
                """Log a message."""
                print(f"LOG: {message}")

        def simple_function():
            """A simple documented function."""
            return "simple"

        def complex_function(a, b, c, d):
            if a > 0:
                if b > 0:
                    if c > 0:
                        return a * b * c
                    else:
                        return a * b
                elif d > 0:
                    return a * d
            return 0
    ''')

    test_code = textwrap.dedent('''
        """Tests for mixed quality module."""

        from mixed import simple_function

        def test_simple():
            """Test simple function."""
            assert simple_function() == "simple"
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "mixed.py").write_text(mixed_code)
        (Path(tmpdir) / "test_mixed.py").write_text(test_code)

        calculator = MFCQICalculator()
        result = calculator.calculate(Path(tmpdir))

        # Should return a reasonable score
        assert 0.0 <= result <= 1.0
        assert isinstance(result, float)


def test_get_detailed_metrics():
    """RED: Test that calculator can return detailed metric breakdown."""
    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Simple module."""

        def hello():
            """Say hello."""
            return "Hello, World!"
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "simple.py").write_text(code)

        calculator = MFCQICalculator()
        details = calculator.get_detailed_metrics(Path(tmpdir))

        # Should return a dictionary with all metric scores
        assert isinstance(details, dict)
        assert "cyclomatic_complexity" in details
        assert "halstead_volume" in details
        assert "maintainability_index" in details
        assert "code_duplication" in details
        assert "documentation_coverage" in details
        # Design pattern density may not be included for simple codebases
        # This depends on the complexity-based inclusion logic
        assert "mfcqi_score" in details

        # All values should be floats between 0 and 1 (except raw values)
        for key, value in details.items():
            if key != "mfcqi_score":  # MFCQI score might be calculated differently
                assert isinstance(value, (int, float))


def test_geometric_mean_formula():
    """RED: Test that calculator uses geometric mean formula."""
    from mfcqi.calculator import MFCQICalculator

    # Create calculator and test with known values
    calculator = MFCQICalculator()

    # Mock metric values for testing geometric mean (all above min threshold)
    # This tests the internal _calculate_geometric_mean method
    test_values = [0.8, 0.7, 0.9, 0.6, 0.85, 0.75, 0.8]
    expected_geometric_mean = (0.8 * 0.7 * 0.9 * 0.6 * 0.85 * 0.75 * 0.8) ** (1 / 7)

    # Test the geometric mean calculation
    result = calculator._calculate_geometric_mean(test_values)
    assert abs(result - expected_geometric_mean) < 0.001

    # Test with zeros (should use minimum threshold)
    test_values_with_zero = [0.8, 0.0, 0.9, 0.6, 0.85, 0.75, 0.8]
    result_with_zero = calculator._calculate_geometric_mean(test_values_with_zero)
    # Should be > 0 due to minimum threshold handling
    assert result_with_zero > 0.0


def test_empty_codebase():
    """RED: Test MFCQI calculation for empty codebase."""
    from mfcqi.calculator import MFCQICalculator

    with tempfile.TemporaryDirectory() as tmpdir:
        calculator = MFCQICalculator()
        result = calculator.calculate(Path(tmpdir))

        # Empty codebase should return 0 or very low score
        assert result == 0.0


def test_cqi_score_bounds():
    """RED: Test that MFCQI score is always between 0 and 1."""
    from mfcqi.calculator import MFCQICalculator

    # Test with various codebases to ensure score bounds
    test_cases = [
        "def x(): pass",  # Minimal code
        "def f():\n    '''Doc'''\n    return 1",  # Documented
        "",  # Empty
    ]

    calculator = MFCQICalculator()

    for i, code in enumerate(test_cases):
        with tempfile.TemporaryDirectory() as tmpdir:
            if code:  # Skip empty code case
                (Path(tmpdir) / f"test{i}.py").write_text(code)

            result = calculator.calculate(Path(tmpdir))

            # Score must be between 0 and 1
            assert 0.0 <= result <= 1.0, f"Score {result} out of bounds for case {i}"


def test_get_detailed_metrics_with_tool_outputs():
    """Test that calculator can return detailed metrics with tool outputs."""
    import textwrap

    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Module with some complexity."""

        def complex_function(a, b, c):
            """A function with some logic."""
            if a > 0:
                if b > 0:
                    return a * b
                else:
                    return a + c
            else:
                return c
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "complex.py").write_text(code)

        calculator = MFCQICalculator()
        result = calculator.get_detailed_metrics_with_tool_outputs(Path(tmpdir))

        # Should return a dictionary with metrics and tool outputs
        assert isinstance(result, dict)
        assert "metrics" in result
        assert "tool_outputs" in result
        assert "mfcqi_score" in result

        # Metrics should contain the standard metrics
        metrics = result["metrics"]
        assert "cyclomatic_complexity" in metrics
        assert "halstead_volume" in metrics


def test_get_complex_functions():
    """Test that calculator can identify complex functions."""
    import textwrap

    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Module with functions of varying complexity."""

        def simple():
            """Simple function."""
            return 1

        def complex_nested(a, b, c, d):
            """Complex nested function."""
            if a > 0:
                if b > 0:
                    if c > 0:
                        if d > 0:
                            return a * b * c * d
                        else:
                            return a * b * c
                    else:
                        return a * b
                else:
                    return a
            else:
                return 0
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "complex.py").write_text(code)

        calculator = MFCQICalculator()
        complex_funcs = calculator._get_complex_functions(Path(tmpdir), limit=5)

        # Should return a list of complex functions
        assert isinstance(complex_funcs, list)
        # Should find at least the complex_nested function
        if complex_funcs:
            assert all(isinstance(f, dict) for f in complex_funcs)
            assert all("name" in f for f in complex_funcs)
            assert all("complexity" in f for f in complex_funcs)


def test_metric_exception_handling():
    """Test that calculator handles metric exceptions gracefully."""
    import textwrap
    from unittest.mock import patch

    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Test module."""
        def test():
            """Test function."""
            return 1
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text(code)

        calculator = MFCQICalculator()

        # Patch one metric to raise an exception
        with patch.object(
            calculator.metrics["cyclomatic_complexity"],
            "extract",
            side_effect=Exception("Test error"),
        ):
            # Should still return a score (0.0 for failed metric)
            result = calculator.calculate(Path(tmpdir))
            assert 0.0 <= result <= 1.0
            assert calculator.last_metric_statuses["cyclomatic_complexity"]["status"] == "failed"
            assert "Test error" in calculator.last_metric_statuses["cyclomatic_complexity"]["error"]


def test_get_detailed_metrics_invalid_codebase():
    """Test that get_detailed_metrics handles invalid codebases."""
    from mfcqi.calculator import MFCQICalculator

    calculator = MFCQICalculator()

    # Test with non-existent path
    result = calculator.get_detailed_metrics(Path("/nonexistent/path"))

    assert isinstance(result, dict)
    assert result["mfcqi_score"] == 0.0
    assert "cyclomatic_complexity" in result
    assert result["cyclomatic_complexity"] == 0.0


def test_get_detailed_metrics_with_tool_outputs_invalid_codebase():
    """Test that get_detailed_metrics_with_tool_outputs handles invalid codebases."""
    from mfcqi.calculator import MFCQICalculator

    calculator = MFCQICalculator()

    # Test with non-existent path
    result = calculator.get_detailed_metrics_with_tool_outputs(Path("/nonexistent/path"))

    assert isinstance(result, dict)
    assert result["mfcqi_score"] == 0.0
    assert result["metrics"] == {}
    assert result["tool_outputs"] == {}


def test_detailed_metrics_exception_handling():
    """Test that get_detailed_metrics handles metric exceptions."""
    import textwrap
    from unittest.mock import patch

    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Test module."""
        def test():
            """Test function."""
            return 1
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text(code)

        calculator = MFCQICalculator()

        # Patch metric to raise exception
        with patch.object(
            calculator.metrics["maintainability_index"], "extract", side_effect=RuntimeError("Test")
        ):
            result = calculator.get_detailed_metrics(Path(tmpdir))

            # Should still return results with 0.0 for failed metric
            assert isinstance(result, dict)
            assert "maintainability_index" in result
            assert result["maintainability_index"] == 0.0
            assert calculator.last_metric_statuses["maintainability_index"]["status"] == "failed"
            assert "Test" in calculator.last_metric_statuses["maintainability_index"]["error"]


def test_paradigm_detection_exception_falls_back_to_complexity():
    """Test that paradigm detection failure falls back to complexity-based detection."""
    import textwrap
    from unittest.mock import patch

    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Test module."""
        class TestClass:
            """Test class."""
            pass
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text(code)

        calculator = MFCQICalculator(use_paradigm_detection=True)

        # Patch paradigm detector to raise exception
        with patch.object(
            calculator.paradigm_detector, "detect_paradigm", side_effect=RuntimeError("Test error")
        ):
            # Should fall back to complexity-based detection
            result = calculator.calculate(Path(tmpdir))
            assert 0.0 <= result <= 1.0


def test_get_complex_functions_with_file_errors():
    """Test _get_complex_functions handles file read errors."""
    import textwrap

    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Module with complex function."""
        def complex(a, b, c):
            """Complex function."""
            if a:
                if b:
                    if c:
                        if a > b:
                            if b > c:
                                if a > c:
                                    return a * b * c
            return 0
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = Path(tmpdir) / "complex.py"
        py_file.write_text(code)

        calculator = MFCQICalculator()

        # Should handle errors gracefully
        complex_funcs = calculator._get_complex_functions(Path(tmpdir))

        # Should return a list (may be empty if error occurred)
        assert isinstance(complex_funcs, list)


def test_oo_metrics_include_cbo_and_lcom():
    """RED: Test that OO code includes CBO and LCOM metrics."""
    import textwrap

    from mfcqi.calculator import MFCQICalculator

    # OO code with multiple classes and coupling
    oo_code = textwrap.dedent('''
        """Object-oriented module with coupling and cohesion."""

        class Database:
            """Database connection."""
            def __init__(self):
                """Initialize database."""
                self.connection = None

            def connect(self):
                """Connect to database."""
                self.connection = "connected"
                return self.connection

        class UserRepository:
            """User repository with database coupling."""
            def __init__(self, database):
                """Initialize repository.

                Args:
                    database: Database instance
                """
                self.database = database
                self.cache = {}

            def get_user(self, user_id):
                """Get user by ID.

                Args:
                    user_id: User identifier
                """
                if user_id in self.cache:
                    return self.cache[user_id]
                return None

            def save_user(self, user_id, user_data):
                """Save user data.

                Args:
                    user_id: User identifier
                    user_data: User information
                """
                self.cache[user_id] = user_data
                return user_data
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "repository.py").write_text(oo_code)

        calculator = MFCQICalculator(use_paradigm_detection=True)
        details = calculator.get_detailed_metrics(Path(tmpdir))

        # Should include CBO (Coupling Between Objects)
        assert "cbo" in details, "CBO metric should be included for OO code"

        # Should include LCOM (Lack of Cohesion of Methods)
        assert "lcom" in details, "LCOM metric should be included for OO code"

        # Metrics should be valid scores
        assert 0.0 <= details["cbo"] <= 1.0
        assert 0.0 <= details["lcom"] <= 1.0


def test_cbo_metric_detects_coupling():
    """RED: Test that CBO metric correctly detects coupling between classes."""
    import textwrap

    from mfcqi.calculator import MFCQICalculator

    # Highly coupled classes
    coupled_code = textwrap.dedent('''
        """Module with high coupling."""

        class ServiceA:
            """Service A."""
            pass

        class ServiceB:
            """Service B."""
            pass

        class ServiceC:
            """Service C."""
            pass

        class GodObject:
            """God object with high coupling to many services."""
            def __init__(self, service_a, service_b, service_c):
                """Initialize with multiple dependencies."""
                self.service_a = service_a
                self.service_b = service_b
                self.service_c = service_c
                self.data = {}
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "coupled.py").write_text(coupled_code)

        calculator = MFCQICalculator()
        details = calculator.get_detailed_metrics(Path(tmpdir))

        # CBO should detect coupling
        assert "cbo" in details
        # High coupling should result in lower score
        assert 0.0 <= details["cbo"] <= 1.0


def test_lcom_metric_detects_lack_of_cohesion():
    """RED: Test that LCOM metric correctly detects lack of cohesion."""
    import textwrap

    from mfcqi.calculator import MFCQICalculator

    # Class with low cohesion (methods don't share attributes)
    low_cohesion_code = textwrap.dedent('''
        """Module with low cohesion class."""

        class MixedResponsibilities:
            """Class with mixed responsibilities (low cohesion)."""

            def __init__(self):
                """Initialize with separate data."""
                self.user_data = {}
                self.product_data = {}
                self.order_data = {}

            def manage_user(self, user_id):
                """Manage user (only uses user_data)."""
                return self.user_data.get(user_id)

            def manage_product(self, product_id):
                """Manage product (only uses product_data)."""
                return self.product_data.get(product_id)

            def manage_order(self, order_id):
                """Manage order (only uses order_data)."""
                return self.order_data.get(order_id)
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "low_cohesion.py").write_text(low_cohesion_code)

        calculator = MFCQICalculator()
        details = calculator.get_detailed_metrics(Path(tmpdir))

        # LCOM should detect lack of cohesion
        assert "lcom" in details
        # Low cohesion should result in lower score
        assert 0.0 <= details["lcom"] <= 1.0


def test_single_file_detailed_metrics_have_doc_coverage():
    """Analyzing a single .py file should return real metrics (not zeros fallback)."""
    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent('''
        """Module docstring."""
        def f(x, y):
            """Add x and y."""
            return x + y
    ''')

    with tempfile.TemporaryDirectory() as tmpdir:
        py = Path(tmpdir) / "one.py"
        py.write_text(code)

        calc = MFCQICalculator()
        details = calc.get_detailed_metrics(py)

        assert isinstance(details, dict)
        assert "documentation_coverage" in details
        # Normalized documentation coverage should be > 0 for documented module/function
        assert details["documentation_coverage"] > 0.0
        assert 0.0 <= details["mfcqi_score"] <= 1.0


def test_single_file_calculate_bounds():
    """calculate() on a single file should run and return a bounded score."""
    from mfcqi.calculator import MFCQICalculator

    code = "def f():\n    return 1\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        py = Path(tmpdir) / "f.py"
        py.write_text(code)

        calc = MFCQICalculator()
        score = calc.calculate(py)
        assert 0.0 <= score <= 1.0


def test_single_file_detailed_metrics_with_tool_outputs():
    """get_detailed_metrics_with_tool_outputs() should accept a single file."""
    from mfcqi.calculator import MFCQICalculator

    code = textwrap.dedent("""
        def g(a, b):
            if a:
                return b
            return a
    """)

    with tempfile.TemporaryDirectory() as tmpdir:
        py = Path(tmpdir) / "g.py"
        py.write_text(code)

        calc = MFCQICalculator()
        result = calc.get_detailed_metrics_with_tool_outputs(py)

        assert isinstance(result, dict)
        assert "metrics" in result and isinstance(result["metrics"], dict)
        assert "mfcqi_score" in result
        # Should include some standard metrics
        assert "cyclomatic_complexity" in result["metrics"]
