"""Push alerts to Slack and/or Telegram for messages that matter.

Both are optional: if the env vars are empty, nothing is sent.
"""

from __future__ import annotations

import logging

import httpx

from .config import Settings
from .models import Category, ProcessedMessage, Urgency

log = logging.getLogger(__name__)

EMOJI = {
    Category.sales_lead: "💰", Category.support: "🛠️", Category.invoice_payment: "🧾",
    Category.partnership: "🤝", Category.spam: "🚫", Category.other: "📩",
}


def should_notify(p: ProcessedMessage) -> bool:
    t = p.triage
    if t.category is Category.spam:
        return False
    return t.urgency is Urgency.high or t.needs_human or t.category is Category.sales_lead


def format_alert(p: ProcessedMessage) -> str:
    t = p.triage
    lines = [
        f"{EMOJI[t.category]} *{t.category.value.replace('_', ' ').title()}* · urgency: *{t.urgency.value}*",
        f"From: {t.sender_name or p.message.sender} ({p.message.channel.value})",
        f"Summary: {t.summary}",
    ]
    if t.amount is not None:
        lines.append(f"Amount: {t.currency or ''} {t.amount:,.0f}".strip())
    if t.needs_human:
        lines.append("⚠️ Needs a human before replying")
    if t.action_items:
        lines.append("Next: " + "; ".join(t.action_items))
    return "\n".join(lines)


def send_alerts(settings: Settings, p: ProcessedMessage, client: httpx.Client | None = None) -> bool:
    if not should_notify(p):
        return False
    text = format_alert(p)
    sent = False
    own_client = client is None
    client = client or httpx.Client(timeout=10)
    try:
        if settings.slack_webhook_url:
            r = client.post(settings.slack_webhook_url, json={"text": text})
            sent |= r.is_success
        if settings.telegram_bot_token and settings.telegram_chat_id:
            r = client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": text.replace("*", "")},
            )
            sent |= r.is_success
    except httpx.HTTPError as exc:
        log.warning("Notification failed: %s", exc)
    finally:
        if own_client:
            client.close()
    return sent
