"""Tests for username/password auth, progress save/load, and business rules."""


def _register(client, username, password="testpass123"):
    resp = client.post("/users/register", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["userId"]


def _login(client, username, password="testpass123"):
    resp = client.post("/users/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["userId"]


def test_register_creates_user(client):
    uid = _register(client, "alice")
    assert isinstance(uid, int)


def test_login_after_register_returns_same_id(client):
    uid_1 = _register(client, "alice")
    uid_2 = _login(client, "alice")
    assert uid_1 == uid_2


def test_register_distinct_users_get_distinct_ids(client):
    uid_a = _register(client, "alice")
    uid_b = _register(client, "bob")
    assert uid_a != uid_b


def test_register_rejects_empty_username(client):
    resp = client.post("/users/register", json={"username": "   ", "password": "testpass"})
    assert resp.status_code == 400


def test_register_rejects_too_long_username(client):
    resp = client.post("/users/register", json={"username": "x" * 33, "password": "testpass"})
    assert resp.status_code == 400


def test_register_rejects_short_password(client):
    resp = client.post("/users/register", json={"username": "alice", "password": "x"})
    assert resp.status_code == 400


def test_register_rejects_duplicate_username(client):
    _register(client, "alice")
    resp = client.post("/users/register", json={"username": "alice", "password": "testpass"})
    assert resp.status_code == 409


def test_login_with_wrong_password_fails(client):
    _register(client, "alice", password="correct123")
    resp = client.post("/users/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user_fails(client):
    resp = client.post("/users/login", json={"username": "ghost", "password": "anything"})
    assert resp.status_code == 401


def test_save_and_get_progress_roundtrip(client):
    uid = _register(client, "alice")
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


def test_get_progress_by_username(client):
    _register(client, "alice")
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 5.0})
    prog = client.get("/progress/by-username/alice").json()
    assert prog["relu"]["status"] == "solved"


def test_solved_keeps_best_time(client):
    uid = _register(client, "alice")
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 30.0})
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 10.0})
    client.post("/progress", json={"username": "alice", "taskId": "relu", "status": "solved", "execTimeMs": 20.0})

    prog = client.get(f"/progress/{uid}").json()
    assert prog["relu"]["bestTimeMs"] == 10.0
    assert prog["relu"]["attempts"] == 3


def test_attempted_after_solved_stays_solved(client):
    uid = _register(client, "alice")
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
