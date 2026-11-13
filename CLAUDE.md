# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this is
FastAPI service that triages inbound business messages with Claude and returns a structured `Triage` object. See README for the architecture.

## Commands
- Run: `DEMO_MODE=true uvicorn app.main:app --reload`
- Test: `pytest -q` (must stay green; tests never call the real API)
- Lint: `ruff check .` (fix with `ruff check . --fix`)
- Eval: `python -m evals.run_eval -v` (Claude) / `TRIAGE_MODE=rules python -m evals.run_eval`

## Conventions
- `app/models.py` is the single source of truth for the AI output shape. If you add a field to `Triage`, update the rules engine, the dashboard, the n8n Sheets mapping and the tests.
- Every LLM engine (Claude, Groq, Gemini) must answer through the forced `record_triage` tool/function. Don't parse free text.
- Any LLM failure must fall back to `RulesTriage`. The webhook must never return 500 because of the model.
- Never render message content with `innerHTML` in the dashboard.
- Secrets only come from env vars. Never hard-code keys and never commit `.env`.
- When changing the prompt, run the eval before and after and note both numbers in the PR.
