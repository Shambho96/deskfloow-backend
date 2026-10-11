#!/usr/bin/env python3
"""
DeskFlow Backend Command Runner
Package.json-style script runner for the FastAPI backend.

Usage:
    python run.py dev          # Start uvicorn development server
    python run.py run          # Alias for dev
    python run.py migrate      # Apply database migrations (alembic upgrade head)
    python run.py makemigrations "message" # Auto-generate migration
    python run.py rollback     # Revert last migration (alembic downgrade -1)
    python run.py check-db     # Test database connectivity & latency
    python run.py test         # Run pytest test suite
"""

import sys
import subprocess
from typing import Dict, Tuple

# Configuration of available scripts (similar to package.json "scripts")
SCRIPTS: Dict[str, Tuple[str, str]] = {
    "dev": (
        f'"{sys.executable}" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000',
        "Start FastAPI server with hot-reload on http://localhost:8000"
    ),
    "run": (
        f'"{sys.executable}" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000',
        "Alias for 'dev'"
    ),
    "migrate": (
        f'"{sys.executable}" -m alembic upgrade head',
        "Apply all database migrations (alembic upgrade head)"
    ),
    "makemigrations": (
        f'"{sys.executable}" -m alembic revision --autogenerate -m',
        "Auto-generate migration script (Usage: python run.py makemigrations \"description\")"
    ),
    "rollback": (
        f'"{sys.executable}" -m alembic downgrade -1',
        "Roll back the last migration step (alembic downgrade -1)"
    ),
    "check-db": (
        f'"{sys.executable}" -m app.core.db_check',
        "Test database connection and measure latency"
    ),
    "test": (
        f'"{sys.executable}" -m pytest',
        "Run automated tests with pytest"
    )
}

def print_help():
    print("\n" + "=" * 65)
    print(" DeskFlow Backend Scripts (package.json style)")
    print("=" * 65)
    print(" Usage: python run.py <command> [extra arguments]\n")
    print(f" {'Command':<18} {'Description'}")
    print(" " + "-" * 62)
    for cmd, (_, desc) in SCRIPTS.items():
        print(f"  {cmd:<17} {desc}")
    print("=" * 65 + "\n")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    command = sys.argv[1].lower()
    extra_args = sys.argv[2:]

    if command not in SCRIPTS:
        print(f"\n[ERROR] Unknown command: '{command}'")
        print_help()
        sys.exit(1)

    cmd_template, _ = SCRIPTS[command]
    
    # Append any additional flags or arguments passed by the user
    if extra_args:
        # Wrap string args containing spaces with quotes
        sanitized_args = [f'"{a}"' if " " in a and not (a.startswith('"') and a.endswith('"')) else a for a in extra_args]
        full_command = f"{cmd_template} {' '.join(sanitized_args)}"
    else:
        full_command = cmd_template

    print(f"\n> DeskFlow: {full_command}\n", flush=True)

    try:
        # Run using shell so Windows terminal handles signals and reload cleanly
        exit_code = subprocess.call(full_command, shell=True)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Process stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
