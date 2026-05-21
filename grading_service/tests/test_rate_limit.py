"""Tests for per-IP rate limiting on /grade."""

RELU_SOLUTION = "def relu(x):\n    return x * (x > 0).float()\n"


def test_grade_rate_limit_returns_429_after_max(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_GRADE_RATE_MAX", 2)
    app_module._grade_hits.clear()

    headers = {"x-forwarded-for": "10.0.0.1"}
    payload = {"taskId": "relu", "code": RELU_SOLUTION}

    r1 = client.post("/grade", json=payload, headers=headers)
    r2 = client.post("/grade", json=payload, headers=headers)
    r3 = client.post("/grade", json=payload, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_rate_limit_per_ip(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "_GRADE_RATE_MAX", 1)
    app_module._grade_hits.clear()

    payload = {"taskId": "relu", "code": RELU_SOLUTION}

    r_a = client.post("/grade", json=payload, headers={"x-forwarded-for": "10.0.0.1"})
    r_b = client.post("/grade", json=payload, headers={"x-forwarded-for": "10.0.0.2"})

    assert r_a.status_code == 200
    assert r_b.status_code == 200  # different IP, separate bucket
