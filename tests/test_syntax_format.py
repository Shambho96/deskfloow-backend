import sys
import subprocess
import py_compile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_all_python_syntax():
    """Validates that all Python files in app/ compile without syntax or indentation errors."""
    app_dir = REPO_ROOT / "app"
    python_files = list(app_dir.rglob("*.py"))
    assert len(python_files) > 0, "No Python files found in app directory"

    errors = []
    for py_file in python_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"{py_file.name}: {e.msg}")

    assert not errors, f"Syntax errors found:\n" + "\n".join(errors)


def test_ruff_format_check():
    """Validates that all Python files in app/ conform to the Ruff code formatter."""
    res = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "app/"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert res.returncode == 0, (
        f"Code formatting check failed:\n{res.stdout}\n{res.stderr}\nRun 'ruff format app/' to fix."
    )


def test_ruff_linter_check():
    """Validates that all Python files in app/ pass the configured Ruff linter."""
    res = subprocess.run([sys.executable, "-m", "ruff", "check", "app/"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"Ruff linting failed:\n{res.stdout}\n{res.stderr}"


def test_app_and_graphql_import():
    """Validates that the FastAPI application and GraphQL schema load cleanly without import errors."""
    from app.main import app
    from app.graphql.schema import schema
    from app.db.base import Base

    assert app is not None
    assert schema is not None
    assert Base is not None
