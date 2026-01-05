from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.ai.clients import build_default_client
from app.ai.insights import InsightsInput, generate_insights
from app.config import load_config
from app.core.file_search import file_stats, read_snippet, search_files
from app.core.tasks import add_task, delete_tasks, init_db, list_tasks, set_task_completed


def _as_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def render_tasks(db_path: Path) -> None:
    st.subheader("Task Inbox")

    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("New task", placeholder="e.g. Review bank statement anomalies")
        submitted = st.form_submit_button("Add")
        if submitted and title.strip():
            add_task(db_path, title.strip())
            st.success("Task added.")

    colA, colB = st.columns([1, 1])
    with colA:
        include_completed = st.checkbox("Show completed", value=True)
    with colB:
        if st.button("Delete completed tasks"):
            tasks = list_tasks(db_path, include_completed=True)
            done_ids = [t.id for t in tasks if t.completed_at is not None]
            n = delete_tasks(db_path, done_ids)
            st.info(f"Deleted {n} completed task(s).")

    tasks = list_tasks(db_path, include_completed=include_completed)
    if not tasks:
        st.caption("No tasks yet.")
        return

    for t in tasks:
        checked = t.completed_at is not None
        cols = st.columns([0.08, 0.82, 0.10])
        with cols[0]:
            new_checked = st.checkbox(" ", value=checked, key=f"task_done_{t.id}")
        with cols[1]:
            st.write(t.title)
        with cols[2]:
            if st.button("🗑️", key=f"task_del_{t.id}"):
                delete_tasks(db_path, [t.id])
                st.rerun()

        if new_checked != checked:
            set_task_completed(db_path, t.id, new_checked)
            st.rerun()


def render_search(root_dir: Path) -> None:
    st.subheader("Search Files")

    query = st.text_input("Search query", placeholder="Try: invoice OR regex like \\bCFA\\b")
    c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
    with c1:
        regex = st.checkbox("Regex", value=False)
    with c2:
        case_sensitive = st.checkbox("Case sensitive", value=False)
    with c3:
        max_hits = st.slider("Max hits", min_value=20, max_value=500, value=200, step=20)

    hits: list = []
    if query.strip():
        with st.spinner("Searching..."):
            hits = search_files(
                root_dir,
                query,
                regex=regex,
                case_sensitive=case_sensitive,
                max_hits=max_hits,
            )
        st.session_state["last_hits"] = hits
    else:
        hits = st.session_state.get("last_hits", [])

    st.caption(f"Hits: {len(hits)} (root: {root_dir})")
    if not hits:
        return

    for idx, h in enumerate(hits[:200]):
        try:
            rel = h.path.relative_to(root_dir)
        except Exception:
            rel = h.path
        label = f"{rel}:{h.line_no} — {h.line[:120]}"
        with st.expander(label, expanded=(idx == 0)):
            st.code(read_snippet(h.path, h.line_no, radius=6))


def render_dashboard(db_path: Path, root_dir: Path) -> None:
    st.subheader("Insights Dashboard")

    tasks = list_tasks(db_path, include_completed=True)
    open_count = sum(1 for t in tasks if t.completed_at is None)
    done_count = sum(1 for t in tasks if t.completed_at is not None)

    c1, c2, c3 = st.columns([0.33, 0.33, 0.34])
    c1.metric("Open tasks", open_count)
    c2.metric("Completed tasks", done_count)

    with c3:
        if st.button("Refresh file stats"):
            st.session_state.pop("file_stats", None)

    if "file_stats" not in st.session_state:
        with st.spinner("Computing file stats..."):
            st.session_state["file_stats"] = file_stats(root_dir)

    st.caption("Top file types (by count)")
    st.json(dict(list(st.session_state["file_stats"].items())[:12]))

    st.divider()
    st.subheader("AI Insights (optional)")

    cfg = load_config()
    client = build_default_client(
        openai_api_key=cfg.openai_api_key,
        openai_model=cfg.openai_model,
        ollama_base_url=cfg.ollama_base_url,
        ollama_model=cfg.ollama_model,
    )
    st.caption(f"Provider: {client.name()}")

    question = st.text_area(
        "Ask for insights",
        value="What should I focus on today? Summarize any patterns from the search results and suggest next searches.",
        height=120,
    )
    hits = st.session_state.get("last_hits", [])
    max_hits_for_ai = st.slider("Include up to N hits", min_value=0, max_value=50, value=10, step=5)
    selected_hits = hits[:max_hits_for_ai] if hits else []

    if st.button("Generate insights"):
        with st.spinner("Thinking..."):
            try:
                out = generate_insights(
                    client,
                    InsightsInput(tasks=tasks, hits=selected_hits, root_dir=root_dir),
                    question=question,
                )
            except Exception as e:
                out = f"Error generating insights: {e}"
        st.text_area("Output", value=out, height=320)


def main() -> None:
    st.set_page_config(page_title="Daily Tasks + File Insights", layout="wide")
    st.title("Daily Tasks + File Insights")

    cfg = load_config()
    init_db(cfg.db_path)

    with st.sidebar:
        st.header("Settings")
        root_str = st.text_input("Root folder to search", value=str(cfg.root_dir))
        root_dir = _as_path(root_str)
        if not root_dir.exists() or not root_dir.is_dir():
            st.error("Root folder does not exist or is not a directory.")
        st.caption("Tip: set `CFA_AI_ROOT` to persist this.")

    if not root_dir.exists() or not root_dir.is_dir():
        st.stop()

    tabs = st.tabs(["Tasks", "Search", "Dashboard"])
    with tabs[0]:
        render_tasks(cfg.db_path)
    with tabs[1]:
        render_search(root_dir)
    with tabs[2]:
        render_dashboard(cfg.db_path, root_dir)


if __name__ == "__main__":
    main()


