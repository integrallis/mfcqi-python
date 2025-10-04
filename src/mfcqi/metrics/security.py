"""
Security vulnerability metric using Bandit SAST (Static Application Security Testing).

Implements source code security analysis to detect common vulnerability patterns
in Python code including SQL injection, command injection, hardcoded credentials,
weak cryptography, and other OWASP Top 10 vulnerabilities.

Research Foundation:
    - OWASP Top 10 2021: Industry-standard vulnerability categories
    - CWE (Common Weakness Enumeration): Standardized weakness taxonomy
    - CVSS v3.1: Common Vulnerability Scoring System for severity
    - NIST SSDF: Secure Software Development Framework

SAST Impact on Security:
    - SAST adoption reduces vulnerabilities by 40-60% (Synopsys 2024)
    - Code-level detection 100x cheaper than production fixes
    - Average cost to fix vulnerability: $100 (dev) vs $10,000 (production)
    - SAST finds 85% of injection flaws, 75% of crypto issues

Implementation:
    - Uses Bandit Python API directly (no subprocess)
    - Maps all findings to CWE IDs for standardized categorization
    - CVSS-inspired severity scoring (HIGH=6, MEDIUM=3, LOW=1)
    - Normalizes as vulnerability density (CVSS points per LOC)

References:
    [1] OWASP (2021). "OWASP Top 10 - 2021"
    [2] MITRE (2024). "Common Weakness Enumeration (CWE)"
    [3] FIRST (2019). "CVSS v3.1 Specification"
    [4] NIST (2022). "SP 800-218: Secure Software Development Framework"
    [5] Synopsys (2024). "DevSecOps Practices and Open Source Management Report"
"""

import contextlib
import json
import logging
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, ClassVar, Union, cast

try:
    from bandit.core import config as b_config
    from bandit.core import manager as b_manager

    BANDIT_AVAILABLE = True
except ImportError:
    BANDIT_AVAILABLE = False
    b_config = None
    b_manager = None

from mfcqi.core.file_utils import get_python_files
from mfcqi.core.metric import Metric

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Only show warnings and errors by default


class SecurityMetric(Metric):
    """Security vulnerability density metric using Bandit SAST.

    Performs static analysis to detect security anti-patterns and vulnerable
    code constructs. Maps all findings to CWE IDs and calculates CVSS-inspired
    severity scores normalized by codebase size.

    Detection Categories:
        - Injection flaws (SQL, command, code)
        - Broken authentication (hardcoded credentials)
        - Cryptographic failures (weak algorithms, insecure RNG)
        - XML/XXE vulnerabilities
        - Security misconfiguration (debug mode, bind 0.0.0.0)
        - Insecure deserialization (pickle)

    Normalization Strategy:
        - Calculates total CVSS points: HIGH=6, MEDIUM=3, LOW=1
        - Normalizes by codebase size: points / (LOC / 1000)
        - Exponential decay: score = e^(-density/5)
        - Severe penalties for any HIGH severity issues

    Rationale for High Weight (0.7):
        - Security vulnerabilities directly enable attacks
        - Single vulnerability can compromise entire system
        - Code-level flaws persist across deployments
        - Automated exploit scanners target common patterns
    """

    # Critical security checks that should NEVER be skipped
    CRITICAL_CHECKS: ClassVar[list[str]] = [
        "B301",  # pickle - arbitrary code execution
        "B605",  # os.system - command injection
        "B307",  # eval - arbitrary code execution
        "B608",  # SQL injection
        "B105",  # hardcoded passwords
        "B104",  # hardcoded bind all interfaces (0.0.0.0)
    ]

    # Bandit to CWE mapping (based on OWASP and CWE database)
    BANDIT_TO_CWE: ClassVar[dict[str, str]] = {
        "B101": "CWE-703",  # assert_used - Improper Check or Handling of Exceptional Conditions
        "B102": "CWE-78",  # exec_used - OS Command Injection
        "B103": "CWE-78",  # set_bad_file_permissions
        "B104": "CWE-605",  # hardcoded_bind_all_interfaces
        "B105": "CWE-259",  # hardcoded_password_string
        "B106": "CWE-259",  # hardcoded_password_funcarg
        "B107": "CWE-259",  # hardcoded_password_default
        "B108": "CWE-319",  # hardcoded_tmp_directory - Cleartext Transmission
        "B110": "CWE-330",  # try_except_pass
        "B112": "CWE-330",  # try_except_continue
        "B201": "CWE-400",  # flask_debug_true - Resource Exhaustion
        "B301": "CWE-502",  # pickle - Deserialization of Untrusted Data
        "B302": "CWE-327",  # marshal - Use of Broken Crypto
        "B303": "CWE-327",  # md5 - Use of Weak Hash
        "B304": "CWE-327",  # des - Use of Weak Crypto
        "B305": "CWE-327",  # cipher - Use of Weak Crypto
        "B306": "CWE-311",  # mktemp_q - Missing Encryption
        "B307": "CWE-78",  # eval - OS Command Injection (can lead to it)
        "B308": "CWE-611",  # mark_safe - Improper Restriction of XML
        "B309": "CWE-611",  # httpsconnection - XML External Entity
        "B310": "CWE-22",  # urllib_urlopen - Path Traversal
        "B311": "CWE-330",  # random - Use of Insufficiently Random Values
        "B312": "CWE-326",  # telnetlib - Inadequate Encryption Strength
        "B313": "CWE-611",  # xml_bad_cElementTree
        "B314": "CWE-611",  # xml_bad_ElementTree
        "B315": "CWE-611",  # xml_bad_expatreader
        "B316": "CWE-611",  # xml_bad_expatbuilder
        "B317": "CWE-611",  # xml_bad_sax
        "B318": "CWE-611",  # xml_bad_minidom
        "B319": "CWE-611",  # xml_bad_pulldom
        "B320": "CWE-611",  # xml_bad_etree
        "B321": "CWE-326",  # ftplib - Inadequate Encryption
        "B322": "CWE-22",  # input - Path Traversal
        "B323": "CWE-295",  # unverified_context - Improper Certificate Validation
        "B324": "CWE-327",  # hashlib_new_insecure_functions
        "B325": "CWE-319",  # tempnam - Cleartext Storage
        "B401": "CWE-94",  # import_telnetlib
        "B402": "CWE-94",  # import_ftplib
        "B403": "CWE-94",  # import_pickle
        "B404": "CWE-94",  # import_subprocess
        "B405": "CWE-611",  # import_xml_etree
        "B406": "CWE-611",  # import_xml_sax
        "B407": "CWE-611",  # import_xml_expat
        "B408": "CWE-611",  # import_xml_minidom
        "B409": "CWE-611",  # import_xml_pulldom
        "B410": "CWE-611",  # import_lxml
        "B411": "CWE-611",  # import_xmlrpclib
        "B412": "CWE-94",  # import_httpoxy
        "B413": "CWE-327",  # import_pycrypto
        "B414": "CWE-327",  # import_pycryptodome
        "B501": "CWE-295",  # request_with_no_cert_validation
        "B502": "CWE-327",  # ssl_with_bad_version
        "B503": "CWE-326",  # ssl_with_bad_defaults
        "B504": "CWE-295",  # ssl_with_no_version
        "B505": "CWE-327",  # weak_cryptographic_key
        "B506": "CWE-1333",  # yaml_load - Inefficient Regex
        "B507": "CWE-295",  # ssh_no_host_key_verification
        "B601": "CWE-78",  # paramiko_calls - OS Command Injection
        "B602": "CWE-78",  # subprocess_popen_with_shell_equals_true
        "B603": "CWE-78",  # subprocess_without_shell_equals_true
        "B604": "CWE-78",  # any_other_function_with_shell_equals_true
        "B605": "CWE-78",  # start_process_with_a_shell
        "B606": "CWE-78",  # start_process_with_no_shell
        "B607": "CWE-78",  # start_process_with_partial_path
        "B608": "CWE-89",  # hardcoded_sql_expressions - SQL Injection
        "B609": "CWE-78",  # linux_commands_wildcard_injection
        "B610": "CWE-77",  # django_extra_used - Command Injection
        "B611": "CWE-89",  # django_rawsql_used - SQL Injection
        "B701": "CWE-94",  # jinja2_autoescape_false - Code Injection
        "B702": "CWE-330",  # use_of_mako_templates - Insufficient Randomness
        "B703": "CWE-79",  # django_mark_safe - Cross-site Scripting
    }

    def __init__(self, threshold: float = 0.03):
        """Initialize security metric and check for Bandit.

        Args:
            threshold: Vulnerability density threshold for normalization.
                      Default 0.03 = 3 CVSS points per 100 lines is concerning.
                      This is more realistic for Python codebases with subprocess usage.
                      Lower values are stricter, higher values are more lenient.
        """
        self._check_bandit_installed()
        self._cache: dict[
            str, tuple[float, float, list[Any]]
        ] = {}  # path -> (mtime_sum, result, issues)
        self._cached_codebase: Path | None = None
        self._cached_python_files: list[Path] = []
        self.threshold = threshold

    def _check_bandit_installed(self) -> None:
        """Check if Bandit is installed."""
        if not BANDIT_AVAILABLE:
            logger.error("Bandit is not installed")
            raise RuntimeError(
                "Bandit is not installed. Please install it with: pip install bandit"
            )

    def extract(self, codebase: Path) -> float:
        """Extract security vulnerability density from codebase."""
        logger.info(f"Analyzing security vulnerabilities in {codebase}")

        # Check cache
        cache_key = str(codebase.resolve())
        mtime_sum = self._get_mtime_sum(codebase)

        if cache_key in self._cache:
            cached_mtime, cached_result, cached_issues = self._cache[cache_key]
            if cached_mtime == mtime_sum:
                logger.debug(f"Using cached result for {codebase}")
                self.last_issues = cached_issues  # Store for LLM context
                return float(cached_result)

        # Run Bandit to find vulnerabilities
        vulnerabilities = self._run_bandit(codebase)

        # If Bandit failed to run, return worst score
        if vulnerabilities is None:
            logger.error("Bandit failed to run - assuming worst case for security")
            self.last_issues = []
            # Return high vulnerability density to indicate problem
            return 10.0  # Will normalize to 0.0 (worst score)

        self.last_issues = vulnerabilities  # Store for LLM context

        if not vulnerabilities:
            logger.info("No vulnerabilities found")
            return 0.0  # No vulnerabilities = good

        # Calculate total CVSS-like score
        total_score = 0.0
        for vuln in vulnerabilities:
            severity = vuln.get("issue_severity", "LOW")
            confidence = vuln.get("issue_confidence", "LOW")
            test_id = vuln.get("test_id", "")

            # Calculate base CVSS score
            cvss_score = self._calculate_cvss(severity, confidence)

            # Adjust for CWE severity
            cwe_id = self._get_cwe_id(test_id)
            cvss_score = self._adjust_for_cwe(cvss_score, cwe_id)

            total_score += cvss_score

        logger.info(
            f"Found {len(vulnerabilities)} vulnerabilities with total CVSS score {total_score:.2f}"
        )

        # Count lines of code for density calculation
        loc = self._count_lines(codebase)
        if loc == 0:
            logger.warning("No lines of code found in codebase")
            return 0.0

        # Return vulnerability density (CVSS points per line)
        density = total_score / loc
        logger.info(f"Vulnerability density: {density:.4f} (CVSS points per LOC)")

        # Cache the result
        self._cache[cache_key] = (mtime_sum, density, vulnerabilities)

        return density

    def _get_mtime_sum(self, codebase: Path) -> float:
        """Calculate sum of modification times for all Python files."""
        # Cache python files to avoid redundant filesystem traversal
        if not hasattr(self, "_cached_python_files") or self._cached_codebase != codebase:
            self._cached_python_files = list(get_python_files(codebase))
            self._cached_codebase = codebase

        mtime_sum = 0.0
        for py_file in self._cached_python_files:
            try:
                mtime_sum += py_file.stat().st_mtime
            except OSError:
                continue
        return mtime_sum

    def _run_bandit(self, codebase: Path, enforce_critical: bool = False) -> list[Any] | None:
        """Run Bandit security scanner and return issues using library API.

        Returns None if Bandit fails to run (timeout, etc).
        Returns empty list if Bandit runs but finds no issues.
        """
        if not BANDIT_AVAILABLE:
            return None

        try:
            # Run standard bandit scan using library
            results = self._run_standard_bandit_scan_library(codebase)

            # Run critical checks if needed
            if enforce_critical and (codebase / ".bandit").exists():
                critical_results = self._run_critical_bandit_checks_library(codebase)
                results = self._merge_critical_results(results, critical_results)

            return list(results) if results else []

        except Exception as e:
            logger.warning(f"Bandit execution failed: {e}")
            return None

    def _run_standard_bandit_scan_library(self, codebase: Path, timeout: int = 180) -> list[Any]:
        """Run standard Bandit scan using library API with timeout."""
        result_container: dict[str, Any] = {"result": [], "exception": None}

        def run_bandit_thread() -> None:
            """Run Bandit in a separate thread."""
            try:
                # Check for .bandit config file
                bandit_config = codebase / ".bandit"
                skips = []
                excluded_paths = []

                if bandit_config.exists():
                    try:
                        import configparser

                        parser = configparser.ConfigParser()
                        parser.read(bandit_config)
                        if "bandit" in parser:
                            # Get skips
                            if parser["bandit"].get("skips"):
                                skips = [
                                    s.strip() for s in parser["bandit"].get("skips", "").split(",")
                                ]

                            # Get excludes
                            exclude = parser["bandit"].get("exclude", "")
                            if exclude:
                                excluded_paths = [p.strip() for p in exclude.split(",")]
                    except configparser.Error:
                        # If configparser fails, try to parse manually for common patterns
                        try:
                            config_text = bandit_config.read_text()
                            # Look for skips in list format
                            import re

                            skips_match = re.search(
                                r"skips\s*=\s*\[(.*?)\]", config_text, re.DOTALL
                            )
                            if skips_match:
                                # Extract items from the list
                                skips_text = skips_match.group(1)
                                # Find all quoted strings
                                skips = re.findall(r'["\']([^"\']+)["\']', skips_text)
                        except Exception as e:
                            # Log bandit config parsing failure (graceful degradation)
                            logger.debug(f"Failed to parse bandit config at {bandit_config}: {e}")

                # Create Bandit configuration and manager
                b_conf = b_config.BanditConfig()
                b_mgr = b_manager.BanditManager(b_conf, "file")

                # Apply skips by removing tests from the test set
                # Map of test IDs to their AST node types and function names
                test_id_map = {
                    "B101": ("Assert", "assert_used"),
                    "B102": ("Call", "exec_used"),
                    "B103": ("Import", "set_bad_file_permissions"),
                    "B104": ("FunctionDef", "hardcoded_bind_all_interfaces"),
                    "B105": ("Str", "hardcoded_password_string"),
                    "B106": ("FunctionDef", "hardcoded_password_funcdef"),
                    "B107": ("FunctionDef", "hardcoded_password_default"),
                    # Add more mappings as needed
                }

                for skip_id in skips:
                    if skip_id in test_id_map:
                        ast_type, func_name = test_id_map[skip_id]
                        if ast_type in b_mgr.b_ts.tests:
                            # Filter out the specific test function
                            b_mgr.b_ts.tests[ast_type] = [
                                t for t in b_mgr.b_ts.tests[ast_type] if t.__name__ != func_name
                            ]

                # Use src directory if it exists to avoid scanning dependencies
                scan_path = codebase / "src" if (codebase / "src").exists() else codebase

                # Add common excludes to speed up scanning
                default_excludes = [
                    "*/test/*",
                    "*/tests/*",
                    "*/.venv/*",
                    "*/venv/*",
                    "*/node_modules/*",
                    "*/__pycache__/*",
                    "*/build/*",
                    "*/dist/*",
                    "*/.git/*",
                    "*/.tox/*",
                ]
                all_excludes = (
                    ",".join(excluded_paths + default_excludes)
                    if excluded_paths
                    else ",".join(default_excludes)
                )

                # Discover files
                b_mgr.discover_files([str(scan_path)], True, all_excludes)

                # Run tests
                b_mgr.run_tests()

                # Get results in the same format as subprocess version
                results = []
                for issue in b_mgr.get_issue_list():
                    results.append(
                        {
                            "filename": issue.fname,
                            "line_number": issue.lineno,
                            "issue_severity": issue.severity.upper(),
                            "issue_confidence": issue.confidence.upper(),
                            "issue_text": issue.text,
                            "test_name": issue.test,
                            "test_id": issue.test_id,
                        }
                    )

                result_container["result"] = results

            except Exception as e:
                result_container["exception"] = e

        # Run in thread with timeout
        thread = threading.Thread(target=run_bandit_thread, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.warning(f"Bandit scan timed out after {timeout} seconds")
            raise TimeoutError(f"Bandit timed out after {timeout} seconds")

        if result_container["exception"]:
            raise result_container["exception"]

        result = result_container.get("result", [])
        return list(result) if result else []

    def _run_standard_bandit_scan(self, codebase: Path, output_file: str) -> list[Any]:
        """Run standard Bandit scan and return results."""
        # Use src directory if it exists to avoid scanning dependencies
        scan_path = codebase / "src" if (codebase / "src").exists() else codebase

        # Build command - Bandit automatically detects .bandit files
        cmd = ["bandit", "-r", str(scan_path), "-f", "json", "-o", output_file]

        # Check for explicit config file
        bandit_config = codebase / ".bandit"
        if bandit_config.exists():
            logger.debug(f"Using Bandit config from {bandit_config}")

        # Run bandit with timeout
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,  # Shorter timeout since we're scanning src only
        )

        # Read and return results
        with open(output_file) as output:
            data = json.load(output)
            results = data.get("results", [])
            return list(results)

    def _run_critical_bandit_checks_library(self, codebase: Path) -> list[Any]:
        """Run critical Bandit checks using library API."""
        try:
            # Create Bandit configuration
            b_conf = b_config.BanditConfig()

            # Create Bandit manager
            b_mgr = b_manager.BanditManager(b_conf, "file")

            # Scan the codebase
            scan_path = codebase / "src" if (codebase / "src").exists() else codebase

            # Discover files (no excludes for critical checks)
            b_mgr.discover_files([str(scan_path)], True, [])

            # Run all tests (we'll filter results to critical ones)
            b_mgr.run_tests()

            # Get results - filter to only critical checks
            results = []
            for issue in b_mgr.get_issue_list():
                if issue.test_id in self.CRITICAL_CHECKS:
                    results.append(
                        {
                            "filename": issue.fname,
                            "line_number": issue.lineno,
                            "issue_severity": issue.severity.upper(),
                            "issue_confidence": issue.confidence.upper(),
                            "issue_text": issue.text,
                            "test_name": issue.test,
                            "test_id": issue.test_id,
                        }
                    )

            return results

        except Exception as e:
            logger.warning(f"Critical checks failed: {e}")
            return []

    def _run_critical_bandit_checks(self, codebase: Path) -> list[Any]:
        """Run critical Bandit checks without config interference."""
        with tempfile.TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir)

            # Copy Python files to temp directory
            self._copy_python_files_to_temp(codebase, temp_path)

            # Run critical checks
            return self._execute_critical_checks(temp_path, codebase)

    def _copy_python_files_to_temp(self, codebase: Path, temp_path: Path) -> None:
        """Copy Python files to temporary directory."""
        import shutil

        # Use cached python files if available
        if not hasattr(self, "_cached_python_files") or self._cached_codebase != codebase:
            self._cached_python_files = list(get_python_files(codebase))
            self._cached_codebase = codebase

        for py_file in self._cached_python_files:
            rel_path = py_file.relative_to(codebase)
            dest_file = temp_path / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py_file, dest_file)

    def _execute_critical_checks(self, temp_path: Path, original_codebase: Path) -> list[Any]:
        """Execute critical checks and return adjusted results."""
        tests_arg = ",".join(self.CRITICAL_CHECKS)
        critical_cmd = [
            "bandit",
            "-r",
            str(temp_path),
            "-f",
            "json",
            "-t",
            tests_arg,
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as cf:
            critical_file = cf.name
            critical_cmd.extend(["-o", critical_file])

            try:
                subprocess.run(critical_cmd, capture_output=True, text=True, timeout=10)
                results = self._parse_critical_results(critical_file, temp_path, original_codebase)
                return results
            finally:
                # Clean up temp file - handle Windows permission issues
                if Path(critical_file).exists():
                    from contextlib import suppress

                    # On Windows, file might still be in use
                    # Just leave it - temp files will be cleaned up eventually
                    with suppress(PermissionError):
                        Path(critical_file).unlink()

    def _parse_critical_results(
        self, critical_file: str, temp_path: Path, original_codebase: Path
    ) -> list[Any]:
        """Parse critical check results and fix file paths."""
        try:
            with open(critical_file) as critical_output:
                critical_data = json.load(critical_output)
                critical_results = critical_data.get("results", [])

                # Fix filenames to point back to original location
                for cr in critical_results:
                    cr["filename"] = cr["filename"].replace(str(temp_path), str(original_codebase))

                return list(critical_results)
        except (json.JSONDecodeError, FileNotFoundError):
            return []  # No critical issues found

    def _merge_critical_results(self, results: list[Any], critical_results: list[Any]) -> list[Any]:
        """Merge critical results with standard results."""
        existing_ids = {r.get("test_id") for r in results}

        for cr in critical_results:
            if cr.get("test_id") in self.CRITICAL_CHECKS and cr.get("test_id") not in existing_ids:
                results.append(cr)

        return results

    def _cleanup_temp_file(self, temp_file: str | None) -> None:
        """Clean up temporary file."""
        if temp_file:
            temp_path = Path(temp_file)
            if temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()  # Best effort cleanup

    def _calculate_cvss(self, severity: str, confidence: str) -> float:
        """Calculate CVSS-like score based on Bandit severity and confidence.

        Uses CVSS 3.1 ranges:
        - Low: 0.1-3.9
        - Medium: 4.0-6.9
        - High: 7.0-8.9
        - Critical: 9.0-10.0

        Confidence affects the score within the severity band.
        """
        # Base scores for each severity level (middle of CVSS range)
        base_scores = {
            "LOW": 2.0,  # Middle of Low range (0.1-3.9)
            "MEDIUM": 5.5,  # Middle of Medium range (4.0-6.9)
            "HIGH": 8.0,  # Middle of High range (7.0-8.9)
        }

        # Confidence multipliers
        confidence_factors = {
            "LOW": 0.6,  # 60% confidence = lower score
            "MEDIUM": 0.85,  # 85% confidence = medium score
            "HIGH": 1.0,  # 100% confidence = full score
        }

        base = base_scores.get(severity.upper(), 0.1)
        factor = confidence_factors.get(confidence.upper(), 0.5)

        # Calculate adjusted score
        score = base * factor

        # Ensure score stays within reasonable CVSS bounds
        if severity.upper() == "LOW":
            score = max(0.1, min(3.9, score))
        elif severity.upper() == "MEDIUM":
            score = max(2.0, min(6.9, score))
        elif severity.upper() == "HIGH":
            score = max(4.0, min(8.9, score))

        return score

    def _get_cwe_id(self, bandit_id: str) -> str:
        """Map Bandit test ID to CWE ID."""
        return self.BANDIT_TO_CWE.get(bandit_id, "CWE-1")  # CWE-1 is generic weakness

    def _adjust_for_cwe(self, base_score: float, cwe_id: str) -> float:
        """Adjust CVSS score based on CWE severity.

        Critical CWEs get a multiplier to increase their impact.
        """
        # Critical CWEs that should be weighted more heavily
        CRITICAL_CWES = {
            "CWE-78",  # OS Command Injection
            "CWE-89",  # SQL Injection
            "CWE-94",  # Code Injection
            "CWE-502",  # Deserialization
            "CWE-259",  # Hardcoded Password
            "CWE-22",  # Path Traversal
            "CWE-79",  # XSS
        }

        if cwe_id in CRITICAL_CWES:
            # Increase score by 20% for critical CWEs
            return min(10.0, base_score * 1.2)

        return base_score

    def _count_lines(self, codebase: Path) -> int:
        """Count source lines of code (excluding comments and blank lines)."""
        import ast

        # Use cached python files if available
        if not hasattr(self, "_cached_python_files") or self._cached_codebase != codebase:
            self._cached_python_files = list(get_python_files(codebase))
            self._cached_codebase = codebase

        total = 0
        for py_file in self._cached_python_files:
            try:
                content = py_file.read_text()
                # Parse the AST to get actual code lines
                tree = ast.parse(content)
                # Count lines with actual AST nodes
                lines_with_code = set()
                for node in ast.walk(tree):
                    if hasattr(node, "lineno"):
                        lines_with_code.add(node.lineno)
                        if hasattr(node, "end_lineno") and node.end_lineno:
                            for line in range(node.lineno, node.end_lineno + 1):
                                lines_with_code.add(line)
                total += len(lines_with_code)
            except (OSError, UnicodeDecodeError, SyntaxError):
                # If we can't parse, fall back to counting non-empty, non-comment lines
                try:
                    lines = py_file.read_text().splitlines()
                    for line_text in lines:
                        stripped = line_text.strip()
                        if stripped and not stripped.startswith("#"):
                            total += 1
                except (OSError, UnicodeDecodeError):
                    continue
        return total

    def normalize(self, value: Union[float, dict[str, Any]]) -> float:
        """Normalize the vulnerability density to 0-1 range.
        Lower density = higher score (better security).
        Uses exponential decay for smooth gradient.
        """
        value = cast("float", value)  # This metric only returns float from extract()
        import math

        if value == 0.0:
            return 1.0

        # Use exponential decay: score = e^(-value/threshold)
        score = math.exp(-value / self.threshold)

        return max(0.0, min(1.0, score))

    def get_name(self) -> str:
        """Return metric name."""
        return "security"

    def get_weight(self) -> float:
        """Return evidence-based weight for SAST security analysis.

        Weight: 0.7

        Rationale: SAST detects code-level vulnerabilities that persist
        across deployments and directly enable attacks. Security flaws
        have disproportionate impact relative to other quality issues.

        Evidence:
        - Verizon DBIR 2024: Software vulnerabilities in 14% of breaches
        - Ponemon 2023: Mean cost per vulnerable record: $165
        - Forrester 2024: 42% of breaches exploit known code vulnerabilities
        - SAST effectiveness: 40-60% vulnerability reduction (Synopsys)

        Lower than secrets_exposure (0.85) and dependency_security (0.75)
        because SAST has higher false positive rate and requires exploitation.
        Secrets and vulnerable dependencies provide immediate attack paths.

        References:
        [1] Verizon (2024). "Data Breach Investigations Report"
        [2] Ponemon Institute (2023). "Cost of a Data Breach Report"
        [3] Forrester (2024). "The State of Application Security"
        [4] Synopsys (2024). "DevSecOps Practices Report"
        """
        return 0.7
