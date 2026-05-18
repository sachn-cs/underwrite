"""Unit tests for SDK generation script."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

_script_path = Path(__file__).resolve().parents[2] / "scripts" / "generate_sdk.py"
_spec = importlib.util.spec_from_file_location("generate_sdk", _script_path)
_generate_sdk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_generate_sdk)
generate = _generate_sdk.generate


class TestGenerateSdk:
    def test_generate_minimal_spec(self) -> None:
        spec = {
            "paths": {
                "/health": {
                    "get": {
                        "operationId": "health_check",
                        "summary": "Health check",
                        "parameters": [],
                    }
                },
                "/seed": {
                    "post": {
                        "operationId": "create_seed",
                        "summary": "Create seed",
                        "parameters": [],
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        },
                    }
                },
                "/users/{user_id}": {
                    "get": {
                        "operationId": "get_user",
                        "summary": "Get user",
                        "parameters": [
                            {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}}
                        ],
                    }
                },
            }
        }
        code = generate(spec)
        assert "class UluClient" in code
        assert "def health_check(" in code
        assert "def create_seed(" in code
        assert "body: dict[str, Any]" in code
        assert "def get_user(" in code
        assert "user_id: str" in code
        assert 'path = path.replace("{user_id}", str(user_id))' in code

    def test_cli_input_output(self) -> None:
        spec = {
            "paths": {
                "/ready": {
                    "get": {
                        "operationId": "ready_check",
                        "summary": "Ready check",
                        "parameters": [],
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "openapi.json"
            input_path.write_text(json.dumps(spec))
            output_path = Path(tmp) / "sdk.py"
            import subprocess

            result = subprocess.run(
                ["python", "scripts/generate_sdk.py", "--input", str(input_path), "--output", str(output_path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert output_path.exists()
            assert "def ready_check(" in output_path.read_text()
