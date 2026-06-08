"""FastAPI grading service for torch_judge tasks."""

import logging
import signal
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path for torch_judge imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import ast
import importlib
import os
import threading
import time
from collections import defaultdict
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from torch_judge.tasks import get_task

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("grading")

app = FastAPI(title="Grading Service")

# Lock to serialize sys.stdout redirects across concurrent request threads
_stdout_lock = threading.Lock()

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Execution timeout
# ---------------------------------------------------------------------------
_EXEC_TIMEOUT = int(os.environ.get("EXEC_TIMEOUT_SEC", "30"))


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum: int, frame: Any) -> None:
    raise _TimeoutError("Execution timed out")


def _exec_with_timeout(code: str, ns: dict, timeout: int = _EXEC_TIMEOUT) -> None:
    # signal.alarm only works in the main thread. FastAPI runs sync endpoints
    # in a worker thread, so fall back to plain exec there. Timeout protection
    # still applies when called from the main thread (e.g. tests).
    import threading
    if threading.current_thread() is threading.main_thread():
        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        try:
            exec(code, ns)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
    else:
        exec(code, ns)


# ---------------------------------------------------------------------------
# Restricted builtins for user code execution
# ---------------------------------------------------------------------------
import builtins as _builtins

_SAFE_BUILTINS = {
    k: v for k, v in vars(_builtins).items()
    if k not in (
        "__import__", "open", "eval", "exec", "compile",
        "breakpoint", "exit", "quit", "input", "globals", "locals",
        "memoryview", "help",
    )
}

_ALLOWED_IMPORT_ROOTS = {"torch", "numpy", "math", "time"}


def _is_allowed_import(module_name: str) -> bool:
    root = module_name.split(".", 1)[0]
    return root in _ALLOWED_IMPORT_ROOTS


def _restricted_import(
    name: str,
    globals: dict[str, Any] | None = None,
    locals: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] | list[str] = (),
    level: int = 0,
) -> Any:
    if level != 0:
        raise ImportError("Relative imports are not allowed")
    if not _is_allowed_import(name):
        raise ImportError(f"Import of '{name}' is not allowed")
    return _builtins.__import__(name, globals, locals, fromlist, level)


_SAFE_BUILTINS["__import__"] = _restricted_import


def _safe_import_module(module_name: str) -> Any:
    if not _is_allowed_import(module_name):
        raise ImportError(f"Import of '{module_name}' is not allowed")
    return importlib.import_module(module_name)


def _safe_import_attr(module_name: str, attr_name: str) -> Any:
    module = _safe_import_module(module_name)
    try:
        return getattr(module, attr_name)
    except AttributeError as e:
        raise ImportError(f"Cannot import name '{attr_name}' from '{module_name}'") from e


class _ImportRewriter(ast.NodeTransformer):
    """Rewrite allowed import statements so user builtins do not need __import__."""

    def visit_Import(self, node: ast.Import) -> list[ast.stmt]:
        rewritten: list[ast.stmt] = []
        for alias in node.names:
            if not _is_allowed_import(alias.name):
                raise ImportError(f"Import of '{alias.name}' is not allowed")
            bound_name = alias.asname or alias.name.split(".", 1)[0]
            imported_name = alias.name if alias.asname else bound_name
            rewritten.append(
                ast.copy_location(
                    ast.Assign(
                        targets=[ast.Name(id=bound_name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="__pyre_import_module__", ctx=ast.Load()),
                            args=[ast.Constant(value=imported_name)],
                            keywords=[],
                        ),
                    ),
                    node,
                )
            )
        return rewritten

    def visit_ImportFrom(self, node: ast.ImportFrom) -> list[ast.stmt]:
        if node.module is None or node.level:
            raise ImportError("Relative imports are not allowed")
        if not _is_allowed_import(node.module):
            raise ImportError(f"Import of '{node.module}' is not allowed")

        rewritten: list[ast.stmt] = []
        for alias in node.names:
            if alias.name == "*":
                raise ImportError("Wildcard imports are not allowed")
            bound_name = alias.asname or alias.name
            rewritten.append(
                ast.copy_location(
                    ast.Assign(
                        targets=[ast.Name(id=bound_name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="__pyre_import_attr__", ctx=ast.Load()),
                            args=[
                                ast.Constant(value=node.module),
                                ast.Constant(value=alias.name),
                            ],
                            keywords=[],
                        ),
                    ),
                    node,
                )
            )
        return rewritten

# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-worker)
# ---------------------------------------------------------------------------
_GRADE_RATE_WINDOW = 60
_GRADE_RATE_MAX = int(os.environ.get("GRADE_RATE_MAX", "30"))
_grade_hits: dict[str, list[float]] = defaultdict(list)


def _is_grade_limited(ip: str) -> bool:
    now = time.monotonic()
    timestamps = [t for t in _grade_hits[ip] if now - t < _GRADE_RATE_WINDOW]
    if len(timestamps) >= _GRADE_RATE_MAX:
        _grade_hits[ip] = timestamps
        return True
    timestamps.append(now)
    _grade_hits[ip] = timestamps
    return False

# ---------------------------------------------------------------------------
# SQLite DB (user sessions + progress)
# ---------------------------------------------------------------------------

_DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "data" / "pyre.db"))


def _init_db() -> None:
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token TEXT UNIQUE,
            username TEXT UNIQUE,
            password_hash TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('todo', 'attempted', 'solved')),
            best_time_ms REAL,
            attempts INTEGER DEFAULT 0,
            solved_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, task_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            code TEXT NOT NULL,
            passed INTEGER NOT NULL,
            exec_time_ms REAL,
            submitted_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Migrate: add username column if missing (existing DBs)
    cur = conn.execute("PRAGMA table_info(users)")
    col_info = cur.fetchall()
    columns = [row[1] for row in col_info]
    if "username" not in columns:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE users RENAME TO users_old")
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token TEXT UNIQUE,
                username TEXT UNIQUE,
                password_hash TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("INSERT INTO users (id, session_token, created_at) SELECT id, session_token, created_at FROM users_old")
        conn.execute("DROP TABLE users_old")
        conn.execute("PRAGMA foreign_keys=ON")
    elif "password_hash" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    conn.commit()
    conn.close()


@app.on_event("startup")
def _on_startup() -> None:
    _init_db()
    logger.info("Grading service started (DB=%s, exec_timeout=%ds, rate_max=%d/min)", _DB_PATH, _EXEC_TIMEOUT, _GRADE_RATE_MAX)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class SubmitRequest(BaseModel):
    taskId: str
    code: str


class RunRequest(BaseModel):
    taskId: str
    code: str
    testIndices: list[int] | None = None


class TestResult(BaseModel):
    name: str
    passed: bool
    execTimeMs: float
    error: str | None = None
    output: str | None = None


class GradeResponse(BaseModel):
    passed: int
    total: int
    allPassed: bool
    results: list[TestResult]
    totalTimeMs: float
    error: str | None = None


def _format_syntax_error(e: SyntaxError) -> str:
    location = ""
    if e.lineno is not None:
        location = f" (line {e.lineno}"
        if e.offset is not None:
            location += f", column {e.offset}"
        location += ")"
    message = f"Syntax error: {e.msg}{location}"
    if e.text:
        line = e.text.rstrip()
        message += f"\n{line}"
        if e.offset is not None and e.offset > 0:
            message += f"\n{' ' * (e.offset - 1)}^"
    return message


def _validate_code(code: str) -> str | None:
    """Return an error message if code contains disallowed top-level statements."""
    allowed = (
        ast.FunctionDef, ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Import, ast.ImportFrom,
        ast.Assign, ast.AnnAssign, ast.AugAssign,
        ast.Expr,  # top-level expressions / docstrings
    )
    try:
        tree = ast.parse(code, filename="<submitted>")
    except SyntaxError as e:
        return _format_syntax_error(e)
    for node in tree.body:
        if not isinstance(node, allowed):
            return f"Only definitions and assignments are allowed at the top level (found: {type(node).__name__})"
    return None


def _execute_tests(code: str, task: dict, test_indices: list[int] | None = None, capture_output: bool = True) -> GradeResponse:
    import torch, math
    err = _validate_code(code)
    if err:
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error=err)
    user_ns: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "torch": torch,
        "Tensor": torch.Tensor,
        "nn": torch.nn,
        "F": torch.nn.functional,
        "np": __import__("numpy"),
        "math": math,
        "__pyre_import_module__": _safe_import_module,
        "__pyre_import_attr__": _safe_import_attr,
    }
    try:
        tree = ast.parse(code)
        tree = _ImportRewriter().visit(tree)
        ast.fix_missing_locations(tree)
        compiled = compile(tree, "<submitted>", "exec")
        _exec_with_timeout(compiled, user_ns)
    except SyntaxError as e:
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error=_format_syntax_error(e))
    except ImportError as e:
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error=f"ImportError: {e}")
    except _TimeoutError:
        logger.warning("User code definition timed out")
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error="Code definition timed out")
    except Exception as e:
        logger.info("User code raised at definition: %s: %s", type(e).__name__, e)
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error=f"{type(e).__name__}: {e}")

    fn_name = task.get("function_name")
    if fn_name is None:
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error="Task has no function_name defined")

    if fn_name not in user_ns:
        return GradeResponse(passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0, error=f"Function '{fn_name}' not found in submitted code")

    all_tests = task.get("tests", [])
    tests = [all_tests[i] for i in test_indices if 0 <= i < len(all_tests)] if test_indices is not None else all_tests

    if test_indices is not None and len(test_indices) > 0 and len(tests) == 0:
        return GradeResponse(
            passed=0, total=0, allPassed=False, results=[], totalTimeMs=0.0,
            error=f"All provided test indices are out of range (valid range: 0..{len(all_tests) - 1})",
        )

    results: list[TestResult] = []
    passed = 0
    total_time_ms = 0.0

    for test in tests:
        _torch = __import__("torch")
        test_ns: dict[str, Any] = {
            "torch": _torch,
            "Tensor": _torch.Tensor,
            "nn": _torch.nn,
            "F": _torch.nn.functional,
            "np": __import__("numpy"),
            "math": math,
            fn_name: user_ns[fn_name],
        }
        test_code = test["code"].replace("{fn}", fn_name)

        output = None
        if capture_output:
            with _stdout_lock:
                old_stdout = sys.stdout
                sys.stdout = captured = io.StringIO()
                try:
                    start = time.perf_counter()
                    _exec_with_timeout(test_code, test_ns)
                    exec_time_ms = (time.perf_counter() - start) * 1000
                    output = captured.getvalue() or None
                    results.append(TestResult(name=test["name"], passed=True, execTimeMs=exec_time_ms, output=output))
                    passed += 1
                except _TimeoutError:
                    exec_time_ms = (time.perf_counter() - start) * 1000
                    output = captured.getvalue() or None
                    results.append(TestResult(name=test["name"], passed=False, execTimeMs=exec_time_ms, error="Execution timed out", output=output))
                except AssertionError as e:
                    exec_time_ms = (time.perf_counter() - start) * 1000
                    output = captured.getvalue() or None
                    results.append(TestResult(name=test["name"], passed=False, execTimeMs=exec_time_ms, error=str(e), output=output))
                except Exception as e:
                    exec_time_ms = (time.perf_counter() - start) * 1000
                    output = captured.getvalue() or None
                    results.append(TestResult(name=test["name"], passed=False, execTimeMs=exec_time_ms, error=f"{type(e).__name__}: {e}", output=output))
                finally:
                    sys.stdout = old_stdout
        else:
            start = time.perf_counter()
            try:
                _exec_with_timeout(test_code, test_ns)
                exec_time_ms = (time.perf_counter() - start) * 1000
                results.append(TestResult(name=test["name"], passed=True, execTimeMs=exec_time_ms))
                passed += 1
            except _TimeoutError:
                exec_time_ms = (time.perf_counter() - start) * 1000
                results.append(TestResult(name=test["name"], passed=False, execTimeMs=exec_time_ms, error="Execution timed out"))
            except AssertionError as e:
                exec_time_ms = (time.perf_counter() - start) * 1000
                results.append(TestResult(name=test["name"], passed=False, execTimeMs=exec_time_ms, error=str(e)))
            except Exception as e:
                exec_time_ms = (time.perf_counter() - start) * 1000
                results.append(TestResult(name=test["name"], passed=False, execTimeMs=exec_time_ms, error=f"{type(e).__name__}: {e}"))
        total_time_ms += exec_time_ms

    return GradeResponse(passed=passed, total=len(results), allPassed=passed == len(results), results=results, totalTimeMs=total_time_ms)


@app.post("/grade", response_model=GradeResponse)
def grade(request: SubmitRequest, req: Request) -> GradeResponse:
    ip = (req.headers.get("x-forwarded-for") or "unknown").split(",")[0].strip()
    if _is_grade_limited(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    task = get_task(request.taskId)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{request.taskId}' not found")
    return _execute_tests(request.code, task)


@app.post("/run", response_model=GradeResponse)
def run(request: RunRequest, req: Request) -> GradeResponse:
    ip = (req.headers.get("x-forwarded-for") or "unknown").split(",")[0].strip()
    if _is_grade_limited(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    task = get_task(request.taskId)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{request.taskId}' not found")
    return _execute_tests(request.code, task, request.testIndices)



@app.get("/tasks/{task_id}/notebook")
def get_notebook(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None or not task.get("solution"):
        raise HTTPException(status_code=404, detail=f"Notebook for '{task_id}' not found")
    cells = [{"type": "code", "source": task["solution"].strip(), "role": "solution"}]
    if "explanation" in task:
        cells.append({"type": "markdown", "source": task["explanation"].strip(), "role": "explanation"})
    if "demo" in task:
        cells.append({"type": "code", "source": task["demo"].strip(), "role": "demo"})
    return {"cells": cells}


@app.get("/tasks/{task_id}/solution")
def get_solution(task_id: str) -> dict[str, str]:
    task = get_task(task_id)
    if task is None or not task.get("solution"):
        raise HTTPException(status_code=404, detail=f"Solution for '{task_id}' not found")
    return {"solution": task["solution"]}


class UserRequest(BaseModel):
    sessionToken: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ProgressEntry(BaseModel):
    status: str
    bestTimeMs: float | None = None
    attempts: int
    solvedAt: str | None = None


class SaveProgressRequest(BaseModel):
    sessionToken: str | None = None
    username: str | None = None
    taskId: str
    status: str
    execTimeMs: float | None = None
    code: str | None = None
    allPassed: bool | None = None


@app.post("/users")
def get_or_create_user(request: UserRequest) -> dict[str, int]:
    with _get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE session_token = ?", (request.sessionToken,)).fetchone()
        if row:
            return {"userId": row[0]}
        cur = conn.execute("INSERT INTO users (session_token) VALUES (?)", (request.sessionToken,))
        return {"userId": cur.lastrowid}


@app.post("/users/login")
def login(request: LoginRequest) -> dict[str, int | str]:
    import bcrypt
    username = request.username.strip()
    if not username or len(username) > 32:
        raise HTTPException(status_code=400, detail="Username must be 1-32 characters")
    if not request.password or len(request.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    with _get_db() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            uid, stored_hash = row
            if not stored_hash:
                raise HTTPException(status_code=401, detail="Account has no password set. Please contact admin.")
            if not bcrypt.checkpw(request.password.encode(), stored_hash.encode()):
                raise HTTPException(status_code=401, detail="Invalid password")
            return {"userId": uid, "username": username}
        raise HTTPException(status_code=401, detail="User not found. Please register first.")


class RegisterRequest(BaseModel):
    username: str
    password: str


@app.post("/users/register")
def register(request: RegisterRequest) -> dict[str, int | str]:
    import bcrypt
    username = request.username.strip()
    if not username or len(username) > 32:
        raise HTTPException(status_code=400, detail="Username must be 1-32 characters")
    if not request.password or len(request.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    with _get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        return {"userId": cur.lastrowid, "username": username}


@app.get("/progress/{user_id}")
def get_progress(user_id: int) -> dict[str, ProgressEntry]:
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT task_id, status, best_time_ms, attempts, solved_at FROM progress WHERE user_id = ?",
            (user_id,)
        ).fetchall()
    return {
        row[0]: ProgressEntry(status=row[1], bestTimeMs=row[2], attempts=row[3], solvedAt=row[4])
        for row in rows
    }


@app.get("/progress/by-username/{username}")
def get_progress_by_username(username: str) -> dict[str, ProgressEntry]:
    """Lookup progress by username — used by frontend api routes that already
    verified the user via the auth cookie. No password check here."""
    with _get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return {}
        user_id = row[0]
        rows = conn.execute(
            "SELECT task_id, status, best_time_ms, attempts, solved_at FROM progress WHERE user_id = ?",
            (user_id,)
        ).fetchall()
    return {
        row[0]: ProgressEntry(status=row[1], bestTimeMs=row[2], attempts=row[3], solvedAt=row[4])
        for row in rows
    }


@app.post("/progress")
def save_progress(request: SaveProgressRequest) -> dict[str, str]:
    try:
        with _get_db() as conn:
            if request.username:
                row = conn.execute("SELECT id FROM users WHERE username = ?", (request.username.strip(),)).fetchone()
            elif request.sessionToken:
                row = conn.execute("SELECT id FROM users WHERE session_token = ?", (request.sessionToken,)).fetchone()
            else:
                raise HTTPException(status_code=400, detail="username or sessionToken required")
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user_id = row[0]
            existing = conn.execute(
                "SELECT status FROM progress WHERE user_id = ? AND task_id = ?",
                (user_id, request.taskId)
            ).fetchone()
            if existing:
                existing_status = existing[0]
                if request.status == "solved":
                    # Atomic min() to avoid races when concurrent submissions arrive.
                    conn.execute(
                        """
                        UPDATE progress
                        SET status = 'solved',
                            best_time_ms = CASE
                                WHEN best_time_ms IS NULL THEN ?
                                WHEN ? IS NULL THEN best_time_ms
                                ELSE MIN(best_time_ms, ?)
                            END,
                            attempts = attempts + 1,
                            solved_at = COALESCE(solved_at, datetime('now'))
                        WHERE user_id = ? AND task_id = ?
                        """,
                        (request.execTimeMs, request.execTimeMs, request.execTimeMs, user_id, request.taskId)
                    )
                else:
                    next_status = existing_status if existing_status == "solved" and request.status in ("todo", "attempted") else request.status
                    conn.execute(
                        "UPDATE progress SET status = ?, attempts = attempts + 1 WHERE user_id = ? AND task_id = ?",
                        (next_status, user_id, request.taskId)
                    )
            else:
                if request.status == "solved":
                    conn.execute(
                        "INSERT INTO progress (user_id, task_id, status, best_time_ms, attempts, solved_at) VALUES (?, ?, ?, ?, 1, datetime('now'))",
                        (user_id, request.taskId, request.status, request.execTimeMs)
                    )
                else:
                    conn.execute(
                        "INSERT INTO progress (user_id, task_id, status, best_time_ms, attempts, solved_at) VALUES (?, ?, ?, ?, 1, NULL)",
                        (user_id, request.taskId, request.status, None)
                    )
            if request.code is not None:
                conn.execute(
                    "INSERT INTO submissions (user_id, task_id, code, passed, exec_time_ms) VALUES (?, ?, ?, ?, ?)",
                    (user_id, request.taskId, request.code, 1 if request.allPassed else 0, request.execTimeMs)
                )
    except HTTPException:
        raise
    except sqlite3.Error as e:
        logger.error("save_progress DB error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save progress")
    return {"ok": "true"}


@app.get("/submissions/{user_id}/{task_id}")
def get_submissions(user_id: int, task_id: str) -> list[dict]:
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT id, passed, exec_time_ms, submitted_at, code FROM submissions "
            "WHERE user_id = ? AND task_id = ? ORDER BY submitted_at DESC LIMIT 50",
            (user_id, task_id)
        ).fetchall()
    return [
        {"id": r[0], "passed": bool(r[1]), "execTimeMs": r[2], "submittedAt": r[3], "code": r[4]}
        for r in rows
    ]


@app.get("/submissions/by-username/{username}/{task_id}")
def get_submissions_by_username(username: str, task_id: str) -> list[dict]:
    """Lookup submission history by username — used by frontend api routes that
    already verified the user via the auth cookie. No password check here."""
    with _get_db() as conn:
        user_row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user_row:
            return []
        rows = conn.execute(
            "SELECT id, passed, exec_time_ms, submitted_at, code FROM submissions "
            "WHERE user_id = ? AND task_id = ? ORDER BY submitted_at DESC LIMIT 50",
            (user_row[0], task_id)
        ).fetchall()
    return [
        {"id": r[0], "passed": bool(r[1]), "execTimeMs": r[2], "submittedAt": r[3], "code": r[4]}
        for r in rows
    ]


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with _get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

