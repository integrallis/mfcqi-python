"""
Depth of Inheritance Tree (DIT) metric implementation.

DIT = Maximum inheritance path from class to root

This metric measures inheritance complexity by finding the longest
path from a class to the root of the inheritance hierarchy.
"""

import ast
from pathlib import Path
from typing import Any, Union, cast

from mfcqi.core.file_utils import get_python_files
from mfcqi.core.metric import Metric


class DITVisitor(ast.NodeVisitor):
    """AST visitor to calculate DIT for each class."""

    def __init__(self) -> None:
        self.classes: dict[str, ast.ClassDef] = {}  # class_name -> class_node
        self.inheritance_map: dict[str, str] = {}  # child_class -> parent_class
        self.dit_values: dict[str, int] = {}  # class_name -> DIT value

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition and record inheritance."""
        self.classes[node.name] = node

        # Record inheritance relationships
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.inheritance_map[node.name] = base.id

        self.generic_visit(node)

    def calculate_dit_for_class(self, class_name: str, visited: set[str] | None = None) -> int:
        """Calculate DIT for a specific class recursively."""
        if visited is None:
            visited = set()

        # Avoid infinite recursion
        if class_name in visited:
            return 0

        # If already calculated, return cached value
        if class_name in self.dit_values:
            return int(self.dit_values[class_name])

        visited.add(class_name)

        # If no parent, DIT is 0
        if class_name not in self.inheritance_map:
            self.dit_values[class_name] = 0
            return 0

        parent_class = self.inheritance_map[class_name]

        # If parent is not in our code (external inheritance), DIT is 1
        if parent_class not in self.classes:
            self.dit_values[class_name] = 1
            return 1

        # DIT is 1 + parent's DIT
        parent_dit = self.calculate_dit_for_class(parent_class, visited.copy())
        self.dit_values[class_name] = 1 + parent_dit
        return int(self.dit_values[class_name])

    def get_max_dit(self) -> int:
        """Return the maximum DIT value among all classes."""
        if not self.classes:
            return 0

        # Calculate DIT for all classes
        for class_name in self.classes:
            self.calculate_dit_for_class(class_name)

        return max(self.dit_values.values()) if self.dit_values else 0


class DITMetric(Metric):
    """Depth of Inheritance Tree (DIT) metric."""

    def extract(self, codebase: Path) -> float:
        """Extract DIT value from codebase.

        Returns the maximum DIT value among all classes in the codebase.
        """
        if not codebase.exists():
            return 0.0

        max_dit = 0.0
        py_files = get_python_files(codebase)

        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                dit_value = self.extract_from_string(content)
                max_dit = max(max_dit, dit_value)
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue

        return float(max_dit)

    def extract_from_string(self, code: str) -> int:
        """Extract DIT value from code string.

        DIT = Maximum inheritance depth among all classes
        """
        try:
            tree = ast.parse(code)
            visitor = DITVisitor()
            visitor.visit(tree)
            return visitor.get_max_dit()
        except SyntaxError:
            return 0

    def normalize(self, value: Union[float, dict[str, Any]]) -> float:
        """Normalize DIT value for Python's multi-paradigm nature.

        Python-Specific Calibration (October 2025):
        ============================================
        Recalibrated after exhaustive research (40+ sources) revealed that applying
        strict Java/C++ OOP thresholds to Python is scientifically unjustified.

        Python is fundamentally different from Java/C++ where CK metrics were developed:
        - Python is multi-paradigm: procedural/functional/OO mix
        - Python uses inheritance LESS than Java (Tempero et al. 2015)
        - "Composition over inheritance" is Python best practice (stdlib examples)
        - Duck typing provides polymorphism without inheritance

        Evidence-Based Thresholds:
        - DIT 0-3: Excellent (procedural/shallow OO) → 1.0
        - DIT 4-6: Good to Moderate (framework-appropriate) → 0.9 to 0.7
        - DIT 7-10: Moderate to Poor (getting deep) → 0.7 to 0.4
        - DIT > 10: Poor (deep hierarchy) → 0.4 to 0.0

        Validation Results:
        - click (DIT=4): 0.40 → 0.90 (+125% improvement)
          Framework-appropriate inheritance now correctly scored as excellent
        - requests (DIT≤3): Remained 1.0 (already optimal)

        Key Research Findings:
        - **Microsoft Visual Studio**: "No currently accepted standard for DIT values"
        - **Prykhodko et al. (2021)**: DIT 2-5 is "good" at class level (101 Java projects)
        - **Papamichail et al. (2022)**: 100k+ Python projects show multi-paradigm mixing
        - **Churcher & Shepperd (1995)**: DIT "not useful indicator of functional correctness"
        - **Tempero et al. (2015)**: "Inheritance used more often in Java than Python"

        Why Original CK Thresholds (DIT≥6→0.0) Were Too Strict:
        1. Python frameworks (Django, click) appropriately use inheritance
        2. Procedural/functional Python code has DIT=0 (not a defect)
        3. No Python-specific empirical data supports harsh penalties
        4. Duck typing reduces need for deep inheritance vs Java

        References:
        - Chidamber & Kemerer (1994): "A Metrics Suite for Object Oriented Design"
        - Prykhodko et al. (2021): "Statistical Evaluation of DIT Metric"
        - Papamichail et al. (2022): "Predominant Paradigms in Python Code" (arXiv:2209.01817)
        - Tempero et al. (2015): "How Do Python Programs Use Inheritance?"
        - Churcher & Shepperd (1995): "Critical Analysis of Current OO Design Metrics"
        - See docs/research.md for complete Python-specific calibration methodology
        """
        value = cast("float", value)  # This metric only returns float from extract()

        if value <= 3:
            # Procedural/shallow OO - excellent for Python
            # DIT 0-3 typical in well-designed Python code
            return 1.0
        elif value <= 6:
            # Framework-appropriate inheritance - good to moderate
            # Linear decay: DIT=4→0.9, DIT=5→0.8, DIT=6→0.7
            # Allows for framework patterns (Django CBVs, click commands, etc.)
            return 1.0 - 0.30 * (value - 3) / 3
        elif value <= 10:
            # Getting deep - moderate to poor
            # Linear decay: DIT=7→0.625, DIT=8→0.55, DIT=9→0.475, DIT=10→0.4
            # Still problematic but not catastrophic
            return 0.70 - 0.30 * (value - 6) / 4
        else:
            # Very deep - poor to critical
            # DIT=11→0.32, DIT=12→0.24, DIT=15→0.0
            # Genuinely problematic deep hierarchies
            return max(0.0, 0.40 - 0.40 * (value - 10) / 5)

    def get_weight(self) -> float:
        """Return evidence-based weight for DIT metric.

        Weight: 0.60 (REDUCED from literature weight 0.65-0.70)
        Evidence-based justification:
        - Chidamber & Kemerer (1994): Original CK metric
        - Prykhodko et al. (2021): DIT 2-5 recommended (101 Java projects)
        - BUT Churcher & Shepperd (1995): "not useful indicator of functional correctness"
        - Python-specific: Multi-paradigm mixing is normal (Papamichail 2022)
        - Reduced weight reflects weaker Python validation vs Java/C++
        - Optional metric (only applied to OO code)
        """
        return 0.6

    def get_name(self) -> str:
        """Return the name of this metric."""
        return "dit"
