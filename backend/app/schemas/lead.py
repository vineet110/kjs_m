from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.common import Email, OneLine, RequiredPhone


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class LeadIn(BaseModel):
    # price_sheet / spec_pdf / sample / quote = gated buttons on product pages; configurator = private-label tool
    source: Literal["enquiry_form", "price_sheet", "spec_pdf", "sample", "quote", "configurator", "koko"] = "enquiry_form"
    name: OneLine = Field(min_length=2, max_length=120)
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
    chat: list[ChatMessage] = Field(default_factory=list, max_length=30)  # Koko leads only

    @model_validator(mode="after")
    def need_contact(self):
        if not self.consent:
            raise ValueError("Please agree to be contacted.")
        # Same cap as a Koko chat: the chat is summarised by the AI, and a huge one costs a lot.
        if sum(len(m.content) for m in self.chat) > 8000:
            raise ValueError("The conversation is too long.")
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
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    page: str = Field(default="", max_length=255)
    chat_id: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9-]*$")  # random id from the browser

    @model_validator(mode="after")
    def starts_and_ends_with_visitor(self):
        # The browser sends the history. A history that starts with a made-up "assistant" turn is a
        # common prompt-injection trick, and the last message must be the visitor's question.
        if self.messages[0].role != "user" or self.messages[-1].role != "user":
            raise ValueError("The conversation must start and end with a visitor message.")
        if sum(len(m.content) for m in self.messages) > 8000:
            raise ValueError("The conversation is too long. Please start a new chat.")
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
