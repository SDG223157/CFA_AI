from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    data_dir: Path
    db_path: Path

    openai_api_key: str | None
    openai_model: str

    ollama_base_url: str
    ollama_model: str


def load_config() -> AppConfig:
    repo_root = Path(__file__).resolve().parents[1]

    root_dir = Path(os.getenv("CFA_AI_ROOT", str(repo_root))).expanduser().resolve()
    data_dir = (repo_root / ".local").resolve()
    db_path = data_dir / "tasks.sqlite3"

    return AppConfig(
        root_dir=root_dir,
        data_dir=data_dir,
        db_path=db_path,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
    )


