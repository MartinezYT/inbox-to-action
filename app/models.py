"""Request/response schemas. Pydantic validates everything coming in and going out."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    sales_lead = "sales_lead"
    support = "support"
    invoice_payment = "invoice_payment"
    partnership = "partnership"
    spam = "spam"
    other = "other"


class Urgency(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Channel(StrEnum):
    email = "email"
    web_form = "web_form"
    whatsapp = "whatsapp"
    other = "other"


class IncomingMessage(BaseModel):
    """What a webhook (n8n, a form, an email parser) sends us."""

    sender: str = Field(..., min_length=1, max_length=320, examples=["tunde@bluepeak.ng"])
    subject: str = Field("", max_length=500)
    body: str = Field(..., min_length=1, examples=["Hi, we need a quote for 40 deliveries a week..."])
    channel: Channel = Channel.email


class Triage(BaseModel):
    """The structured decision the AI (or the rules fallback) returns."""

    category: Category
    urgency: Urgency
    confidence: float = Field(..., ge=0, le=1)
    summary: str = Field(..., description="One-sentence summary of what the sender wants.")
    sender_name: str | None = None
    company: str | None = None
    amount: float | None = Field(None, description="Money amount mentioned, if any.")
    currency: str | None = Field(None, description="ISO code, e.g. NGN or USD.")
    action_items: list[str] = Field(default_factory=list)
    suggested_reply: str = ""
    needs_human: bool = Field(False, description="True when a person should review before replying.")


class ProcessedMessage(BaseModel):
    id: int
    received_at: datetime
    message: IncomingMessage
    triage: Triage
    engine: str = Field(..., description="'claude' or 'rules' - which engine made the decision.")
    notified: bool = False


class Stats(BaseModel):
    total: int
    by_category: dict[str, int]
    by_urgency: dict[str, int]
    needs_human: int
