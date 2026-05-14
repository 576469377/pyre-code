"""Tests for username login, progress save/load, and business rules."""


def _login(client, username):
    resp = client.post("/users/login", json={"username": username})
    assert resp.status_code == 200
    return resp.json()["userId"]


def test_login_creates_user_and_is_idempotent(client):
    uid_1 = _login(client, "alice")
    uid_2 = _login(client, "alice")
    assert uid_1 == uid_2


def test_login_distinct_users_get_distinct_ids(client):
    uid_a = _login(client, "alice")
    uid_b = _login(client, "bob")
    assert uid_a != uid_b


def test_login_rejects_empty_username(client):
    resp = client.post("/users/login", json={"username": "   "})
    assert resp.status_code == 400


def test_login_rejects_too_long_username(client):
    resp = client.post("/users/login", json={"username": "x" * 33})
    assert resp.status_code == 400


def test_save_and_get_progress_roundtrip(client):
    uid = _login(client, "alice")
    resp = client.post(
        "/progress",
        json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 12.5},
    )
    assert resp.status_code == 200

    prog = client.get(f"/progress/{uid}").json()
    assert "relu" in prog
    assert prog["relu"]["status"] == "solved"
    assert prog["relu"]["bestTimeMs"] == 12.5
    assert prog["relu"]["attempts"] == 1
    assert prog["relu"]["solvedAt"] is not None


def test_solved_keeps_best_time(client):
    uid = _login(client, "alice")
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 30.0})
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 10.0})
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 20.0})

    prog = client.get(f"/progress/{uid}").json()
    assert prog["relu"]["bestTimeMs"] == 10.0
    assert prog["relu"]["attempts"] == 3


def test_attempted_after_solved_stays_solved(client):
    uid = _login(client, "alice")
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 10.0})
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "attempted"})

    prog = client.get(f"/progress/{uid}").json()
    assert prog["relu"]["status"] == "solved"
    assert prog["relu"]["attempts"] == 2


def test_progress_requires_user_identity(client):
    resp = client.post("/progress", json={"taskId": "relu", "status": "solved"})
    assert resp.status_code == 400


def test_progress_unknown_user_returns_404(client):
    resp = client.post(
        "/progress",
        json={"username": "ghost", "taskId": "relu", "status": "solved"},
    )
    assert resp.status_code == 404
