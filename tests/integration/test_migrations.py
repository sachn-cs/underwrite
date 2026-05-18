"""Tests for Alembic migration scripts.

Item 7 from production roadmap.
"""

from __future__ import annotations

import subprocess
import sys


def test_offline_sql_generation():
    """Verifies migrations compile to valid PostgreSQL DDL in offline mode."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        cwd="/Users/sachin/repo/unsecured-lending-underwriting",
    )
    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE users" in result.stdout
    assert "CREATE TABLE loans" in result.stdout
    assert "CREATE TABLE sponsor_edges" in result.stdout
