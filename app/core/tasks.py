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


