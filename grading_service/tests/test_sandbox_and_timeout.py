"""Tests for restricted builtins and exec timeout."""
import pytest


@pytest.mark.parametrize("forbidden", ["open", "eval", "exec", "compile"])
def test_forbidden_builtins_unavailable_in_user_code(client, forbidden):
    code = f"def relu(x):\n    {forbidden}\n    return x"
    resp = client.post("/grade", json={"taskId": "relu", "code": code})
    assert resp.status_code == 200
    body = resp.json()
    # The function references the forbidden name only when called, so submission itself
    # succeeds at definition time. Submit code that uses it at definition time.
    code_at_def = f"_x = {forbidden}\ndef relu(x):\n    return x"
    resp2 = client.post("/grade", json={"taskId": "relu", "code": code_at_def})
    assert resp2.status_code == 200
    assert resp2.json()["error"] is not None
    assert "NameError" in resp2.json()["error"] or forbidden in resp2.json()["error"]


def test_user_code_definition_timeout(monkeypatch, app_module):
    # Override timeout to 1s and exercise via internal helper to avoid TestClient overhead
    monkeypatch.setattr(app_module, "_EXEC_TIMEOUT", 1)
    task = {"function_name": "f", "tests": []}
    code = "while True:\n    pass\n"
    # _validate_code rejects bare while; wrap inside a top-level call expression instead
    code = "def _spin():\n    while True:\n        pass\n_spin()\n"
    result = app_module._execute_tests(code, task)
    assert result.error is not None
    assert "timed out" in result.error.lower()


def test_test_code_timeout_surfaces_per_test(monkeypatch, app_module):
    monkeypatch.setattr(app_module, "_EXEC_TIMEOUT", 1)
    task = {
        "function_name": "f",
        "tests": [{"name": "infinite", "code": "while True:\n    pass\n"}],
    }
    user_code = "def f(x):\n    return x\n"
    result = app_module._execute_tests(user_code, task)
    assert result.allPassed is False
    assert len(result.results) == 1
    assert result.results[0].passed is False
    assert "timed out" in (result.results[0].error or "").lower()


def test_disallowed_import_is_rejected(client):
    code = """import os
def relu(x):
    return x
"""
    resp = client.post("/grade", json={"taskId": "relu", "code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is not None
    assert "ImportError" in body["error"]
    assert "not allowed" in body["error"]

def test_direct_restricted_import_rejects_disallowed_module(client):
    code = """_x = __import__('os')
def relu(x):
    return x
"""
    resp = client.post("/grade", json={"taskId": "relu", "code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is not None
    assert "ImportError" in body["error"]
    assert "not allowed" in body["error"]

