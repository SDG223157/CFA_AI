from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ai.clients import ChatMessage, LLMClient
from app.core.file_search import FileHit, read_snippet
from app.core.tasks import Task


@dataclass(frozen=True)
class InsightsInput:
    tasks: list[Task]
    hits: list[FileHit]
    root_dir: Path


SYSTEM_PROMPT = """You are an assistant that helps a user manage daily tasks and extract insights from local files.
Be practical, concise, and action-oriented.
If you suggest file actions, describe them clearly but do not fabricate file contents beyond what is shown.
"""


def build_user_prompt(inp: InsightsInput, *, question: str) -> str:
    open_tasks = [t for t in inp.tasks if t.completed_at is None]
    done_tasks = [t for t in inp.tasks if t.completed_at is not None]

    lines: list[str] = []
    lines.append(f"Root folder: {inp.root_dir}")
    lines.append("")
    lines.append("Tasks:")
    lines.append(f"- Open: {len(open_tasks)}")
    for t in open_tasks[:20]:
        lines.append(f"  - {t.title}")
    if len(open_tasks) > 20:
        lines.append("  - ...")
    lines.append(f"- Completed (recent): {min(len(done_tasks), 10)}")
    for t in done_tasks[:10]:
        lines.append(f"  - {t.title}")

    lines.append("")
    lines.append(f"File search hits shown: {len(inp.hits)}")
    for h in inp.hits[:10]:
        rel = h.path
        try:
            rel = h.path.relative_to(inp.root_dir)
        except Exception:
            pass
        lines.append(f"- {rel}:{h.line_no}: {h.line[:200]}")
        snippet = read_snippet(h.path, h.line_no, radius=2)
        if snippet:
            lines.append("  Snippet:")
            for sline in snippet.splitlines()[:8]:
                lines.append(f"  {sline}")

    lines.append("")
    lines.append("User question:")
    lines.append(question.strip() or "Give me insights and next steps.")

    lines.append("")
    lines.append(
        "Output format:\n"
        "1) Top 5 actionable priorities for today\n"
        "2) File/data insights (if any)\n"
        "3) Suggested next searches or questions\n"
    )
    return "\n".join(lines)


def generate_insights(client: LLMClient, inp: InsightsInput, *, question: str) -> str:
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_user_prompt(inp, question=question)),
    ]
    return client.chat(messages)


