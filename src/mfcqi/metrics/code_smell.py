"""
Code Smell Density metric implementation.

Based on research recommendations from code_smells.md:
- Multi-layer detection (Architectural, Design, Implementation, Test)
- Weighted severity scoring
- De-duplication across tools
- Normalization per 1K SLOC

Key References:
===============
- PyExamine (MSR 2025): 49 metrics across three layers
- pytest-smell (2022): Test smell detection
- Designite/DPy: Architectural and design smells

"""

import logging
from pathlib import Path
from typing import Any, Union, cast

from mfcqi.core.file_utils import get_python_files
from mfcqi.core.metric import Metric
from mfcqi.smell_detection.aggregator import SmellAggregator
from mfcqi.smell_detection.detector_base import SmellDetector

logger = logging.getLogger(__name__)


class CodeSmellDensity(Metric):
    """Measures code smell density using multi-layer detection.

    Three-Layer Scoring Approach (from code_smells.md):
    ==================================================
    1. Architectural/Design smells (weight: 0.45)
       - Hardest to fix, largest long-term impact
       - Sources: Designite/DPy, PyExamine architectural layer

    2. Implementation/Code smells (weight: 0.35)
       - Moderate impact, easier to fix than architectural
       - Sources: PyExamine code layer, DPy implementation smells

    3. Test smells (weight: 0.20)
       - Impacts reliability, easier to remediate
       - Sources: pytest-smell, PyNose

    Scoring:
    ========
    - Extract: Returns weighted smell count per KLOC
    - Normalize: Converts to quality score [0,1] where higher is better
    - Lower smell density = higher quality score
    """

    def __init__(self, detectors: list[SmellDetector] | None = None):
        """Initialize with optional list of smell detectors.

        Args:
            detectors: List of SmellDetector instances.
                      If None, uses default detectors (when available).
        """
        super().__init__()
        self.detectors = detectors or []
        self.aggregator = SmellAggregator(detectors=self.detectors)

    def extract(self, codebase: Path) -> float:
        """Extract weighted smell density per 1K lines of code.

        Algorithm:
        1. Run all detectors via aggregator (auto-deduplicates)
        2. Calculate weighted counts by category
        3. Apply category weights (arch: 0.45, impl: 0.35, test: 0.20)
        4. Normalize per 1000 LOC

        Args:
            codebase: Path to analyze

        Returns:
            Weighted smell count per KLOC (higher is worse)
        """
        if not self.detectors:
            # No detectors configured = no smells detected
            return 0.0

        # Get weighted counts by category
        weighted_counts = self.aggregator.weighted_count_by_category(codebase)

        # Apply category weights from research (code_smells.md)
        category_weights = self._get_category_weights()

        total_weighted_smell_count = 0.0
        for category, count in weighted_counts.items():
            category_key = category.value  # Get string value from enum
            weight = category_weights.get(category_key, 0.35)  # Default to implementation weight
            total_weighted_smell_count += count * weight

        # Normalize per 1K LOC
        total_loc = self._count_lines_of_code(codebase)
        if total_loc == 0:
            return 0.0

        smells_per_kloc = (total_weighted_smell_count / total_loc) * 1000.0

        return smells_per_kloc

    def normalize(self, value: Union[float, dict[str, Any]]) -> float:
        """Normalize smell density to quality score [0,1].
        Higher smell density = lower quality score

        Thresholds (smells per KLOC):
        - 0: Perfect (1.0)
        - 5: Good (0.8)
        - 10: Moderate (0.6)
        - 20: Poor (0.3)
        - 50+: Very poor (0.0)

        Args:
            value: Weighted smells per KLOC

        Returns:
            Quality score [0,1] where higher is better
        """
        value = cast("float", value)  # This metric only returns float from extract()
        if value <= 0:
            return 1.0  # Perfect - no smells
        elif value >= 50:
            return 0.0  # Very poor - too many smells
        elif value <= 5:
            # 0-5: Excellent (1.0 to 0.8)
            return 1.0 - (value / 5.0) * 0.2
        elif value <= 10:
            # 5-10: Good (0.8 to 0.6)
            return 0.8 - ((value - 5) / 5.0) * 0.2
        elif value <= 20:
            # 10-20: Moderate (0.6 to 0.3)
            return 0.6 - ((value - 10) / 10.0) * 0.3
        else:
            # 20-50: Poor (0.3 to 0.0)
            return max(0.0, 0.3 - ((value - 20) / 30.0) * 0.3)

    def get_weight(self) -> float:
        """Return evidence-based weight for code smell density.

        Weight: 0.5 (moderate impact)

        Justification:
        - Code smells are indicators of design/implementation issues
        - Strong correlation with maintainability
        - Moderate impact on defect prediction (lower than complexity/coverage)
        - Research: Architectural smells have long-term impact
        - Balanced weight reflects current detection maturity

        References:
        - code_smells.md: Three-layer categorization and weights
        - PyExamine (MSR 2025): Empirical validation of smell detection
        """
        return 0.5

    def get_name(self) -> str:
        """Return the name of this metric."""
        return "Code Smell Density"

    def _get_category_weights(self) -> dict[str, float]:
        """Get category weights from research recommendations.

        Returns:
            Dictionary mapping category names to weights
        """
        return {
            "architectural": 0.45,  # Highest impact, hardest to fix
            "design": 0.45,  # Grouped with architectural
            "implementation": 0.35,  # Moderate impact
            "test": 0.20,  # Lower impact, easier to fix
        }

    def _count_lines_of_code(self, codebase: Path) -> int:
        """Count total non-blank, non-comment lines of code.

        Args:
            codebase: Path to codebase

        Returns:
            Total LOC count
        """
        py_files = get_python_files(codebase)

        total_loc = 0
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for line in lines:
                    stripped = line.strip()
                    # Count non-blank, non-comment lines
                    if stripped and not stripped.startswith("#"):
                        total_loc += 1

            except Exception as e:
                # Log file reading failure (graceful degradation, continue with other files)
                logger.debug(f"Failed to read {py_file} for LOC counting: {e}")
                continue

        return total_loc
