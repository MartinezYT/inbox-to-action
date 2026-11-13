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
    # "auto" uses Claude when a key is present, otherwise the offline rules engine.
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
    demo_rate_per_minute: int = field(default_factory=lambda: int(_env("DEMO_RATE_PER_MINUTE", "8")))
    max_message_chars: int = field(default_factory=lambda: int(_env("MAX_MESSAGE_CHARS", "8000")))

    @property
    def use_claude(self) -> bool:
        if self.triage_mode == "rules":
            return False
        if self.triage_mode == "claude":
            return True
        return bool(self.anthropic_api_key)


def get_settings() -> Settings:
    return Settings()
