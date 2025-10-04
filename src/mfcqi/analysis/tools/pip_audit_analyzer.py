"""
pip-audit analyzer for dependency vulnerability scanning.

Uses pip_audit Python API directly - NO subprocess.

pip_audit provides these internal APIs:
- pip_audit._audit.Auditor: Main auditing engine
- pip_audit._service.PyPIService / OsvService: Vulnerability databases
- pip_audit._dependency_source: Multiple dependency sources
  - RequirementSource: requirements.txt
  - PyProjectSource: pyproject.toml (PEP 518/621, Poetry)

NOTE: pip-audit is an optional dependency. If not installed, this analyzer
will gracefully degrade and return empty vulnerability lists.
"""

from pathlib import Path
from typing import Any


class PipAuditAnalyzer:
    """Analyzer for scanning Python dependencies for known vulnerabilities.

    Requires pip-audit package to be installed. If not available, gracefully
    degrades and returns empty results.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize pip-audit analyzer with optional configuration.

        Args:
            config: Optional configuration dict with 'vulnerability_service' key
        """
        self.config = config or {}
        self._available = False
        self.service = None
        self.auditor = None

        # Lazy import pip_audit - don't crash if not installed
        try:
            from pip_audit._audit import Auditor
            from pip_audit._service import OsvService, PyPIService

            # Create vulnerability service based on config
            service_name = self.config.get("vulnerability_service", "pypi")

            if service_name == "osv":
                self.service = OsvService()
            else:
                self.service = PyPIService()

            # Create auditor with the service
            self.auditor = Auditor(self.service)
            self._available = True

        except ImportError:
            # pip-audit not installed - graceful degradation
            pass

    def scan_requirements(self, requirements_file: Path) -> list[dict[str, Any]]:
        """
        Scan a requirements.txt file for vulnerabilities using pip_audit Python API.

        Args:
            requirements_file: Path to requirements.txt file

        Returns:
            List of vulnerability dictionaries with package info.
            Returns empty list if pip-audit not available.
        """
        # Check if pip-audit is available
        if not self._available:
            return []

        try:
            # Lazy import here too for the RequirementSource
            from pip_audit._dependency_source import RequirementSource

            # Check file exists
            if not requirements_file.exists():
                raise FileNotFoundError(f"Requirements file not found: {requirements_file}")

            # Create dependency source from requirements file
            source = RequirementSource([requirements_file])

            # Validate auditor is initialized (safer than assert which can be disabled with -O)
            if self.auditor is None:
                raise RuntimeError(
                    "pip-audit auditor not initialized despite _available=True"
                )

            # Run audit using Python API
            audit_results = self.auditor.audit(source)

            # Convert results to our format
            vulnerabilities = []

            for spec, vulns in audit_results:
                package_name = spec.name
                package_version = str(spec.version)

                for vuln in vulns:
                    vulnerabilities.append(
                        {
                            "package": package_name,
                            "version": package_version,
                            "vulnerability_id": vuln.id,
                            "description": vuln.description or "",
                            "fix_versions": vuln.fix_versions,
                            "aliases": vuln.aliases,
                        }
                    )

            return vulnerabilities

        except Exception:
            # Return empty list on error (graceful degradation)
            return []

    def scan_pyproject(self, pyproject_file: Path) -> list[dict[str, Any]]:
        """
        Scan a pyproject.toml file for vulnerabilities using pip_audit Python API.

        Supports both PEP 518/621 format and Poetry format.

        Args:
            pyproject_file: Path to pyproject.toml file

        Returns:
            List of vulnerability dictionaries with package info.
            Returns empty list if pip-audit not available.
        """
        # Check if pip-audit is available
        if not self._available:
            return []

        try:
            # Lazy import here too for the PyProjectSource
            from pip_audit._dependency_source import PyProjectSource

            # Check file exists
            if not pyproject_file.exists():
                raise FileNotFoundError(f"pyproject.toml not found: {pyproject_file}")

            # Create dependency source from pyproject.toml
            source = PyProjectSource(pyproject_file)

            # Validate auditor is initialized (safer than assert which can be disabled with -O)
            if self.auditor is None:
                raise RuntimeError(
                    "pip-audit auditor not initialized despite _available=True"
                )

            # Run audit using Python API
            audit_results = self.auditor.audit(source)

            # Convert results to our format
            vulnerabilities = []

            for spec, vulns in audit_results:
                package_name = spec.name
                package_version = str(spec.version)

                for vuln in vulns:
                    vulnerabilities.append(
                        {
                            "package": package_name,
                            "version": package_version,
                            "vulnerability_id": vuln.id,
                            "description": vuln.description or "",
                            "fix_versions": vuln.fix_versions,
                            "aliases": vuln.aliases,
                        }
                    )

            return vulnerabilities

        except Exception:
            # Return empty list on error (graceful degradation)
            return []

    def scan_dependency_file(self, dep_file: Path) -> list[dict[str, Any]]:
        """
        Intelligently scan any Python dependency file format.

        Auto-detects file type based on name and delegates to appropriate scanner.

        Supported formats:
        - requirements.txt, requirements-*.txt → RequirementSource
        - pyproject.toml → PyProjectSource
        - setup.py, setup.cfg, Pipfile → Not yet supported (returns empty)

        Args:
            dep_file: Path to dependency file

        Returns:
            List of vulnerability dictionaries
        """
        filename = dep_file.name

        if filename == "pyproject.toml":
            return self.scan_pyproject(dep_file)
        elif filename.startswith("requirements") and filename.endswith(".txt"):
            return self.scan_requirements(dep_file)
        else:
            # setup.py, setup.cfg, Pipfile not yet supported
            # Would require additional dependency source implementations
            return []
