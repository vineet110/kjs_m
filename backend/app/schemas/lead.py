from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, field_validator, model_validator

from app.core.config.ini import cfg
from app.schemas.common import Email, OneLine, RequiredPhone


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def not_too_long(cls, v: str, info: ValidationInfo) -> str:
        # config/koko.ini message_max, read now (a Field(max_length=...) would be fixed at import). A visitor's
        # line over it is refused; Koko's own lines the browser sends back are only cut: the server uses its
        # saved copy of them, and a lowered limit must not block the chat after one long answer
        limit = cfg().koko.message_max
        if len(v) > limit:
            if info.data.get("role") == "assistant" and len(v) <= 4 * limit:
                return v[:limit]  # (far longer than any reply Koko gives: refused, not parsed and cut every time)
            raise ValueError(f"A chat message can be at most {limit} characters.")
        return v


class LeadIn(BaseModel):
    # price_sheet / spec_pdf / sample / quote = gated buttons on product pages; configurator = private-label tool
    # website_offer = the "Get your offer" form on the home page: phone required, name optional
    source: Literal["enquiry_form", "price_sheet", "spec_pdf", "sample", "quote", "configurator", "koko",
                    "website_offer"] = "enquiry_form"
    name: OneLine = Field(default="", max_length=120)  # at least 2 characters, except for website_offer
    company: OneLine = Field(default="", max_length=200)
    email: Email | None = None
    phone: RequiredPhone = Field(max_length=30)
    country: OneLine = Field(default="", max_length=80)
    buyer_type: OneLine = Field(default="", max_length=40)
    product_slug: str | None = Field(default=None, max_length=120)
    category_slug: str | None = Field(default=None, max_length=120)
    quantity: OneLine = Field(default="", max_length=120)
    message: str = Field(default="", max_length=4000)
    source_page: str = Field(default="", max_length=255)
    consent: bool
    website: str = Field(default="", max_length=255)  # honeypot: hidden field, humans leave it empty
    # Koko leads only. As many lines as a Koko request may have (koko.ini request_lines, checked below), so a
    # long chat never blocks its enquiry form
    chat: list[ChatMessage] = Field(default_factory=list)
    # Koko's chat id: the sales summary is made from the saved transcript, never the browser's copy (R71)
    chat_id: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9-]*$")

    @field_validator("chat")
    @classmethod
    def chat_not_too_long(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        # Only the newest lines are kept, never a refusal: the visitor can't send the form without the chat,
        # and the summary comes from the saved transcript anyway
        return v[-cfg().koko.request_lines:]

    @model_validator(mode="after")
    def need_contact(self):
        if not self.consent:
            raise ValueError("Please agree to be contacted.")
        # Checked after cleaning ("  " becomes ""). The offer form asks only for a phone number.
        if self.source != "website_offer" and len(self.name) < 2:
            raise ValueError("Please enter your name.")
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
    updated_at: datetime | None = None
    created_by_name: str | None = None  # internal leads: who typed it in
    extra: dict[str, str] = Field(default_factory=dict)  # "Extra Info" (see InternalLeadIn)


ExtraName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ExtraValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
MAX_EXTRA = 30  # Extra Info columns on one lead


class InternalLeadIn(BaseModel):
    """A lead staff type in by hand (a phone call, a trade fair, a walk-in). It is theirs from the start."""
    name: OneLine = Field(min_length=2, max_length=120)
    company: OneLine = Field(default="", max_length=200)
    email: Email | None = None
    phone: RequiredPhone = Field(max_length=30)
    country: OneLine = Field(default="", max_length=80)
    buyer_type: OneLine = Field(default="", max_length=40)
    category_slug: str | None = Field(default=None, max_length=120)
    quantity: OneLine = Field(default="", max_length=120)
    message: str = Field(default="", max_length=4000)
    # "Extra Info": file columns we have no field for, that the person chose to Add
    extra: dict[ExtraName, ExtraValue] = Field(default_factory=dict, max_length=MAX_EXTRA)


class InternalLeadFormIn(InternalLeadIn):
    """The New internal lead form: also says which file columns were rejected (names only, for the audit log)."""
    extra_rejected: list[ExtraName] = Field(default_factory=list, max_length=MAX_EXTRA)


class Contact(BaseModel):
    """One person who sent us enquiries (leads with the same phone number, or email, are one contact)."""
    lead_id: int  # their newest enquiry: the contact page opens on it
    name: str
    email: str
    phone: str
    active: int  # open enquiries (new or contacted)
    inactive: int  # closed ones
    total: int
    last_at: datetime


class KokoIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)  # at most koko.ini request_lines (checked below)
    page: str = Field(default="", max_length=255)
    chat_id: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9-]*$")  # random id from the browser

    @model_validator(mode="after")
    def starts_and_ends_with_visitor(self):
        # The browser sends the history. A history that starts with a made-up "assistant" turn is a
        # common prompt-injection trick, and the last message must be the visitor's question.
        if self.messages[0].role != "user" or self.messages[-1].role != "user":
            raise ValueError("The conversation must start and end with a visitor message.")
        # A long chat is never refused (the visitor would be stuck): only its newest request_lines are kept (the
        # server sends the AI its own saved copy cut to chat_max anyway); a Koko line our cut leaves first goes too
        self.messages = self.messages[-cfg().koko.request_lines:]
        while self.messages[0].role != "user":
            self.messages = self.messages[1:]
        return self


class KokoCardProduct(BaseModel):
    name: str
    slug: str
    image_path: str


class KokoCatalogue(BaseModel):
    """The catalogue card on Koko's first reply on a product or category page (from the database, not the AI)."""
    category_name: str
    category_slug: str
    products: list[KokoCardProduct]


class KokoOut(BaseModel):
    reply: str
    suggest_enquiry: bool
    catalogue: KokoCatalogue | None = None
