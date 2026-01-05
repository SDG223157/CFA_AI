## Daily Tasks + File Insights (AI Dashboard)

A local app to capture daily tasks, search your files/data, and generate insights with an optional AI layer.

### What you get
- **Task inbox**: add tasks quickly; mark done; persistence on disk
- **File search**: search within a chosen root folder; preview file snippets
- **Insights dashboard**: lightweight stats + optional AI summary over selected results

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
    - Google Console **Authorized redirect URI** must be: `APP_BASE_URL/` (note the trailing slash)
  - Optional: `CFA_AI_ROOT` (inside the container; typically leave default unless you mount data)
- **Persistent Storage** (recommended):
  - Mount a volume to `/app/.local` to persist `tasks.sqlite3` across deploys

### Configuration
Set environment variables (optional):
- **`CFA_AI_ROOT`**: folder to search (defaults to the repo folder)
- **`OPENROUTER_API_KEY`**: enables OpenRouter (recommended for you)
- **`OPENROUTER_MODEL`**: defaults to `qwen/qwen2.5-vl-7b-instruct`
- **`OPENROUTER_BASE_URL`**: defaults to `https://openrouter.ai/api/v1`
- **`OPENAI_API_KEY`**: enables OpenAI insights (optional)
- **`OPENAI_MODEL`**: defaults to `gpt-4o-mini`
- **`OLLAMA_BASE_URL`**: enables Ollama insights (optional, default `http://localhost:11434`)
- **`OLLAMA_MODEL`**: defaults to `llama3.1`
- See `env.example.txt` for a copy/paste template.

### Notes
- This repo intentionally keeps the AI layer **pluggable**. If no AI credentials are configured, you still get useful non-AI insights + safe stub responses.

