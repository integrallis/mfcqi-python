"""
MFCQI (Benchmark Analysis Reporting Utility) Calculator implementation.

Uses geometric mean formula from research:
(Cyclo * Cognitive * Halstead * Maintain * Dup * Doc * Security * DepSec * Secrets * Smells)^(1/n)
where each factor is normalized to [0,1] range and n is the number of metrics.

Core metrics include:
- Cyclomatic Complexity
- Cognitive Complexity
- Halstead Volume
- Maintainability Index
- Code Duplication
- Documentation Coverage
- Security (Bandit SAST)
- Dependency Security (pip-audit SCA)
- Secrets Exposure (detect-secrets)
- Code Smell Density (PyExamine + AST test smells)
"""

import logging
from pathlib import Path
from typing import Any

from mfcqi.core.file_utils import get_python_files
from mfcqi.core.paradigm_detector import ParadigmDetector
from mfcqi.metrics.code_smell import CodeSmellDensity
from mfcqi.metrics.cognitive import CognitiveComplexity
from mfcqi.metrics.cohesion import LackOfCohesionOfMethods
from mfcqi.metrics.complexity import CyclomaticComplexity, HalsteadComplexity
from mfcqi.metrics.coupling import CouplingBetweenObjects
from mfcqi.metrics.dependency_security import DependencySecurityMetric
from mfcqi.metrics.dit import DITMetric
from mfcqi.metrics.documentation import DocumentationCoverage
from mfcqi.metrics.duplication import CodeDuplication
from mfcqi.metrics.maintainability import MaintainabilityIndex
from mfcqi.metrics.mhf import MHFMetric
from mfcqi.metrics.rfc import RFCMetric
from mfcqi.metrics.secrets_exposure import SecretsExposureMetric
from mfcqi.metrics.security import SecurityMetric
from mfcqi.metrics.type_safety import TypeSafetyMetric
from mfcqi.smell_detection.ast_test_smells import ASTTestSmellDetector
from mfcqi.smell_detection.pyexamine import PyExamineDetector

logger = logging.getLogger(__name__)


class MFCQICalculator:
    """Calculates MFCQI score using geometric mean of multiple metrics."""

    def __init__(
        self,
        use_paradigm_detection: bool = True,
        include_type_safety: bool = False,  # Include type annotation coverage
    ):
        """Initialize calculator with core metrics.

        Args:
            use_paradigm_detection: Whether to use paradigm detection for metric selection
            include_type_safety: Whether to include type annotation coverage in MFCQI calculation
        """
        # Core metrics that are always included
        self.core_metrics = {
            "cyclomatic_complexity": CyclomaticComplexity(),
            "cognitive_complexity": CognitiveComplexity(),  # Understandability metric
            "halstead_volume": HalsteadComplexity(),
            "maintainability_index": MaintainabilityIndex(),
            "code_duplication": CodeDuplication(),
            "documentation_coverage": DocumentationCoverage(),
            "security": SecurityMetric(),  # Bandit SAST
            "dependency_security": DependencySecurityMetric(),  # pip-audit SCA
            "secrets_exposure": SecretsExposureMetric(),  # detect-secrets
            "code_smell_density": CodeSmellDensity(
                detectors=[
                    PyExamineDetector(),  # Production code smells (architectural/design/implementation)
                    ASTTestSmellDetector(),  # Test smells
                ]
            ),  # Multi-layer smell detection
        }

        # Complexity-dependent metrics (OO-specific)
        self.complexity_metrics = {
            "rfc": RFCMetric(),  # Response for Class
            "dit": DITMetric(),  # Depth of Inheritance Tree
            "mhf": MHFMetric(),  # Method Hiding Factor
            "cbo": CouplingBetweenObjects(),  # Coupling Between Objects
            "lcom": LackOfCohesionOfMethods(),  # Lack of Cohesion of Methods
        }

        # Build final metrics dict
        self.metrics = self.core_metrics.copy()
        if include_type_safety:
            self.metrics["type_safety"] = TypeSafetyMetric()

        self.include_type_safety = include_type_safety
        self.use_paradigm_detection = use_paradigm_detection
        self.paradigm_detector = ParadigmDetector() if use_paradigm_detection else None

        # Cache for metrics to avoid recreating them
        self._cached_metrics: dict[str, Any] | None = None
        self._cached_codebase: Path | None = None

    def calculate(self, codebase: Path) -> float:
        """Calculate MFCQI score using geometric mean formula.

        Args:
            codebase: Path to the codebase directory

        Returns:
            MFCQI score between 0.0 and 1.0
        """
        if not codebase.exists() or (not codebase.is_dir() and not codebase.is_file()):
            return 0.0

        # Check if codebase has any Python files (excluding .venv, etc.)
        py_files = get_python_files(codebase)
        if not py_files:
            return 0.0

        # Determine final metrics based on complexity analysis
        final_metrics = self._determine_applicable_metrics(codebase)

        # Extract and normalize all metrics
        normalized_scores = []

        for _metric_name, metric in final_metrics.items():
            try:
                # Extract raw metric value
                raw_value = metric.extract(codebase)

                # Normalize to [0,1] range
                normalized_value = metric.normalize(raw_value)

                # Ensure bounds
                normalized_value = max(0.0, min(1.0, normalized_value))

                normalized_scores.append(normalized_value)

            except Exception:
                # If metric fails, use 0.0 (worst score)
                normalized_scores.append(0.0)

        # Calculate geometric mean
        return self._calculate_geometric_mean(normalized_scores)

    def _determine_applicable_metrics(self, codebase: Path) -> dict[str, Any]:
        """Determine which metrics to include based on paradigm detection or complexity."""
        # Use cached metrics if same codebase
        if self._cached_codebase == codebase and self._cached_metrics is not None:
            return self._cached_metrics

        metrics = self.metrics.copy()

        # Add OO metrics based on paradigm or complexity
        if self.use_paradigm_detection and self.paradigm_detector:
            self._add_paradigm_based_metrics(codebase, metrics)
        else:
            self._add_complexity_based_metrics(codebase, metrics)

        # Cache the metrics for this codebase
        self._cached_codebase = codebase
        self._cached_metrics = metrics
        return metrics

    def _add_paradigm_based_metrics(self, codebase: Path, metrics: dict[str, Any]) -> None:
        """Add metrics based on paradigm detection."""
        try:
            if self.paradigm_detector:
                paradigm_result = self.paradigm_detector.detect_paradigm(codebase)
            else:
                return
            paradigm = paradigm_result["paradigm"]
            self._add_oo_metrics_for_paradigm(paradigm, metrics)
        except Exception:
            # Fall back to complexity-based detection
            self._add_complexity_based_metrics(codebase, metrics)

    def _add_oo_metrics_for_paradigm(self, paradigm: str, metrics: dict[str, Any]) -> None:
        """Add OO metrics based on specific paradigm."""
        oo_metrics_by_paradigm = {
            "STRONG_OO": {
                "rfc": RFCMetric(),
                "dit": DITMetric(),
                "mhf": MHFMetric(),
                "cbo": CouplingBetweenObjects(),
                "lcom": LackOfCohesionOfMethods(),
            },
            "MIXED_OO": {
                "rfc": RFCMetric(),
                "dit": DITMetric(),
                "mhf": MHFMetric(),
                "cbo": CouplingBetweenObjects(),
                "lcom": LackOfCohesionOfMethods(),
            },
            "WEAK_OO": {"rfc": RFCMetric()},
            "PROCEDURAL": {},
        }

        oo_metrics = oo_metrics_by_paradigm.get(paradigm, {})
        if oo_metrics and isinstance(oo_metrics, dict):
            metrics.update(oo_metrics)

    def _add_complexity_based_metrics(self, codebase: Path, metrics: dict[str, Any]) -> None:
        """Add OO metrics based on complexity analysis."""
        # Add all OO metrics
        metrics.update(
            {
                "rfc": RFCMetric(),
                "dit": DITMetric(),
                "mhf": MHFMetric(),
                "cbo": CouplingBetweenObjects(),
                "lcom": LackOfCohesionOfMethods(),
            }
        )

    def get_detailed_metrics(self, codebase: Path) -> dict[str, float]:
        """Get detailed breakdown of all metrics.

        Args:
            codebase: Path to the codebase directory

        Returns:
            Dictionary with metric names and their normalized scores
        """
        results = {}

        if not codebase.exists() or (not codebase.is_dir() and not codebase.is_file()):
            # Return zeros for included metrics
            for metric_name in self.metrics:
                results[metric_name] = 0.0
            results["mfcqi_score"] = 0.0
            return results

        # Determine applicable metrics (same logic as calculate method)
        applicable_metrics = self._determine_applicable_metrics(codebase)

        # Calculate each applicable metric
        for metric_name, metric in applicable_metrics.items():
            try:
                raw_value = metric.extract(codebase)
                normalized_value = metric.normalize(raw_value)
                normalized_value = max(0.0, min(1.0, normalized_value))
                results[metric_name] = normalized_value
            except Exception as e:
                import logging

                logging.warning(f"Failed to calculate metric {metric_name}: {e}")
                results[metric_name] = 0.0

        # Calculate overall MFCQI score
        results["mfcqi_score"] = self.calculate(codebase)

        return results

    def get_detailed_metrics_with_tool_outputs(self, codebase: Path) -> dict[str, Any]:
        """Get detailed metrics WITH raw tool outputs for LLM context.

        This is slower than get_detailed_metrics() as it collects actual tool data.
        Only use when generating recommendations.

        Returns:
            Dictionary with:
                - mfcqi_score: Overall score
                - metrics: Normalized scores
                - tool_outputs: Raw data from analysis tools
        """
        results = {}
        tool_outputs = {}

        if not codebase.exists() or (not codebase.is_dir() and not codebase.is_file()):
            return {"mfcqi_score": 0.0, "metrics": {}, "tool_outputs": {}}

        # Determine applicable metrics
        applicable_metrics = self._determine_applicable_metrics(codebase)

        # Calculate each metric AND collect tool outputs
        for metric_name, metric in applicable_metrics.items():
            try:
                raw_value = metric.extract(codebase)
                normalized_value = metric.normalize(raw_value)
                results[metric_name] = max(0.0, min(1.0, normalized_value))

                # Get the actual Bandit issues if available for security metric
                if (
                    metric_name == "security"
                    and hasattr(metric, "last_issues")
                    and metric.last_issues
                ):
                    tool_outputs["bandit_issues"] = metric.last_issues

                # Store raw values for context (moved outside of security check)
                if (
                    metric_name == "cyclomatic_complexity"
                    or metric_name == "halstead_volume"
                    or metric_name == "cognitive_complexity"
                ):
                    tool_outputs[f"{metric_name}_raw"] = raw_value

                    # Collect detailed function-level complexity data
                    if metric_name == "cyclomatic_complexity":
                        tool_outputs["complex_functions"] = self._get_complex_functions(codebase)

            except Exception as e:
                # Log metric extraction failure (graceful degradation to 0.0)
                logger.debug(f"Metric '{metric_name}' extraction failed: {e}. Using 0.0")
                results[metric_name] = 0.0

        # Calculate overall score
        mfcqi_score = self.calculate(codebase)

        return {"mfcqi_score": mfcqi_score, "metrics": results, "tool_outputs": tool_outputs}

    def _get_complex_functions(self, codebase: Path, limit: int = 10) -> list[dict[str, Any]]:
        """Get the most complex functions in the codebase.

        Returns list of dicts with function name, file, complexity, and line number.
        """
        try:
            import radon.complexity as rc

            from mfcqi.core.file_utils import get_python_files

            complex_functions = []

            for py_file in get_python_files(codebase):
                try:
                    content = py_file.read_text()
                    results = rc.cc_visit(content)

                    for item in results:
                        if item.complexity > 5:  # Only include moderately complex functions
                            # Determine type based on item class
                            item_type = (
                                "class" if item.__class__.__name__ == "Class" else "function"
                            )
                            complex_functions.append(
                                {
                                    "name": item.name,
                                    "file": str(py_file.relative_to(codebase)),
                                    "complexity": item.complexity,
                                    "line": item.lineno,
                                    "type": item_type,
                                }
                            )
                except Exception as e:
                    # Log file processing failure (graceful degradation, continue with other files)
                    logger.debug(f"Failed to analyze complexity for {py_file}: {e}")
                    continue

            # Sort by complexity and return top N
            complex_functions.sort(key=lambda x: x["complexity"], reverse=True)
            return complex_functions[:limit]

        except Exception as e:
            # Log failure to collect complex functions (graceful degradation)
            logger.debug(f"Failed to collect complex functions: {e}")
            return []

    def _calculate_geometric_mean(self, values: list[float]) -> float:
        """Calculate geometric mean of values with zero handling.

        Args:
            values: List of normalized metric values [0,1]

        Returns:
            Geometric mean between 0.0 and 1.0
        """
        if not values:
            return 0.0

        # Handle zeros by using a minimum threshold (e.g., 0.1)
        # This prevents any single zero metric from making the entire score zero
        min_threshold = 0.1
        adjusted_values = [max(v, min_threshold) for v in values]

        # Calculate geometric mean: (v1 * v2 * ... * vn)^(1/n)
        try:
            product = 1.0
            for value in adjusted_values:
                product *= value

            geometric_mean: float = product ** (1.0 / len(values))

            # Ensure result is in [0,1] range
            return max(0.0, min(1.0, geometric_mean))

        except (OverflowError, ZeroDivisionError, ValueError):
            return 0.0
