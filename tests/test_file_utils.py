"""Tests for file utilities."""

import tempfile
from pathlib import Path

from mfcqi.core.file_utils import get_python_files, should_analyze_file


def test_get_python_files_basic():
    """Test getting Python files from a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some Python files
        (Path(tmpdir) / "module1.py").write_text("# code")
        (Path(tmpdir) / "module2.py").write_text("# code")

        files = get_python_files(Path(tmpdir))

        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)


def test_get_python_files_excludes_venv():
    """Test that .venv and venv directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create regular Python file
        (Path(tmpdir) / "code.py").write_text("# code")

        # Create .venv directory with Python file
        venv_dir = Path(tmpdir) / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "package.py").write_text("# should be excluded")

        files = get_python_files(Path(tmpdir))

        assert len(files) == 1
        assert files[0].name == "code.py"


def test_get_python_files_excludes_pycache():
    """Test that __pycache__ directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create regular Python file
        (Path(tmpdir) / "module.py").write_text("# code")

        # Create __pycache__ directory
        cache_dir = Path(tmpdir) / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "module.cpython-38.pyc").write_text("# cache")

        files = get_python_files(Path(tmpdir))

        assert len(files) == 1
        assert "__pycache__" not in str(files[0])


def test_get_python_files_exclude_tests():
    """Test excluding test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create regular file
        (Path(tmpdir) / "module.py").write_text("# code")

        # Create test file
        (Path(tmpdir) / "test_module.py").write_text("# test")

        # Create tests directory
        tests_dir = Path(tmpdir) / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_something.py").write_text("# test")

        # Without excluding tests
        files_with_tests = get_python_files(Path(tmpdir), exclude_tests=False)
        assert len(files_with_tests) == 3

        # With excluding tests
        files_no_tests = get_python_files(Path(tmpdir), exclude_tests=True)
        assert len(files_no_tests) == 1
        assert files_no_tests[0].name == "module.py"


def test_get_python_files_single_file():
    """Single .py file path should be returned as a list with that file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        py = Path(tmpdir) / "single.py"
        py.write_text("# module\n")

        files = get_python_files(py)
        assert files == [py]


def test_get_python_files_single_file_excludes_tests():
    """Single test file should be excluded when exclude_tests=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_py = Path(tmpdir) / "test_something.py"
        test_py.write_text("# test module\n")

        files = get_python_files(test_py, exclude_tests=True)
        assert files == []

        # Create tests directory
        tests_dir = Path(tmpdir) / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_something.py").write_text("# test")

        # Without excluding tests
        files_with_tests = get_python_files(Path(tmpdir), exclude_tests=False)
        assert len(files_with_tests) == 2

        # With excluding tests
        files_no_tests = get_python_files(Path(tmpdir), exclude_tests=True)
        assert files_no_tests == []


def test_get_python_files_excludes_dot_directories():
    """Test that directories starting with . are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create regular file
        (Path(tmpdir) / "code.py").write_text("# code")

        # Create .git directory
        git_dir = Path(tmpdir) / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        (git_dir / "hook.py").write_text("# should be excluded")

        files = get_python_files(Path(tmpdir))

        assert len(files) == 1
        assert ".git" not in str(files[0])


def test_get_python_files_sorted():
    """Test that returned files are sorted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "z_module.py").write_text("# code")
        (Path(tmpdir) / "a_module.py").write_text("# code")
        (Path(tmpdir) / "m_module.py").write_text("# code")

        files = get_python_files(Path(tmpdir))

        file_names = [f.name for f in files]
        assert file_names == sorted(file_names)


def test_should_analyze_file_valid():
    """Test should_analyze_file with valid file."""
    file_path = Path("src") / "module.py"
    assert should_analyze_file(file_path) is True


def test_should_analyze_file_in_venv():
    """Test should_analyze_file excludes .venv files."""
    file_path = Path(".venv") / "lib" / "package.py"
    assert should_analyze_file(file_path) is False


def test_should_analyze_file_in_pycache():
    """Test should_analyze_file excludes __pycache__ files."""
    file_path = Path("src") / "__pycache__" / "module.cpython-38.pyc"
    assert should_analyze_file(file_path) is False


def test_should_analyze_file_in_dot_directory():
    """Test should_analyze_file excludes files in dot directories."""
    file_path = Path(".git") / "hooks" / "pre-commit.py"
    assert should_analyze_file(file_path) is False


def test_get_python_files_empty_directory():
    """Test get_python_files with empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        files = get_python_files(Path(tmpdir))
        assert files == []
