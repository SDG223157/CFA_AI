from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.ai.clients import ChatMessage, LLMClient


@dataclass(frozen=True)
class TaskAgentResult:
    # Stored as JSON string. If parsing fails, this may hold plain text.
    content: str
    parsed: dict[str, Any] | None


SYSTEM = """You are an assistant that turns a user task into an actionable plan.
Return STRICT JSON only (no markdown, no backticks).
Keep it short and practical.
"""


def _schema_hint() -> str:
    return json.dumps(
        {
            "title": "string (short normalized task title)",
            "priority": "low|medium|high",
            "today_plan": ["step 1", "step 2", "step 3"],
            "suggested_file_searches": [
                {
                    "query": "string",
                    "regex": False,
                    "case_sensitive": False,
                    "why": "string",
                }
            ],
            "questions_to_ask_user": ["string"],
        },
        ensure_ascii=False,
    )


def generate_task_plan(client: LLMClient, *, task_title: str, context: str = "") -> TaskAgentResult:
    user_prompt = (
        "Create a plan for this task.\n\n"
        f"Task: {task_title.strip()}\n"
        + (f"\nContext:\n{context.strip()}\n" if context.strip() else "")
        + "\nReturn JSON matching this schema (keys required):\n"
        + _schema_hint()
    )

    out = client.chat(
        [
            ChatMessage(role="system", content=SYSTEM),
            ChatMessage(role="user", content=user_prompt),
        ]
    )

    txt = (out or "").strip()
    # Best-effort parse
    try:
        parsed = json.loads(txt)
        # Store normalized JSON (pretty) for readability
        return TaskAgentResult(content=json.dumps(parsed, ensure_ascii=False, indent=2), parsed=parsed)
    except Exception:
        return TaskAgentResult(content=txt, parsed=None)


