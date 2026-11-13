from dataclasses import replace

import pytest

from app.models import Category, IncomingMessage, Urgency
from app.notify import format_alert, should_notify
from app.store import Store
from app.triage import RulesTriage, TriageService, _triage_tool, extract_amount
from tests.conftest import FakeClaude

CLAUDE_OUTPUT = {
    "category": "support", "urgency": "high", "confidence": 0.93,
    "summary": "Customer's parcel is late and they want an update.",
    "sender_name": "Bola", "company": None, "amount": None, "currency": None,
    "action_items": ["Check tracking LGS-55812"], "suggested_reply": "Hi Bola, ...",
    "needs_human": False,
}
MSG = IncomingMessage(sender="bola@yahoo.com", subject="Still waiting", body="Where is my package?")


@pytest.mark.parametrize("text,amount,currency", [
    ("Budget is N800k monthly", 800_000, "NGN"),
    ("I paid ₦45,000 yesterday", 45_000, "NGN"),
    ("balance of NGN 1,200,000", 1_200_000, "NGN"),
    ("about 2.5m naira", 2_500_000, "NGN"),
    ("payment of $49.00", 49, "USD"),
    ("no money here", None, None),
])
def test_extract_amount(text, amount, currency):
    assert extract_amount(text) == (amount, currency)


@pytest.mark.parametrize("body,expected", [
    ("Congratulations! You have won the lottery, click here", Category.spam),
    ("Please find attached invoice INV-22", Category.invoice_payment),
    ("My delivery is delayed and the tracking is broken", Category.support),
    ("Can we explore a partnership and work together?", Category.partnership),
    ("How much for a quote on 10 deliveries?", Category.sales_lead),
    ("Hello there", Category.other),
])
def test_rules_categories(settings, body, expected):
    t = RulesTriage(settings).triage(IncomingMessage(sender="a@b.com", body=body))
    assert t.category is expected


def test_rules_flags_refunds_for_human(settings):
    t = RulesTriage(settings).triage(IncomingMessage(sender="a@b.com", body="I need a refund of N18,500 today"))
    assert t.needs_human and t.urgency is Urgency.high


def test_claude_engine_used_and_forced_tool(settings):
    fake = FakeClaude(tool_input=CLAUDE_OUTPUT)
    service = TriageService(replace(settings, triage_mode="claude"), client=fake)
    triage, engine = service.triage(MSG)
    assert engine == "claude"
    assert triage.category is Category.support and triage.confidence == 0.93
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "record_triage"}
    assert "Where is my package?" in call["messages"][0]["content"]


def test_claude_failure_falls_back_to_rules(settings):
    fake = FakeClaude(raise_exc=RuntimeError("API down"))
    service = TriageService(replace(settings, triage_mode="claude"), client=fake)
    triage, engine = service.triage(MSG)
    assert engine == "rules-fallback"
    assert triage.category is Category.support


def test_claude_invalid_output_falls_back(settings):
    fake = FakeClaude(tool_input={"category": "not-a-category"})
    service = TriageService(replace(settings, triage_mode="claude"), client=fake)
    assert service.triage(MSG)[1] == "rules-fallback"


def test_tool_schema_has_no_refs():
    schema = _triage_tool()["input_schema"]
    assert "$defs" not in schema and "$ref" not in str(schema)
    assert set(schema["properties"]["category"]["enum"]) == {c.value for c in Category}


def test_notifications_rules(settings):
    store = Store(":memory:")
    rules = RulesTriage(settings)
    spam = store.add(MSG, rules.triage(IncomingMessage(sender="x", body="you have won, click here")), "rules")
    lead = store.add(MSG, rules.triage(IncomingMessage(sender="x", body="quote for N2m order please")), "rules")
    assert not should_notify(spam)
    assert should_notify(lead)
    assert "Amount: NGN 2,000,000" in format_alert(lead)


def test_angry_late_refund_is_support(settings):
    body = "This is unacceptable. My package was supposed to arrive Monday. I paid N45,000. Refund me today."
    t = RulesTriage(settings).triage(IncomingMessage(sender="bola@yahoo.com", body=body))
    assert t.category is Category.support and t.urgency is Urgency.high and t.needs_human


def test_generic_inbox_has_no_name(settings):
    t = RulesTriage(settings).triage(IncomingMessage(sender="newsletter@techcabal.com", body="Top stories"))
    assert t.sender_name is None


def _fake_openai(arguments: dict | str, seen: list):
    import json as _json

    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_json.loads(request.content))
        args = arguments if isinstance(arguments, str) else _json.dumps(arguments)
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"type": "function", "function": {"name": "record_triage", "arguments": args}}]}}]})

    return httpx.Client(base_url="https://fake.test", transport=httpx.MockTransport(handler))


def test_groq_engine_forces_function_call(settings):
    seen: list = []
    s = replace(settings, triage_mode="groq", groq_api_key="x")
    service = TriageService(s, client=_fake_openai(CLAUDE_OUTPUT, seen))
    triage, engine = service.triage(MSG)
    assert engine == "groq" and service.llm.model == "openai/gpt-oss-120b"
    assert triage.category is Category.support
    body = seen[0]
    assert body["tool_choice"] == {"type": "function", "function": {"name": "record_triage"}}
    params = body["tools"][0]["function"]["parameters"]
    assert "anyOf" not in str(params) and "title" not in params


def test_groq_bad_json_falls_back(settings):
    s = replace(settings, triage_mode="groq", groq_api_key="x")
    service = TriageService(s, client=_fake_openai("{not json", []))
    assert service.triage(MSG)[1] == "rules-fallback"


@pytest.mark.parametrize("keys,expected", [
    ({}, "rules"),
    ({"groq_api_key": "g"}, "groq"),
    ({"gemini_api_key": "m"}, "gemini"),
    ({"anthropic_api_key": "a", "groq_api_key": "g"}, "anthropic"),
])
def test_auto_provider_picks_first_key(settings, keys, expected):
    assert replace(settings, triage_mode="auto", **keys).provider == expected


def test_provider_error_message_is_kept(settings, caplog):
    import httpx

    def handler(request):
        return httpx.Response(404, json={"error": {"message": "The model has been decommissioned"}})

    client = httpx.Client(base_url="https://fake.test", transport=httpx.MockTransport(handler))
    s = replace(settings, triage_mode="groq", groq_api_key="x")
    with caplog.at_level("WARNING"):
        assert TriageService(s, client=client).triage(MSG)[1] == "rules-fallback"
    assert "decommissioned" in caplog.text
