"""Security audit test scanning for potential SQL injection vectors.

Item 135 from production roadmap.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2] / "ulu"

# Patterns that suggest raw SQL string interpolation or concatenation
_SQL_INJECTION_PATTERNS = [
    re.compile(r'f["\']\s*SELECT\s+.*\{.*\}', re.IGNORECASE),
    re.compile(r'f["\']\s*INSERT\s+INTO\s+.*\{.*\}', re.IGNORECASE),
    re.compile(r'f["\']\s*UPDATE\s+.*\{.*\}', re.IGNORECASE),
    re.compile(r'f["\']\s*DELETE\s+FROM\s+.*\{.*\}', re.IGNORECASE),
    re.compile(r'["\']\s*SELECT\s+.*\+\s*["\']', re.IGNORECASE),
    re.compile(r'["\']\s*INSERT\s+INTO\s+.*\+\s*["\']', re.IGNORECASE),
    re.compile(r'["\']\s*UPDATE\s+.*\+\s*["\']', re.IGNORECASE),
    re.compile(r'["\']\s*DELETE\s+FROM\s+.*\+\s*["\']', re.IGNORECASE),
]


def _is_safe_call(node: ast.AST) -> bool:
    """Heuristic: text().bindparams() or text().params() calls are safe."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"bindparams", "params"}:
            return True
    return False


def _check_ast_for_text_call(sql_expr: ast.expr) -> bool:
    """Returns True if the SQL expression is wrapped in sqlalchemy.text() with safe parameters."""
    if isinstance(sql_expr, ast.Call):
        func = sql_expr.func
        if isinstance(func, ast.Attribute) and func.attr == "text":
            return True
        if isinstance(func, ast.Name) and func.id == "text":
            return True
    return False


def _scan_file(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    issues: list[str] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for pattern in _SQL_INJECTION_PATTERNS:
            if pattern.search(line):
                issues.append(f"{path}:{lineno}: suspicious SQL interpolation: {line.strip()}")
    # AST-level checks for execute() / executemany() calls with raw strings
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in {"execute", "executemany"}:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        sql = arg.value.strip()
                        if sql.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
                            issues.append(f"{path}:{node.lineno}: raw SQL string passed to execute()")
                    elif isinstance(arg, ast.JoinedStr):
                        issues.append(f"{path}:{node.lineno}: f-string passed to execute()")
                    elif isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                        issues.append(f"{path}:{node.lineno}: string concatenation passed to execute()")
    return issues


class TestSqlInjectionAudit:
    def test_no_sql_injection_vectors(self) -> None:
        issues: list[str] = []
        for py_file in PROJECT_ROOT.rglob("*.py"):
            issues.extend(_scan_file(py_file))
        if issues:
            pytest.fail("Potential SQL injection vectors found:\n" + "\n".join(issues))
