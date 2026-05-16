"""
Dependency Security metric using pip-audit for vulnerability scanning.

Implements Software Composition Analysis (SCA) to detect known vulnerabilities
in project dependencies by scanning requirements files against vulnerability
databases (PyPI Advisory Database, OSV).

Research Foundation:
    - OWASP Top 10 2021: A06 - Vulnerable and Outdated Components
    - Synopsys OSSRA 2024: 84% of codebases contain open source vulnerabilities
    - Black Duck OSSRA 2025: 74% have high-risk vulnerabilities (↑54% YoY)
    - NIST SP 800-161: Supply Chain Risk Management for ICT

Vulnerability Impact:
    - Average time to patch critical vulnerabilities: 60-120 days
    - 48% of breaches involve vulnerabilities in OSS components
    - Mean cost of data breach involving vulnerable components: $4.45M (IBM 2023)

Implementation:
    - Uses pip-audit Python API directly (no subprocess overhead)
    - Scans ALL Python dependency formats:
      * requirements.txt, requirements-*.txt (pip)
      * pyproject.toml (PEP 518/621, Poetry)
      * setup.py, setup.cfg, Pipfile (future support)
    - Weighted scoring by severity (currently uniform MEDIUM=2.0 pending severity extraction)
    - Exponential decay normalization prevents single vulnerability from dominating

References:
    [1] OWASP (2021). "OWASP Top 10 - A06:2021 Vulnerable and Outdated Components"
    [2] Synopsys (2024). "Open Source Security and Risk Analysis Report"
    [3] Black Duck by Synopsys (2025). "OSSRA Report"
    [4] NIST (2022). "SP 800-161 Rev. 1: Cybersecurity Supply Chain Risk Management"
    [5] IBM Security (2023). "Cost of a Data Breach Report"
"""

import math
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Union, cast

from mfcqi.analysis.tools.pip_audit_analyzer import PipAuditAnalyzer
from mfcqi.core.metric import Metric


class DependencySecurityMetric(Metric):
    """Scans Python dependencies for known CVEs using pip-audit.

    Measures supply chain security risk by detecting vulnerabilities in
    third-party dependencies. Uses exponential decay scoring where even
    a single critical vulnerability significantly impacts the score.

    Normalization Strategy:
        - 0 vulnerabilities → 1.0 (perfect security)
        - Exponential decay: score = e^(-weighted_count/5.0)
        - Calibrated so 5 medium vulnerabilities (weight 10) ≈ 0.14 score
        - Severe penalties align with breach impact statistics

    Rationale for High Weight (0.75):
        - Supply chain attacks increased 742% (Sonatype 2023)
        - Dependencies are major attack surface in modern software
        - Log4Shell (CVE-2021-44228) affected 93% of Java applications
        - Average 231 dependencies per application (Veracode 2024)
    """

    def __init__(self, scan_timeout: float = 30.0):
        """Initialize dependency security metric.

        Args:
            scan_timeout: Maximum seconds to wait for each dependency file scan.
        """
        self.scan_timeout = scan_timeout
        self._scan_cache: dict[tuple[tuple[str, int], ...], tuple[float, list[dict[str, str]]]] = {}
        self.last_scan_errors: list[dict[str, str]] = []

    def extract(self, codebase: Path) -> float:
        """
        Count weighted vulnerability density across ALL Python dependency formats.

        Scans:
        - requirements.txt, requirements-*.txt (pip)
        - pyproject.toml (PEP 518/621, Poetry)
        - setup.py, setup.cfg (future)
        - Pipfile (future)

        Returns:
            Weighted vulnerability count (0.0 = no vulnerabilities)
        """
        analyzer = PipAuditAnalyzer()
        self.last_scan_errors = []

        # Find ALL Python dependency files (ecosystem-wide)
        dependency_files: list[Path] = []

        # requirements.txt and variants
        for pattern in ["requirements.txt", "requirements-*.txt"]:
            dependency_files.extend(codebase.glob(f"**/{pattern}"))

        # pyproject.toml (PEP 518/621, Poetry)
        dependency_files.extend(codebase.glob("**/pyproject.toml"))

        # setup.py, setup.cfg (future support - analyzer will skip gracefully)
        dependency_files.extend(codebase.glob("**/setup.py"))
        dependency_files.extend(codebase.glob("**/setup.cfg"))

        # Pipfile (future support - analyzer will skip gracefully)
        dependency_files.extend(codebase.glob("**/Pipfile"))

        if not dependency_files:
            return 0.0  # No dependencies to scan

        cache_key = self._dependency_cache_key(dependency_files)
        if cache_key in self._scan_cache:
            cached_score, cached_errors = self._scan_cache[cache_key]
            self.last_scan_errors = list(cached_errors)
            return cached_score

        # Scan ALL dependency files using intelligent dispatcher
        weighted_vuln_count = 0.0
        for dep_file in dependency_files:
            vulns = self._scan_dependency_file(analyzer, dep_file)

            # For initial implementation, assign uniform weight per vulnerability
            # pip-audit doesn't provide severity directly, so we use moderate weight
            for _vuln in vulns:
                weighted_vuln_count += 2.0  # MEDIUM severity weight

        self._scan_cache[cache_key] = (weighted_vuln_count, list(self.last_scan_errors))
        return weighted_vuln_count

    def _dependency_cache_key(self, dependency_files: list[Path]) -> tuple[tuple[str, int], ...]:
        """Build a cache key from dependency file paths and modification times."""
        key_parts = []
        for dep_file in sorted(dependency_files):
            try:
                key_parts.append((str(dep_file.resolve()), dep_file.stat().st_mtime_ns))
            except OSError:
                key_parts.append((str(dep_file), 0))
        return tuple(key_parts)

    def _scan_dependency_file(
        self, analyzer: PipAuditAnalyzer, dep_file: Path
    ) -> list[dict[str, Any]]:
        """Scan a dependency file with timeout handling."""
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(analyzer.scan_dependency_file_with_status, dep_file)
        try:
            result = future.result(timeout=self.scan_timeout)
            if not result.success:
                self.last_scan_errors.append({"file": str(dep_file), "error": result.error})
            return result.vulnerabilities
        except FutureTimeoutError:
            future.cancel()
            self.last_scan_errors.append(
                {
                    "file": str(dep_file),
                    "error": f"dependency scan timed out after {self.scan_timeout}s",
                }
            )
            return []
        except Exception as exc:
            self.last_scan_errors.append({"file": str(dep_file), "error": str(exc)})
            return []
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def normalize(self, value: Union[float, dict[str, Any]]) -> float:
        """
        Normalize vulnerability count to [0,1] range.

        0 vulnerabilities = 1.0 (perfect)
        Exponential decay based on weighted count.

        Args:
            value: Weighted vulnerability count from extract()

        Returns:
            Normalized score where 1.0 = no vulnerabilities
        """
        value = cast("float", value)

        if value == 0.0:
            return 1.0

        # Exponential decay: score = e^(-value/threshold)
        # Calibrated so 5 vulnerabilities (weight 10) ≈ 0.14 score
        threshold = 5.0
        return math.exp(-value / threshold)

    def get_weight(self) -> float:
        """
        Return evidence-based weight for dependency security.

        Weight: 0.75

        Rationale: Dependencies are a major attack surface.

        Evidence:
        - Synopsys OSSRA 2024: 84% of codebases contain OSS vulnerabilities
        - Black Duck OSSRA 2025: 74% have high-risk vulnerabilities (up 54% YoY)
        - OWASP Top 10 2021: A06 - Vulnerable and Outdated Components

        References:
        [1] Synopsys (2024). "Open Source Security and Risk Analysis Report"
        [2] Black Duck (2025). "OSSRA Report"
        [3] OWASP (2021). "OWASP Top 10"
        """
        return 0.75

    def get_name(self) -> str:
        """Return the name of this metric."""
        return "Dependency Security"
