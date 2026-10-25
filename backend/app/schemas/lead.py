from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Email


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class LeadIn(BaseModel):
    # price_sheet / spec_pdf / sample / quote = gated buttons on product pages; configurator = private-label tool
    source: Literal["enquiry_form", "price_sheet", "spec_pdf", "sample", "quote", "configurator", "koko"] = "enquiry_form"
    name: str = Field(min_length=2, max_length=120)
    company: str = Field(default="", max_length=200)
    email: Email | None = None
    phone: str = Field(default="", max_length=30)
    country: str = Field(default="", max_length=80)
    buyer_type: str = Field(default="", max_length=40)
    product_slug: str | None = None
    category_slug: str | None = None
    quantity: str = Field(default="", max_length=120)
    message: str = Field(default="", max_length=4000)
    source_page: str = Field(default="", max_length=255)
    consent: bool
    website: str = ""  # honeypot: hidden field, humans leave it empty
    chat: list[ChatMessage] = Field(default_factory=list, max_length=30)  # Koko leads only

    @model_validator(mode="after")
    def need_contact(self):
        if not self.email and not self.phone.strip():
            raise ValueError("Please give an email or a phone number.")
        if not self.consent:
            raise ValueError("Please agree to be contacted.")
        return self


class LeadOut(BaseModel):
    id: int
    source: str
    name: str
    company: str
    email: str
    phone: str
    country: str
    buyer_type: str
    quantity: str
    message: str
    chat_summary: str
    source_page: str
    status: str
    product_name: str | None = None
    category_name: str | None = None
    created_at: datetime
    assigned_to: int | None = None
    owner_name: str | None = None
    responded_at: datetime | None = None
    resolved_at: datetime | None = None
    outcome: str = ""
    note_count: int = 0
    sla_state: str = "ok"  # ok | due_soon | overdue | done
    sla_label: str = ""
    respond_due_at: datetime | None = None
    resolve_due_at: datetime | None = None


class KokoIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    page: str = Field(default="", max_length=255)
    chat_id: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9-]*$")  # random id from the browser


class KokoOut(BaseModel):
    reply: str
    suggest_enquiry: bool
