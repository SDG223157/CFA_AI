from __future__ import annotations

from pathlib import Path

import os
import streamlit as st

from app.ai.clients import build_default_client
from app.ai.insights import InsightsInput, generate_insights
from app.ai.task_agent import generate_task_plan
from app.auth.google_oauth import (
    build_auth_url,
    exchange_code_for_token,
    fetch_userinfo,
    is_allowed,
    load_google_oauth_config,
    new_state,
    sign_state,
    verify_state,
)
from app.config import load_config
from app.core.file_search import file_stats, read_snippet, search_files
from app.core.settings import AppSettings, load_settings, save_settings
from app.core.tasks import (
    add_task,
    add_task_ai,
    delete_tasks,
    init_db,
    list_task_ai,
    list_tasks,
    set_task_completed,
)


def _as_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def _qp_first(v):
    if v is None:
        return None
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _require_login_if_configured() -> dict | None:
    """
    If Google OAuth is configured, require login and return the userinfo dict.
    If not configured, return None and allow access (useful for local dev).
    """
    gcfg = load_google_oauth_config()
    if gcfg is None:
        return None

    user = st.session_state.get("user")
    if isinstance(user, dict) and user.get("email"):
        return user

    qp = st.query_params
    code = _qp_first(qp.get("code"))
    state = _qp_first(qp.get("state"))
    err = _qp_first(qp.get("error"))
    if err:
        st.error(f"Google login error: {err}")

    if code and state:
        # Verify state without relying on Streamlit session persistence (Coolify/proxies can break it).
        secret = (os.getenv("APP_AUTH_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
        ok = verify_state(state=state, secret=secret) if secret else False
        if not ok:
            # Fallback: legacy session-based state
            expected_state = st.session_state.get("oauth_state")
            ok = bool(expected_state and state == expected_state)

        if not ok:
            st.error("Invalid OAuth state. Please try logging in again.")
        else:
            try:
                token = exchange_code_for_token(gcfg, code=code)
                access_token = token.get("access_token")
                if not access_token:
                    raise RuntimeError("Missing access_token from Google token response.")
                info = fetch_userinfo(access_token=str(access_token))
                email = str(info.get("email", "")).strip()
                if not is_allowed(gcfg, email=email):
                    st.error("Access denied: your Google account is not allowed.")
                else:
                    st.session_state["user"] = info
                    st.query_params.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")

    st.title("Daily Tasks + File Insights")
    st.subheader("Login required")
    st.caption("Sign in with Google to access the dashboard.")

    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = new_state()
    # Prefer stateless signed state token so redirects work even if session changes.
    secret = (os.getenv("APP_AUTH_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    state_out = sign_state(secret=secret) if secret else st.session_state["oauth_state"]
    login_url = build_auth_url(gcfg, state=state_out)
    st.link_button("Login with Google", login_url, type="primary")

    st.info(
        "Google Console setup: add this as an Authorized redirect URI:\n"
        f"- {gcfg.redirect_uri}"
    )
    st.stop()


def render_tasks(db_path: Path) -> None:
    st.subheader("Task Inbox")

    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("New task", placeholder="e.g. Review bank statement anomalies")
        auto_plan = st.checkbox("Auto-generate AI plan on add", value=False)
        submitted = st.form_submit_button("Add")
        if submitted and title.strip():
            t = add_task(db_path, title.strip())
            st.success("Task added.")
            if auto_plan:
                cfg = load_config()
                client = build_default_client(
                    openai_api_key=cfg.openai_api_key,
                    openai_model=cfg.openai_model,
                    openrouter_api_key=cfg.openrouter_api_key,
                    openrouter_model=cfg.openrouter_model,
                    openrouter_base_url=cfg.openrouter_base_url,
                    ollama_base_url=cfg.ollama_base_url,
                    ollama_model=cfg.ollama_model,
                )
                try:
                    with st.spinner("Generating AI plan..."):
                        res = generate_task_plan(client, task_title=t.title)
                    add_task_ai(db_path, task_id=t.id, provider=client.name(), kind="plan", content=res.content)
                except Exception as e:
                    msg = f"AI plan failed: {e}"
                    st.error(msg)
                    add_task_ai(db_path, task_id=t.id, provider=client.name(), kind="plan_error", content=msg)

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

    st.divider()
    cfg = load_config()
    client = build_default_client(
        openai_api_key=cfg.openai_api_key,
        openai_model=cfg.openai_model,
        openrouter_api_key=cfg.openrouter_api_key,
        openrouter_model=cfg.openrouter_model,
        openrouter_base_url=cfg.openrouter_base_url,
        ollama_base_url=cfg.ollama_base_url,
        ollama_model=cfg.ollama_model,
    )
    st.caption(f"AI provider for task actions: {client.name()}")
    if st.button("Generate AI plan for all open tasks"):
        open_tasks = [t for t in tasks if t.completed_at is None]
        failures = 0
        with st.spinner(f"Generating plans for {len(open_tasks)} task(s)..."):
            for t in open_tasks[:50]:
                try:
                    res = generate_task_plan(client, task_title=t.title)
                    add_task_ai(db_path, task_id=t.id, provider=client.name(), kind="plan", content=res.content)
                except Exception as e:
                    failures += 1
                    msg = f"AI plan failed: {e}"
                    add_task_ai(db_path, task_id=t.id, provider=client.name(), kind="plan_error", content=msg)
        st.success(f"Done. Failures: {failures}")
        st.rerun()

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

        # AI section
        with st.expander("AI for this task", expanded=False):
            if st.button("Generate AI plan", key=f"ai_plan_{t.id}"):
                try:
                    with st.spinner("Generating plan..."):
                        res = generate_task_plan(client, task_title=t.title)
                    add_task_ai(db_path, task_id=t.id, provider=client.name(), kind="plan", content=res.content)
                except Exception as e:
                    msg = f"AI plan failed: {e}"
                    st.error(msg)
                    add_task_ai(db_path, task_id=t.id, provider=client.name(), kind="plan_error", content=msg)
                st.rerun()

            plans = list_task_ai(db_path, t.id, kind="plan", limit=3)
            if not plans:
                st.caption("No AI plan yet.")
            else:
                latest = plans[0]
                st.caption(f"Latest plan ({latest.provider}) @ {latest.created_at.isoformat(timespec='seconds')}")
                st.code(latest.content)

                # Optional: run suggested searches from the JSON
                try:
                    import json as _json

                    parsed = _json.loads(latest.content)
                    suggested = parsed.get("suggested_file_searches", [])
                except Exception:
                    suggested = []

                if suggested:
                    st.caption("Run a suggested file search (uses the Search tab root folder)")
                    choices = [f"{s.get('query','')}" for s in suggested if isinstance(s, dict)]
                    pick = st.selectbox("Suggested search", options=choices, key=f"suggest_pick_{t.id}")
                    if st.button("Copy to Search tab", key=f"run_suggest_{t.id}"):
                        st.session_state["search_query"] = pick
                        st.session_state["force_search_run"] = True
                        st.info("Copied. Click the Search tab to run it.")


def render_search(root_dir: Path) -> None:
    st.subheader("Search Files")

    query = st.text_input(
        "Search query",
        key="search_query",
        placeholder="Try: invoice OR regex like \\bCFA\\b",
    )
    c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
    with c1:
        regex = st.checkbox("Regex", value=False)
    with c2:
        case_sensitive = st.checkbox("Case sensitive", value=False)
    with c3:
        max_hits = st.slider("Max hits", min_value=20, max_value=500, value=200, step=20)

    hits: list = []
    force_run = bool(st.session_state.pop("force_search_run", False))
    if query.strip() and (force_run or "last_hits" not in st.session_state):
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
        openrouter_api_key=cfg.openrouter_api_key,
        openrouter_model=cfg.openrouter_model,
        openrouter_base_url=cfg.openrouter_base_url,
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
    user = _require_login_if_configured()
    st.title("Daily Tasks + File Insights")

    cfg = load_config()
    init_db(cfg.db_path)
    settings = load_settings(cfg.data_dir)

    with st.sidebar:
        st.header("Settings")
        if user:
            email = str(user.get("email", "")).strip()
            name = str(user.get("name", "") or user.get("given_name", "") or "").strip()
            label = name if name else email
            if label:
                st.caption(f"Signed in as: {label}")
            if st.button("Logout"):
                st.session_state.pop("user", None)
                st.session_state.pop("oauth_state", None)
                st.query_params.clear()
                st.rerun()
        default_root = settings.active_root_dir or str(cfg.root_dir)
        root_str = st.text_input("Root folder to search", value=default_root)
        root_dir = _as_path(root_str)
        if not root_dir.exists() or not root_dir.is_dir():
            st.error("Root folder does not exist or is not a directory.")
        else:
            if root_str != settings.active_root_dir:
                save_settings(cfg.data_dir, AppSettings(active_root_dir=root_str))
        st.caption("Tip: set `CFA_AI_ROOT` to persist this.")

    if not root_dir.exists() or not root_dir.is_dir():
        st.stop()

    tabs = st.tabs(["Tasks", "Search", "Dashboard", "Data Sources"])
    with tabs[0]:
        render_tasks(cfg.db_path)
    with tabs[1]:
        render_search(root_dir)
    with tabs[2]:
        render_dashboard(cfg.db_path, root_dir)
    with tabs[3]:
        st.subheader("Data Sources")
        st.markdown(
            "Use this to point the app at different folders (including mounted cloud drives). "
            "The active search root is controlled by the sidebar **Root folder to search**."
        )

        st.divider()
        st.subheader("Google Drive (recommended: mount into the container)")
        st.markdown(
            "For production, the simplest and most reliable way is to **mount Google Drive** into your Coolify app "
            "(e.g. via `rclone mount`) and then set the sidebar root to that mount path.\n\n"
            "Example paths you might use:\n"
            "- `/mnt/gdrive` (if you mount there)\n"
            "- `/data/gdrive` (if you mount there)\n\n"
            "Then set `CFA_AI_ROOT` (or use the sidebar) to that path."
        )

        st.divider()
        st.subheader("MCP (Model Context Protocol) connectors")
        st.markdown(
            "Yes, we can connect MCP servers (e.g. a Google Drive MCP server) so the app can browse/search without mounting.\n\n"
            "To wire this correctly, I need one detail: **what MCP transport are you using?**\n"
            "- `stdio` (local process) or\n"
            "- `HTTP/SSE` (remote URL)\n\n"
            "Reply with the MCP server you want to use (name/link) and the transport, and I’ll implement the connector."
        )


if __name__ == "__main__":
    main()


