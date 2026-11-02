#!/usr/bin/env python3
"""
DeskFlow Backend - Syntax Checker and Formatter Test Runner
Checks Python syntax compilation and code formatting for Git pre-commit hooks and CI.
"""

import sys
import os
import subprocess
import py_compile
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_staged_python_files(repo_root: Path) -> list[str]:
    """Retrieves list of staged python files in git."""
    try:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "*.py"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
        files = [line.strip() for line in res.stdout.splitlines() if line.strip().endswith(".py")]
        # Filter existing files
        return [f for f in files if (repo_root / f).is_file()]
    except Exception:
        return []


def get_all_python_files(repo_root: Path) -> list[str]:
    """Finds all Python files in the app directory."""
    app_dir = repo_root / "app"
    return [str(p.relative_to(repo_root)) for p in app_dir.rglob("*.py") if p.is_file()]


def check_syntax(files: list[str], repo_root: Path) -> bool:
    """Verifies that all files compile without syntax errors using py_compile."""
    print(f"{CYAN}[*] Checking Python syntax on {len(files)} file(s)...{RESET}")
    has_error = False

    for rel_path in files:
        full_path = repo_root / rel_path
        try:
            py_compile.compile(str(full_path), doraise=True)
        except py_compile.PyCompileError as e:
            print(f"{RED}  [FAIL] Syntax Error in {rel_path}:{RESET}")
            print(f"{RED}         {e.msg}{RESET}")
            has_error = True

    if not has_error:
        print(f"{GREEN}  [PASS] Syntax check passed for all {len(files)} files.{RESET}")
    return not has_error


def run_ruff_check(files: list[str], repo_root: Path) -> bool:
    """Runs ruff lint/syntax check."""
    print(f"{CYAN}[*] Running Ruff lint & syntax checks...{RESET}")
    cmd = [sys.executable, "-m", "ruff", "check"] + files
    res = subprocess.run(cmd, cwd=repo_root)
    if res.returncode == 0:
        print(f"{GREEN}  [PASS] Ruff linter passed.{RESET}")
        return True
    else:
        print(f"{RED}  [FAIL] Ruff linter found issues.{RESET}")
        return False


def run_ruff_format(files: list[str], repo_root: Path, auto_fix: bool = False) -> bool:
    """Runs ruff format check or auto-formatting."""
    if auto_fix:
        print(f"{CYAN}[*] Formatting {len(files)} file(s) with Ruff...{RESET}")
        cmd = [sys.executable, "-m", "ruff", "format"] + files
        res = subprocess.run(cmd, cwd=repo_root)
        return res.returncode == 0
    else:
        print(f"{CYAN}[*] Testing code formatting on {len(files)} file(s)...{RESET}")
        cmd = [sys.executable, "-m", "ruff", "format", "--check"] + files
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"{GREEN}  [PASS] Formatter test passed (all files conform to style).{RESET}")
            return True
        else:
            print(f"{RED}  [FAIL] Formatter test failed: files require formatting.{RESET}")
            print(
                f"{YELLOW}         Run 'python scripts/check_syntax_and_format.py --fix' or 'ruff format' to fix automatically.{RESET}"
            )
            return False


def main():
    repo_root = Path(__file__).resolve().parent.parent
    auto_fix = "--fix" in sys.argv
    check_all = "--all" in sys.argv or "-a" in sys.argv

    staged = get_staged_python_files(repo_root)

    if staged and not check_all:
        files = staged
        print(f"{BOLD}Running pre-commit check on {len(files)} staged file(s)...{RESET}")
    else:
        files = get_all_python_files(repo_root)
        print(f"{BOLD}Running syntax & formatter test on {len(files)} app file(s)...{RESET}")

    if not files:
        print(f"{GREEN}No Python files to check.{RESET}")
        sys.exit(0)

    # 1. Syntax Compilation Check
    syntax_ok = check_syntax(files, repo_root)

    # 2. Ruff Linter & Syntax Check
    linter_ok = run_ruff_check(files, repo_root)

    # 3. Formatter Test
    format_ok = run_ruff_format(files, repo_root, auto_fix=auto_fix)

    if auto_fix and not format_ok:
        # Re-add formatted files if in git staged mode
        if staged:
            subprocess.run(["git", "add"] + staged, cwd=repo_root)
        format_ok = True

    if syntax_ok and linter_ok and format_ok:
        print(f"\n{GREEN}{BOLD}[OK] ALL SYNTAX AND FORMATTER CHECKS PASSED SUCCESSFULLY!{RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{RED}{BOLD}[ERROR] COMMIT REJECTED: Please resolve the errors above before committing.{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
