"""
PyExamine CLI adapter for code smell detection.

PyExamine is a comprehensive Python code smell detection tool:
- GitHub: https://github.com/KarthikShivasankar/python_smells_detector
- Paper: arXiv 2501.18327 (MSR 2025)
- Detects 49 metrics across code/structural/architectural layers

This adapter:
1. Checks if PyExamine CLI is installed
2. Runs the CLI command
3. Parses text output
4. Converts to Smell objects

Installation: pip install python-smells-detector
CLI Command: analyze_code_quality /path/to/project

"""

import logging
import re
import subprocess
from pathlib import Path

from mfcqi.smell_detection.detector_base import SmellDetector
from mfcqi.smell_detection.models import Smell, SmellCategory, SmellSeverity

logger = logging.getLogger(__name__)


class PyExamineDetector(SmellDetector):
    """Adapter for PyExamine CLI tool.

    PyExamine detects smells across three layers:
    - Code: Long methods, large classes, duplicate code
    - Structural: High coupling, deep inheritance
    - Architectural: Cyclic dependencies, god objects

    This detector is optional - only works if PyExamine is installed.
    """

    def __init__(self, cli_command: str = "analyze_code_quality"):
        """Initialize detector.

        Args:
            cli_command: PyExamine CLI command name (default: analyze_code_quality)
        """
        self.cli_command = cli_command

    @property
    def name(self) -> str:
        """Return detector name."""
        return "pyexamine"

    def is_available(self) -> bool:
        """Check if PyExamine CLI is installed.

        Returns:
            True if command is available, False otherwise
        """
        try:
            result = subprocess.run(
                [self.cli_command, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def detect(self, codebase: Path) -> list[Smell]:
        """Detect smells using PyExamine CLI.

        Args:
            codebase: Path to codebase root

        Returns:
            List of detected Smell objects
        """
        if not self.is_available():
            # Tool not installed, return empty list
            return []

        try:
            # Run PyExamine CLI
            result = subprocess.run(
                [self.cli_command, str(codebase), "--type", "code"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(codebase.parent) if codebase.parent else None,
            )

            if result.returncode != 0:
                # CLI failed, return empty
                return []

            # Parse output
            smells = self._parse_output(result.stdout, codebase)
            return smells

        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            # Log PyExamine execution failure (graceful degradation)
            logger.debug(f"PyExamine smell detection failed for {codebase}: {e}")
            return []

    def _parse_output(self, output: str, codebase: Path) -> list[Smell]:
        """Parse PyExamine text output into Smell objects.

        PyExamine outputs text format like:
            Long Method detected in file src/example.py:10
            Method 'process_data' has 60 lines (threshold: 45)

            Cyclic Dependency detected between modules A and B
            Location: src/module_a.py -> src/module_b.py

        Args:
            output: CLI stdout
            codebase: Codebase path for relative locations

        Returns:
            List of Smell objects
        """
        smells: list[Smell] = []

        # Parse line by line
        lines = output.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Pattern 1: "Long Method detected in file src/example.py:10"
            match = re.search(r"([\w\s]+) detected in file ([^:]+):(\d+)", line)
            if match:
                smell_name = match.group(1).strip()
                file_path = match.group(2).strip()
                line_num = match.group(3).strip()

                # Get description from next line if available
                description = line
                if i + 1 < len(lines):
                    description += " " + lines[i + 1].strip()

                smell = self._create_smell(smell_name, f"{file_path}:{line_num}", description, line)
                if smell:
                    smells.append(smell)
                continue

            # Pattern 2: "Cyclic Dependency detected between modules A and B"
            match = re.search(r"([\w\s]+) detected between", line)
            if match:
                smell_name = match.group(1).strip()

                # Try to get location from next line
                location = "unknown"
                if i + 1 < len(lines):
                    loc_match = re.search(r"Location: ([^\s]+)", lines[i + 1])
                    if loc_match:
                        location = loc_match.group(1).strip()

                smell = self._create_smell(smell_name, location, line, line)
                if smell:
                    smells.append(smell)

        return smells

    def _create_smell(
        self, smell_name: str, location: str, description: str, full_line: str
    ) -> Smell | None:
        """Create a Smell object from parsed data.

        Args:
            smell_name: Name of the smell (e.g., "Long Method")
            location: File location (e.g., "src/file.py:10")
            description: Full description
            full_line: Original line for severity detection

        Returns:
            Smell object or None if cannot parse
        """
        # Map smell names to categories
        category = self._map_category(smell_name)

        # Map severity
        severity = self._map_severity(full_line, smell_name)

        # Generate ID from name
        smell_id = smell_name.upper().replace(" ", "_")

        return Smell(
            id=smell_id,
            name=smell_name,
            category=category,
            severity=severity,
            location=location,
            tool=self.name,
            description=description,
        )

    def _map_category(self, smell_name: str) -> SmellCategory:
        """Map smell name to category.

        Based on PyExamine's three-layer categorization.

        Args:
            smell_name: Name of the smell

        Returns:
            SmellCategory enum value
        """
        smell_lower = smell_name.lower()

        # Architectural smells
        if any(
            keyword in smell_lower
            for keyword in ["cyclic", "dependency", "hub", "god object", "architecture"]
        ):
            return SmellCategory.ARCHITECTURAL

        # Design smells
        if any(
            keyword in smell_lower
            for keyword in ["god class", "coupling", "cohesion", "inheritance"]
        ):
            return SmellCategory.DESIGN

        # Default to implementation for code-level smells
        return SmellCategory.IMPLEMENTATION

    def _map_severity(self, text: str, smell_name: str) -> SmellSeverity:
        """Map smell to severity level.

        Checks for explicit severity in text, otherwise infers from smell type.

        Args:
            text: Full text of the smell
            smell_name: Name of the smell

        Returns:
            SmellSeverity enum value
        """
        text_lower = text.lower()

        # Check for explicit severity markers
        if "severity: high" in text_lower or "critical" in text_lower:
            return SmellSeverity.HIGH

        if "severity: medium" in text_lower or "moderate" in text_lower:
            return SmellSeverity.MEDIUM

        if "severity: low" in text_lower:
            return SmellSeverity.LOW

        # Infer from smell type
        smell_lower = smell_name.lower()

        # High severity smells
        if any(keyword in smell_lower for keyword in ["god", "cyclic", "duplicate"]):
            return SmellSeverity.HIGH

        # Medium severity smells
        if any(keyword in smell_lower for keyword in ["long", "large", "complex"]):
            return SmellSeverity.MEDIUM

        # Default to LOW
        return SmellSeverity.LOW
