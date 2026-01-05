from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".log",
    ".html",
    ".css",
    ".sql",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".local",
}


@dataclass(frozen=True)
class FileHit:
    path: Path
    line_no: int
    line: str


def iter_files(root: Path, max_files: int = 5000) -> Iterable[Path]:
    count = 0
    for p in root.rglob("*"):
        if count >= max_files:
            return
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            count += 1
            yield p


def is_probably_text(path: Path, max_bytes: int = 2048) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        data = path.open("rb").read(max_bytes)
    except Exception:
        return False
    if not data:
        return True
    # Heuristic: if it has many NUL bytes, treat as binary.
    return (data.count(b"\x00") / len(data)) < 0.01


def search_files(
    root: Path,
    query: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    max_hits: int = 200,
    max_files: int = 5000,
) -> list[FileHit]:
    query = query.strip()
    if not query:
        return []

    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(query if regex else re.escape(query), flags=flags)

    hits: list[FileHit] = []
    for path in iter_files(root, max_files=max_files):
        if len(hits) >= max_hits:
            break
        if not is_probably_text(path):
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, start=1):
                    if pattern.search(line):
                        hits.append(FileHit(path=path, line_no=i, line=line.rstrip("\n")))
                        if len(hits) >= max_hits:
                            break
        except Exception:
            continue

    return hits


def read_snippet(path: Path, center_line: int, *, radius: int = 4) -> str:
    start = max(1, center_line - radius)
    end = center_line + radius

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return ""

    out_lines: list[str] = []
    for i in range(start, min(end, len(lines)) + 1):
        prefix = ">>" if i == center_line else "  "
        out_lines.append(f"{prefix} {i:>5}: {lines[i - 1].rstrip()}")
    return "\n".join(out_lines)


def file_stats(root: Path, max_files: int = 5000) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in iter_files(root, max_files=max_files):
        ext = path.suffix.lower() or "<none>"
        counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


