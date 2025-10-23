"""Unit tests to cover core branches in ParadigmDetector.

These specifically target branches not exercised by integration tests
so that core modules maintain 100% coverage per CONTRIBUTING.md.
"""

import ast

from mfcqi.core.paradigm_detector import ParadigmDetector, ParadigmVisitor


def test_classify_paradigm_weak_oo():
    """_classify_paradigm returns WEAK_OO for scores in [0.2, 0.4)."""
    det = ParadigmDetector()
    assert det._classify_paradigm(0.25) == "WEAK_OO"


def test_visitor_counts_multiple_inheritance():
    """ParadigmVisitor increments multiple_inheritance for classes with >1 base."""
    code = """
class A: ...
class B: ...
class C(A, B):
    pass
"""
    tree = ast.parse(code)
    visitor = ParadigmVisitor()
    visitor.visit(tree)

    assert visitor.inheritance_count == 1
    assert visitor.multiple_inheritance == 1
