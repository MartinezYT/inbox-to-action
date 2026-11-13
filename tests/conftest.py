from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeClaude:
    """Stands in for anthropic.Anthropic so tests never hit the network or cost money."""

    def __init__(self, tool_input: dict | None = None, raise_exc: Exception | None = None):
        self.tool_input = tool_input
        self.raise_exc = raise_exc
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc:
            raise self.raise_exc
        block = SimpleNamespace(type="tool_use", name="record_triage", input=self.tool_input)
        return SimpleNamespace(content=[block])


@pytest.fixture
def settings() -> Settings:
    return replace(Settings(), triage_mode="rules", database_path=":memory:", api_key="test-key",
                   demo_mode=False, seed_demo_data=False, slack_webhook_url="", telegram_bot_token="",
                   anthropic_api_key="")


@pytest.fixture
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def auth() -> dict:
    return {"X-API-Key": "test-key"}
