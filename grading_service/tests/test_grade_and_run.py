"""End-to-end tests for /grade and /run using the relu task."""

RELU_SOLUTION = "def relu(x):\n    return x * (x > 0).float()\n"


def test_grade_correct_solution_passes_all(client):
    resp = client.post("/grade", json={"taskId": "relu", "code": RELU_SOLUTION})
    assert resp.status_code == 200
    body = resp.json()
    assert body["allPassed"] is True
    assert body["passed"] == body["total"] > 0
    assert body["error"] is None


def test_grade_accepts_frontend_starter_imports(client):
    code = """import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

def relu(x):
    return F.relu(x)
"""
    resp = client.post("/grade", json={"taskId": "relu", "code": code})
    assert resp.status_code == 200
    body = resp.json()
    assert body["allPassed"] is True
    assert body["error"] is None


def test_run_accepts_nn_module_user_code(client):
    code = """import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class MyDropout(nn.Module):
    def __init__(self, p=0.5):
        super().__init__()
        self.p = p

    def forward(self, x):
        if not self.training or self.p == 0:
            return x
        mask = (torch.rand_like(x) > self.p).float()
        return x * mask / (1 - self.p)
"""
    resp = client.post(
        "/run",
        json={"taskId": "dropout", "code": code, "testIndices": [1]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allPassed"] is True
    assert body["error"] is None


def test_grade_missing_function_returns_error(client):
    resp = client.post("/grade", json={"taskId": "relu", "code": "def other(x): return x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["allPassed"] is False
    assert "relu" in (body["error"] or "")


def test_grade_syntax_error_surfaces(client):
    resp = client.post("/grade", json={"taskId": "relu", "code": "def relu(:\n  return x"})
    assert resp.status_code == 200
    assert "Syntax error" in (resp.json()["error"] or "")


def test_grade_unknown_task_returns_404(client):
    resp = client.post("/grade", json={"taskId": "no_such_task", "code": "def f(): pass"})
    assert resp.status_code == 404


def test_run_with_test_indices_runs_subset(client):
    resp = client.post(
        "/run",
        json={"taskId": "relu", "code": RELU_SOLUTION, "testIndices": [0]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["allPassed"] is True
