from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, ValidationInfo, field_validator, model_validator

from app.core.config.ini import KokoIni, cfg
from app.schemas.common import Email, OneLine, RequiredPhone


def _top(name: str) -> int:
    """The upper bound of a koko.ini setting's allowed range (its `le`), so the ceilings below follow ini.py."""
    return next(m.le for m in KokoIni.model_fields[name].metadata if getattr(m, "le", None) is not None)


# Before anything is parsed, a request is cut to the most lines and the longest line koko.ini could ever
# allow (the tops of request_lines' and message_max's ranges): a body of tens of thousands of lines, or of
# huge lines, is cut, not validated line by line. The real limits (cfg) are applied after.
CHAT_LINES_CEILING = _top("request_lines")
CHAT_LINE_CEILING = _top("message_max")


def _newest_lines(v):
    """The newest CHAT_LINES_CEILING lines; a Koko line this cut leaves first goes too (a chat starts with
    the visitor). Only cuts a list that was longer: a request that itself starts with Koko is still refused."""
    if not isinstance(v, list):
        return v
    if len(v) > CHAT_LINES_CEILING:
        v = v[-CHAT_LINES_CEILING:]
        while v and isinstance(v[0], dict) and v[0].get("role") == "assistant":
            v = v[1:]
    # cut, never refused: a long Koko answer the browser sends back must not lock the visitor out
    return [{**m, "content": m["content"][:CHAT_LINE_CEILING]}
            if isinstance(m, dict) and isinstance(m.get("content"), str) and len(m["content"]) > CHAT_LINE_CEILING
            else m for m in v]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def not_too_long(cls, v: str, info: ValidationInfo) -> str:
        # config/koko.ini message_max, read now (a Field(max_length=...) would be fixed at import).
        # Every line is cut to message_max, never refused here: the browser sends the whole chat again each time,
        # so refusing an old line (e.g. after message_max was lowered) would block the chat for good. Only a new
        # question that is too long is refused (KokoIn.question_not_too_long).
        return v[:cfg().koko.message_max]


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
    chat: Annotated[list[ChatMessage], BeforeValidator(_newest_lines)] = Field(default_factory=list)
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
    messages: Annotated[list[ChatMessage], BeforeValidator(_newest_lines)] = Field(min_length=1)  # cut below too
    page: str = Field(default="", max_length=255)
    chat_id: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9-]*$")  # random id from the browser
    # A new random id per question; the same one when the widget repeats a request (so a retry is told apart)
    turn_id: str = Field(default="", max_length=40, pattern=r"^[A-Za-z0-9-]*$")

    @model_validator(mode="before")
    @classmethod
    def question_not_too_long(cls, data):
        # The new question (the last line) over message_max is refused, so the visitor knows; older lines are cut
        msgs = data.get("messages") if isinstance(data, dict) else None
        if isinstance(msgs, list) and msgs and isinstance(msgs[-1], dict):
            if len(str(msgs[-1].get("content", ""))) > cfg().koko.message_max:
                raise ValueError(f"A chat message can be at most {cfg().koko.message_max} characters.")
        return data

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
