## Daily Tasks + File Insights (AI Dashboard)

A local app to capture daily tasks, search your files/data, and generate insights with an optional AI layer.

### What you get
- **Task inbox**: add tasks quickly; mark done; persistence on disk
- **File search**: search within a chosen root folder; preview file snippets
- **Insights dashboard**: lightweight stats + optional AI summary over selected results
- **Task Agent**: generate an AI plan + suggested file searches for each task (stored in SQLite)

### Setup
Create and activate a virtualenv, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
streamlit run app/main.py
```

### Deploy on Coolify (Dockerfile)
- **Build Pack**: Dockerfile
- **Dockerfile Location**: `/Dockerfile`
- **Exposed Port**: `8501` (recommended; Streamlit default)
- **Environment Variables** (set in Coolify):
  - `PORT=8501`
  - `OPENROUTER_API_KEY` (required for your model)
  - `OPENROUTER_MODEL=qwen/qwen2.5-vl-7b-instruct`
  - `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
  - (Optional) Google Login:
    - `APP_BASE_URL=https://your-domain` (must match the public domain)
    - `GOOGLE_CLIENT_ID=...`
    - `GOOGLE_CLIENT_SECRET=...`
    - `APP_AUTH_SECRET=...` (recommended; stabilizes OAuth state across redirects/restarts)
    - Google Console **Authorized redirect URI** must be: `APP_BASE_URL/` (note the trailing slash)
  - Optional: `CFA_AI_ROOT` (inside the container; typically leave default unless you mount data)
- **Persistent Storage** (recommended):
  - Mount a volume to `/app/.local` to persist `tasks.sqlite3` across deploys

### Connect Google Drive (Claude-style)
In the **Data Sources** tab, you can **Connect Google Drive**. This will prompt you for the additional scope:
- `https://www.googleapis.com/auth/drive.readonly`

After connecting, you can search Drive, select a file, and click **Analyze selected file with AI**.

Notes:
- The app stores a **Drive refresh token** in SQLite (`/app/.local/tasks.sqlite3`). Keep that volume private.
- If Google doesn’t return a `refresh_token`, revoke access at `https://myaccount.google.com/permissions` and reconnect.

### Using the Task Agent
In the **Tasks** tab:
- Click **“Generate AI plan”** on a task (or **“Generate AI plan for all open tasks”**).
- The latest plan is stored and shown under **“AI for this task”**.
- If the plan includes **suggested file searches**, click **“Copy to Search tab”** and then open the **Search** tab.

### Configuration
Set environment variables (optional):
- **`CFA_AI_ROOT`**: folder to search (defaults to the repo folder)
- **`OPENROUTER_API_KEY`**: enables OpenRouter (recommended for you)
- **`OPENROUTER_MODEL`**: defaults to `qwen/qwen-2.5-vl-7b-instruct`
- **`OPENROUTER_BASE_URL`**: defaults to `https://openrouter.ai/api/v1`
- **`OPENAI_API_KEY`**: enables OpenAI insights (optional)
- **`OPENAI_MODEL`**: defaults to `gpt-4o-mini`
- **`OLLAMA_BASE_URL`**: enables Ollama insights (optional, default `http://localhost:11434`)
- **`OLLAMA_MODEL`**: defaults to `llama3.1`
- See `env.example.txt` for a copy/paste template.

### Notes
- This repo intentionally keeps the AI layer **pluggable**. If no AI credentials are configured, you still get useful non-AI insights + safe stub responses.

