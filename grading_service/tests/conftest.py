"""Shared fixtures for grading_service tests."""
import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """Reimport grading_service.main with a per-test temp DB and reset rate limiter."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("EXEC_TIMEOUT_SEC", "30")
    monkeypatch.setenv("GRADE_RATE_MAX", "1000")  # high default; individual tests override

    # Force reimport so module-level env reads pick up the patched values
    sys.modules.pop("grading_service.main", None)
    module = importlib.import_module("grading_service.main")
    module._grade_hits.clear()
    return module


@pytest.fixture
def client(app_module):
    """TestClient wrapping the freshly-imported app. `with` triggers startup events."""
    with TestClient(app_module.app) as c:
        yield c
