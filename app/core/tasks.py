from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterable
import uuid


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class TaskAI:
    id: str
    task_id: str
    created_at: datetime
    provider: str
    kind: str  # e.g. "plan"
    content: str  # JSON string (or fallback text)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              created_at TEXT NOT NULL,
              completed_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_ai (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              provider TEXT NOT NULL,
              kind TEXT NOT NULL,
              content TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integrations (
              id TEXT PRIMARY KEY,
              user_email TEXT NOT NULL,
              provider TEXT NOT NULL,
              created_at TEXT NOT NULL,
              data TEXT NOT NULL,
              UNIQUE(user_email, provider)
            )
            """
        )
        conn.commit()


def add_task(db_path: Path, title: str) -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        title=title.strip(),
        created_at=_utc_now(),
        completed_at=None,
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO tasks (id, title, created_at, completed_at) VALUES (?, ?, ?, ?)",
            (
                task.id,
                task.title,
                task.created_at.isoformat(),
                None,
            ),
        )
        conn.commit()
    return task


def list_tasks(db_path: Path, include_completed: bool = True) -> list[Task]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if include_completed:
            rows = conn.execute(
                "SELECT id, title, created_at, completed_at FROM tasks ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, created_at, completed_at FROM tasks WHERE completed_at IS NULL ORDER BY created_at DESC"
            ).fetchall()

    def parse_dt(s: str | None) -> datetime | None:
        if s is None:
            return None
        return datetime.fromisoformat(s)

    return [
        Task(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=parse_dt(row["completed_at"]),
        )
        for row in rows
    ]


def set_task_completed(db_path: Path, task_id: str, completed: bool) -> None:
    completed_at = _utc_now().isoformat() if completed else None
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE tasks SET completed_at = ? WHERE id = ?",
            (completed_at, task_id),
        )
        conn.commit()


def delete_tasks(db_path: Path, task_ids: Iterable[str]) -> int:
    ids = list(task_ids)
    if not ids:
        return 0
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            f"DELETE FROM tasks WHERE id IN ({','.join(['?'] * len(ids))})",
            ids,
        )
        conn.commit()
        return int(cur.rowcount)


def add_task_ai(db_path: Path, *, task_id: str, provider: str, kind: str, content: str) -> TaskAI:
    rec = TaskAI(
        id=str(uuid.uuid4()),
        task_id=task_id,
        created_at=_utc_now(),
        provider=provider,
        kind=kind,
        content=content,
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO task_ai (id, task_id, created_at, provider, kind, content) VALUES (?, ?, ?, ?, ?, ?)",
            (
                rec.id,
                rec.task_id,
                rec.created_at.isoformat(),
                rec.provider,
                rec.kind,
                rec.content,
            ),
        )
        conn.commit()
    return rec


def list_task_ai(db_path: Path, task_id: str, *, kind: str | None = None, limit: int = 10) -> list[TaskAI]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if kind:
            rows = conn.execute(
                "SELECT id, task_id, created_at, provider, kind, content FROM task_ai WHERE task_id = ? AND kind = ? ORDER BY created_at DESC LIMIT ?",
                (task_id, kind, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, task_id, created_at, provider, kind, content FROM task_ai WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
                (task_id, int(limit)),
            ).fetchall()

    return [
        TaskAI(
            id=row["id"],
            task_id=row["task_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            provider=row["provider"],
            kind=row["kind"],
            content=row["content"],
        )
        for row in rows
    ]


def upsert_integration(db_path: Path, *, user_email: str, provider: str, data: str) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO integrations (id, user_email, provider, created_at, data)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_email, provider) DO UPDATE SET
              data = excluded.data
            """,
            (
                str(uuid.uuid4()),
                user_email.strip().lower(),
                provider,
                _utc_now().isoformat(),
                data,
            ),
        )
        conn.commit()


def get_integration(db_path: Path, *, user_email: str, provider: str) -> str | None:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT data FROM integrations WHERE user_email = ? AND provider = ?",
            (user_email.strip().lower(), provider),
        ).fetchone()
    return row[0] if row else None


def delete_integration(db_path: Path, *, user_email: str, provider: str) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            "DELETE FROM integrations WHERE user_email = ? AND provider = ?",
            (user_email.strip().lower(), provider),
        )
        conn.commit()
        return int(cur.rowcount)


