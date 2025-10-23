"""
Core Metric interface for Code Quality Index.
TEMPLATE METHOD PATTERN: Defines skeleton of metric calculation algorithm.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union


class Metric(ABC):
    """Abstract base class for all quality metrics using Template Method pattern."""

    def calculate(self, codebase: Path) -> dict[str, Any]:
        """Template method defining the skeleton of metric calculation.

        This is the TEMPLATE METHOD that defines the algorithm structure.
        Subclasses implement the abstract methods to provide specific behavior.
        """
        # Step 1: Validate input
        if not self._validate_codebase(codebase):
            return self._handle_invalid_codebase()

        # Step 2: Pre-process (hook method - optional override)
        self._pre_process(codebase)

        # Step 3: Extract raw metric value (required implementation)
        raw_value = self.extract(codebase)

        # Step 4: Post-process raw value (hook method - optional override)
        processed_value = self._post_process_raw(raw_value)

        # Step 5: Normalize to [0,1] range (required implementation)
        normalized_value = self.normalize(processed_value)

        # Step 6: Apply weight
        weighted_value = normalized_value * self.get_weight()

        # Step 7: Create result with metadata
        result = {
            "metric_name": self.get_name(),
            "raw_value": raw_value,
            "processed_value": processed_value,
            "normalized_value": normalized_value,
            "weighted_value": weighted_value,
            "weight": self.get_weight(),
        }

        # Step 8: Post-calculate hook (optional override)
        self._post_calculate(result)

        return result

    def _validate_codebase(self, codebase: Path) -> bool:
        """Validate codebase exists and is a directory.

        This is a CONCRETE METHOD providing default implementation.
        Can be overridden by subclasses for specific validation.
        """
        return codebase.exists() and codebase.is_dir()

    def _handle_invalid_codebase(self) -> dict[str, Any]:
        """Handle invalid codebase scenario.

        This is a CONCRETE METHOD providing default behavior.
        """
        return {
            "metric_name": self.get_name(),
            "raw_value": 0.0,
            "processed_value": 0.0,
            "normalized_value": 0.0,
            "weighted_value": 0.0,
            "weight": self.get_weight(),
            "error": "Invalid codebase path",
        }

    def _pre_process(self, codebase: Path) -> None:
        """Hook method for pre-processing. Subclasses can override."""
        # Default implementation does nothing
        return

    def _post_process_raw(
        self, raw_value: Union[float, dict[str, Any]]
    ) -> Union[float, dict[str, Any]]:
        """Hook method for post-processing raw value. Default: no change."""
        return raw_value

    def _post_calculate(self, result: dict[str, Any]) -> None:
        """Hook method called after calculation. Subclasses can override."""
        # Default implementation does nothing
        return

    # Abstract methods that MUST be implemented by subclasses
    @abstractmethod
    def extract(self, codebase: Path) -> Union[float, dict[str, Any]]:
        """Extract raw metric value from codebase.

        This is a PRIMITIVE OPERATION in the template method pattern.
        Each subclass must provide its specific extraction logic.

        Returns:
            Either a float (simple metrics) or dict (metrics with detailed breakdowns)
        """
        pass  # pragma: no cover

    @abstractmethod
    def normalize(self, value: Union[float, dict[str, Any]]) -> float:
        """Normalize value to [0,1] range.

        This is a PRIMITIVE OPERATION in the template method pattern.
        Each subclass defines its own normalization strategy.

        Args:
            value: Either a float or dict with metric details

        Returns:
            Normalized score between 0.0 and 1.0
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_weight(self) -> float:
        """Return evidence-based weight for this metric.

        This is a PRIMITIVE OPERATION in the template method pattern.
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this metric.

        This is a PRIMITIVE OPERATION in the template method pattern.
        """
        pass  # pragma: no cover
