"""Application settings, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(default_factory=lambda: _env("CLAUDE_MODEL", "claude-haiku-5-5"))
    # Free alternatives (OpenAI-compatible). Used when there is no Anthropic key.
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL"))  # override the Groq/Gemini default
    # auto | anthropic | groq | gemini | rules. "auto" = first provider with a key, else rules.
    triage_mode: str = field(default_factory=lambda: _env("TRIAGE_MODE", "auto").lower())
    # Shared secret callers must send in the X-API-Key header. Empty = auth disabled (local dev only).
    api_key: str = field(default_factory=lambda: _env("API_KEY"))
    database_path: str = field(default_factory=lambda: _env("DATABASE_PATH", "data/inbox.db"))
    slack_webhook_url: str = field(default_factory=lambda: _env("SLACK_WEBHOOK_URL"))
    telegram_bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))
    business_name: str = field(default_factory=lambda: _env("BUSINESS_NAME", "Acme Logistics Lagos"))
    # Demo mode exposes the dashboard, read endpoints and a rate-limited /api/try publicly.
    # Turn it on for your portfolio deployment (sample data only), off for real customer data.
    demo_mode: bool = field(default_factory=lambda: _env("DEMO_MODE", "false").lower() in ("1", "true", "yes"))
    # In demo mode, load the sample messages on startup when the database is empty
    # (free hosts wipe the disk when the app sleeps).
    seed_demo_data: bool = field(default_factory=lambda: _env("SEED_DEMO_DATA", "true").lower() in ("1", "true", "yes"))
    seed_pause_seconds: float = field(default_factory=lambda: float(_env("SEED_PAUSE_SECONDS", "10")))
    demo_rate_per_minute: int = field(default_factory=lambda: int(_env("DEMO_RATE_PER_MINUTE", "8")))
    max_message_chars: int = field(default_factory=lambda: int(_env("MAX_MESSAGE_CHARS", "8000")))

    @property
    def provider(self) -> str:
        """Which engine to use: anthropic, groq, gemini or rules."""
        mode = "anthropic" if self.triage_mode == "claude" else self.triage_mode
        if mode != "auto":
            return mode
        if self.anthropic_api_key:
            return "anthropic"
        if self.groq_api_key:
            return "groq"
        if self.gemini_api_key:
            return "gemini"
        return "rules"


def get_settings() -> Settings:
    return Settings()
