"""Tunable settings from config/*.ini, applied live (no restart).

Secrets and per-environment values stay in .env (see __init__.py). Everything a person
may want to tune (SLA minutes, batch sizes, rate limits, log levels, feature on/off)
lives in the repo-root config/ folder, one file per feature (chat.ini, leads.ini, ...).
A new feature gets its own file and class here; no tunable numbers as constants in the code.
Security limits (zip-bomb sizes, sign-in windows, redirect caps) stay in code on purpose:
a typo in an ini must never weaken a security check.

How to read a value:  cfg().sla.respond_minutes
Always call cfg() at the moment you need the value. Never copy it into a module-level
constant, or a changed file won't apply.

Order (highest wins): env var KJS__<SECTION>__<KEY>  ->  ini file  ->  default below.
Every few seconds cfg() checks the files' modified-times. On a change it re-reads and
validates everything; if the new values are invalid it keeps the old ones and logs an
error naming the file and key.
"""
import configparser
import logging
import os
import re
import threading
import time
import typing
from pathlib import Path
from typing import Callable, Literal

from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

log = logging.getLogger("app.config")

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR") or Path(__file__).resolve().parents[4] / "config")
CHECK_EVERY_SECONDS = 3
ENV_PREFIX = "KJS__"


# ---------- The shape of every file (types, ranges, defaults) ----------
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"  # 24-hour time like 09:30. A typo ("09.30") is refused, not used.


class AppIni(BaseModel):
    site_name: str = "KJS India"
    timezone: str = "Asia/Kolkata"
    lead_rate_per_hour: int = Field(5, ge=1)  # enquiries per IP per hour
    koko_rate_per_hour: int = Field(40, ge=1)  # chat messages per IP per hour
    lead_file_reads_per_hour: int = Field(60, ge=1)  # Excel / CSV files read into the lead form, per person
    login_failures_per_ip: int = Field(100, ge=1)  # wrong passwords per network per 15 min (all emails)
    signups_per_ip_per_hour: int = Field(30, ge=1)  # the office shares one address: go-live day
    # false = staff may log in before verifying their email (TEMPORARY, while Firebase's verify emails fail).
    # Admin approval still guards every new account, and an old account is never linked by email without
    # a verified email (that would let anyone take over e.g. the first admin).
    require_verified_email: bool = True
    jobs_enabled: bool = True
    jobs_interval_seconds: int = Field(60, ge=5)  # how often background checks run
    jobs_hours: str = Field("08:00-21:00", pattern=r"^\d{2}:\d{2}-\d{2}:\d{2}$")  # IST, Mon-Sat
    job_timeout_seconds: int = Field(300, ge=30, le=1800)  # a stuck job is cancelled after this
    shift_start: str = Field("09:30", pattern=HHMM)  # IST; check-in after shift_start + late_after_minutes = late
    shift_end: str = Field("18:30", pattern=HHMM)
    late_after_minutes: int = Field(15, ge=0)

    @field_validator("timezone")
    @classmethod
    def real_timezone(cls, v: str) -> str:
        ZoneInfo(v)  # raises for a misspelt name, so the last good config is kept
        return v

    @model_validator(mode="after")
    def shift_order(self):
        if self.shift_start >= self.shift_end:
            raise ValueError("shift_start must be before shift_end")
        return self


class FeaturesIni(BaseModel):
    koko: bool = True
    offers_ticker: bool = True
    configurator: bool = False  # needs price bands from KJS (I3)
    partners: bool = True
    gated_actions: bool = True
    whatsapp_button: bool = True
    connect_popup: bool = True  # "let's connect" WhatsApp popup on the public site


class SlaIni(BaseModel):
    respond_minutes: int = Field(20, ge=1)
    resolve_minutes: int = Field(60, ge=1)
    escalate_after_minutes: int = Field(10, ge=0)


class AssignIni(BaseModel):
    batch_size: int = Field(20, ge=1, le=500)
    max_batches_per_day: int = Field(3, ge=1)
    import_max_mb: int = Field(10, ge=1, le=25)  # one Excel / CSV file to auto-assign; nginx caps at 26 MB
    import_max_rows: int = Field(5000, ge=10, le=50000)
    work_start: str = Field("09:30", pattern=HHMM)
    work_end: str = Field("18:30", pattern=HHMM)

    @model_validator(mode="after")
    def work_order(self):
        if self.work_start >= self.work_end:
            raise ValueError("work_start must be before work_end")
        return self


class AlertsIni(BaseModel):
    thresholds: list[int] = Field(default_factory=lambda: [50, 85, 100])
    channels: list[str] = Field(default_factory=lambda: ["in_app", "email"])


class KokoIni(BaseModel):
    temperature: float = Field(0.3, ge=0, le=2)
    max_tokens: int = Field(700, ge=50, le=4000)
    daily_limit: int = Field(2000, ge=0, le=100000)  # AI calls per day for ALL visitors together (cost cap)
    prompt_products: int = Field(8, ge=1, le=30)  # products given to the AI per message
    card_products: int = Field(6, ge=1, le=20)  # products on the catalogue card
    prompt_limit: int = Field(8000, ge=2000, le=60000)  # characters of system prompt (about 2,000 tokens)
    timeout_seconds: int = Field(25, ge=5, le=55)  # whole AI call; nginx gives up at 60 s
    http_timeout_seconds: int = Field(20, ge=5, le=55)  # one HTTP request to the AI provider
    message_max: int = Field(2000, ge=200, le=10000)  # characters of one chat line (visitor or Koko)
    chat_max: int = Field(8000, ge=1000, le=60000)  # characters of the whole chat the AI may be sent

    @model_validator(mode="after")
    def timeout_order(self):
        if self.http_timeout_seconds > self.timeout_seconds:
            raise ValueError("http_timeout_seconds must not be more than timeout_seconds")
        return self


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingIni(BaseModel):
    level: LogLevel = "INFO"  # a typo like "verbose" is refused; the last good config stays
    format: str = "pretty"  # pretty (dev) | json (staging, production)
    show_personal_data: bool = False  # true only on a dev machine
    levels: dict[str, LogLevel] = Field(default_factory=dict)  # [logging.levels] app.services.lead = DEBUG


class StorageIni(BaseModel):
    max_upload_mb: int = Field(25, ge=1, le=25)  # nginx caps uploads at 26 MB: raise both together
    allowed_types: list[str] = Field(default_factory=lambda: [
        "pdf", "png", "jpg", "jpeg", "webp", "xlsx", "xls", "docx", "doc", "csv", "txt", "zip",
        "pptx", "ppt", "gif", "heic", "mp4", "mov"])


class ComplaintsIni(BaseModel):
    developer_email: str = ""  # gets new complaints by email, once email is set up (not used yet)
    min_title_words: int = Field(3, ge=1, le=20)
    min_description_words: int = Field(15, ge=1, le=100)
    list_limit: int = Field(200, ge=50, le=2000)  # newest first on /admin/complaints (no paging yet)


class ChatIni(BaseModel):
    send_per_minute: int = Field(30, ge=1, le=600)  # messages one person may send per minute
    page_max: int = Field(100, ge=10, le=500)  # most messages one request may ask for
    body_max: int = Field(4000, ge=100, le=20000)  # characters in one message


class LeadsIni(BaseModel):
    """Lead limits other than the SLA minutes (those are in sla.ini)."""
    due_soon_minutes: int = Field(5, ge=0, le=120)  # a lead shows "due soon" this close to its target
    file_max_mb: int = Field(10, ge=1, le=25)  # one Excel / CSV file read or imported; nginx caps at 26 MB
    file_preview_rows: int = Field(50, ge=1, le=500)  # rows shown to pick one lead from a file
    import_max_rows: int = Field(500, ge=1, le=5000)  # bulk import: each row becomes a lead
    employee_page_size: int = Field(200, ge=50, le=1000)  # leads per page for an employee (own + unassigned)
    admin_page_size: int = Field(500, ge=50, le=2000)  # leads per page in All Enquiries (leads.view_all)


class AttendanceIni(BaseModel):
    max_shift_hours: int = Field(16, ge=8, le=24)  # longest believable shift (check-out after midnight)
    max_export_days: int = Field(366, ge=7, le=1100)  # longest date range for the Excel export


class NotificationsIni(BaseModel):
    email_attempts: int = Field(3, ge=1, le=10)  # tries before an email is marked failed
    email_time_budget_seconds: int = Field(120, ge=10, le=280)  # per run, so SLA and alert jobs aren't held up
    stuck_retry_minutes: int = Field(15, ge=5, le=1440)  # an email left "sending" by a crash is retried after


class HarvestIni(BaseModel):
    http_timeout_seconds: int = Field(30, ge=5, le=120)  # one request to a lead source


class BoardsIni(BaseModel):
    max_days: int = Field(730, ge=30, le=1830)  # longest order (start to deadline); longer = slow day plan


class AnalyticsIni(BaseModel):
    attendance_days: int = Field(14, ge=7, le=90)  # attendance chart
    tasks_days: int = Field(30, ge=7, le=365)  # tasks done per person
    top_people: int = Field(15, ge=5, le=100)  # people shown in "tasks done"


BUTTON_NAME = r"^[a-z][a-z0-9_]{1,39}$"  # a tracked button's name: add_to_enquiry, whatsapp, ...


class SiteInsightsIni(BaseModel):
    """Website insights: what visitors view, search and click (no cookie, no IP; see site_insights_service)."""
    keep_days: int = Field(180, ge=30, le=730)  # older visitor events are deleted
    cleanup_every_hours: int = Field(6, ge=1, le=168)  # how often that delete runs
    default_days: int = Field(30, ge=1, le=365)  # range shown when the report opens (at most keep_days)
    day_choices: list[int] = Field(default_factory=lambda: [7, 30, 90])  # buttons above the report
    top_n: int = Field(10, ge=3, le=50)  # rows in each "top" list
    max_events_per_send: int = Field(20, ge=1, le=100)  # events in one request from a browser
    sends_per_minute_per_visit: int = Field(20, ge=5, le=600)  # one tab sends about 6 a minute
    sends_per_minute_per_network: int = Field(600, ge=30, le=10000)  # many visitors can share one network
    send_every_seconds: int = Field(10, ge=2, le=120)  # how often a browser sends what it collected
    search_pause_ms: int = Field(1500, ge=300, le=10000)  # typing pause before a search is recorded
    min_search_chars: int = Field(2, ge=1, le=10)  # shorter searches are not recorded
    # Buttons whose clicks are counted. A button is tagged data-track="<name>" on the website.
    buttons: list[str] = Field(default_factory=lambda: [
        "add_to_enquiry", "spec_sheet", "price_sheet", "whatsapp", "call", "send_enquiry", "configurator",
        "sample_quote"])
    # Website pages counted by their address. Product and category pages count when the product or category
    # exists. Any other address is saved as "other" (it could carry anything, like an email).
    pages: list[str] = Field(default_factory=lambda: [
        "/", "/products", "/categories", "/contact", "/partners", "/private-label"])
    # Visitors whose browser name contains one of these words are robots and are not counted
    bot_words: list[str] = Field(default_factory=lambda: [
        "bot", "crawl", "spider", "slurp", "headless", "lighthouse", "preview", "curl", "wget", "python",
        "httpclient", "facebookexternalhit"])

    @field_validator("day_choices")
    @classmethod
    def day_choices_ok(cls, v: list[int]) -> list[int]:
        if not v or any(d < 1 or d > 730 for d in v):
            raise ValueError("day_choices must be 1 to 730 days each")
        return sorted(set(v))

    @field_validator("buttons")
    @classmethod
    def buttons_ok(cls, v: list[str]) -> list[str]:
        bad = [b for b in v if not re.match(BUTTON_NAME, b)]
        if bad or not v:
            raise ValueError(f"button names must be lowercase words joined by _ (bad: {bad})")
        return v

    @field_validator("pages")
    @classmethod
    def pages_ok(cls, v: list[str]) -> list[str]:
        bad = [p for p in v if not re.match(r"^/[a-z0-9\-/]*$", p)]
        if bad:
            raise ValueError(f"pages must be addresses like /contact (bad: {bad})")
        return [p.rstrip("/") or "/" for p in v]

    @model_validator(mode="after")
    def ranges_fit_keep_days(self):
        # A range longer than the days kept would show an error every time the report opens
        if self.default_days > self.keep_days:
            raise ValueError("default_days must be at most keep_days")
        if not any(d <= self.keep_days for d in self.day_choices):
            raise ValueError("at least one of day_choices must be at most keep_days")
        return self

    @field_validator("bot_words")
    @classmethod
    def bot_words_lower(cls, v: list[str]) -> list[str]:
        return [w.lower() for w in v]


class SiteUiIni(BaseModel):
    """Home page look and motion (site_ui.ini). Only display settings: everything here is safe for browsers."""
    enabled: bool = True  # off = the home page stays as it was before the refresh
    slide_seconds: int = Field(6, ge=3, le=30)  # hero banner: seconds per slide
    glow: bool = True  # soft pulse around the Ask Koko and WhatsApp buttons
    glow_seconds: int = Field(3, ge=1, le=10)  # seconds per pulse
    reveal_left_to_right: bool = True  # tiles and product cards come in from the left
    steps_light_up: bool = True  # "How it works" steps light up 1 to 4
    steps_gap_ms: int = Field(450, ge=100, le=2000)  # gap between two steps lighting up
    top_strip: bool = True  # thin strip above the header (since 2020, certificates, phone, email)
    theme_toggle: bool = True  # ☀/☾ button in the header for a dark website
    dark_follows_system: bool = False  # true = dark website for visitors whose device is in dark mode
    partner_strip: bool = True  # sliding partner and certificate strip
    partner_strip_px_per_second: int = Field(45, ge=10, le=200)  # its speed
    # Admin > Website > Hero
    hero_max_slides: int = Field(5, ge=1, le=10)  # slides that can be switched on at once
    hero_max_stats: int = Field(4, ge=1, le=6)  # numbers in the stats box
    image_max_px: int = Field(1600, ge=400, le=4000)  # uploaded pictures: longest side after shrinking
    image_quality: int = Field(82, ge=40, le=95)  # JPEG/WebP quality after shrinking
    # Admin > Website > Partner logos and Pop-up activity
    partners_max: int = Field(12, ge=1, le=40)  # partners that can be on in the sliding strip
    activity_max_age_days: int = Field(60, ge=1, le=365)  # older activity lines stop showing by themselves
    activity_public_max: int = Field(100, ge=5, le=500)  # lines the website loads at most
    # The site talks (PR C): hover messages, nudges, the "Get your offer" box and its pop-ups
    talk: bool = True  # hover messages and nudges
    talk_all_pages: bool = False  # false = home page only
    typing_search: bool = True  # example searches type themselves in the search box
    bubble_seconds: int = Field(5, ge=2, le=20)  # a nudge stays this long
    idle_seconds: int = Field(20, ge=5, le=300)  # Koko speaks after this long without a move (once per visit)
    phone_koko_seconds: int = Field(6, ge=2, le=120)  # phones: Koko speaks once after this long
    phone_whatsapp_seconds: int = Field(16, ge=2, le=300)  # phones: WhatsApp speaks once after this long
    offer_box: bool = True  # the "Get your offer" box, its pop-ups and form
    popup_times: list[int] = Field(default_factory=lambda: [5, 8, 11, 15, 17, 25])  # seconds after page load; repeats
    popup_show_seconds: int = Field(4, ge=1, le=30)  # a pop-up stays this long, then fades
    popup_fade_ms: int = Field(1800, ge=200, le=5000)  # how slowly it fades
    popups_on_screen: int = Field(3, ge=1, le=5)  # at most this many at once (computer)
    popups_on_screen_phone: int = Field(1, ge=1, le=3)  # at most this many at once (phone)
    popups_per_visit: int = Field(20, ge=1, le=200)  # then they stop for the visit
    form_open_seconds: int = Field(14, ge=5, le=120)  # an untouched form closes itself after this long
    form_warn_seconds: int = Field(4, ge=1, le=30)  # "about to slip away" shows this long before

    @field_validator("popup_times")
    @classmethod
    def popup_times_ok(cls, v: list[int]) -> list[int]:
        # Seconds after page load, rising: 5, 8, 11 ... A typo like "5, 3" must not fire two at once
        if not v or len(v) > 20 or any(t < 1 or t > 600 for t in v) or v != sorted(set(v)):
            raise ValueError("popup_times must be 1 to 20 rising numbers of seconds (1 to 600)")
        return v

    @model_validator(mode="after")
    def warning_fits(self):
        if self.form_warn_seconds >= self.form_open_seconds:
            raise ValueError("form_warn_seconds must be less than form_open_seconds")
        return self


MODULE_LEVELS = {"off": 0, "admin": 1, "on": 2}  # on = everyone, admin = admins only, off = nobody
ModuleLevel = Literal["on", "admin", "off"]
# area -> areas it needs, switched on at least as far (batches go only to staff who checked in)
MODULE_NEEDS = {"batches": ("attendance",), "site_insights": ("analytics",)}  # insights: a tab on Reports


class ModulesIni(BaseModel):
    """Portal areas released in phases. Leads, tasks, My day, profile, approvals, users and settings
    have no switch: they are always on."""
    model_config = ConfigDict(extra="forbid")  # a misspelt area is refused, never silently ignored

    batches: ModuleLevel = "on"  # My batches, Auto-assign
    order_boards: ModuleLevel = "on"  # order boards (employee + admin), their files and alerts
    attendance: ModuleLevel = "on"  # attendance, team attendance, holidays, leave, shifts, availability
    website_admin: ModuleLevel = "on"  # All Products, SEO & Partners, Manage KOKO
    analytics: ModuleLevel = "on"
    alerts: ModuleLevel = "on"
    audit: ModuleLevel = "on"
    chat: ModuleLevel = "on"  # Chat: channels, groups, direct messages (API and live connection)
    lead_harvester: ModuleLevel = "on"  # Client Schedulers (Lead Harvester) page, API and job
    # Website insights tab on Reports; off = visitors are not recorded. Off when the line is missing, so a
    # modules.ini with analytics = off and no site_insights line stays valid (it needs analytics).
    site_insights: ModuleLevel = "off"

    @field_validator("*", mode="before")
    @classmethod
    def lower(cls, v):
        return v.strip().lower() if isinstance(v, str) else v  # "On" and " on" are fine

    @model_validator(mode="after")
    def needs(self):
        for area, needed in MODULE_NEEDS.items():
            for other in needed:
                mine, theirs = getattr(self, area), getattr(self, other)
                if MODULE_LEVELS[mine] > MODULE_LEVELS[theirs]:
                    raise ValueError(f"{area} = {mine} needs {other} switched on at least as far, "
                                     f"but {other} = {theirs}")
        return self


class Config(BaseModel):
    app: AppIni = AppIni()
    features: FeaturesIni = FeaturesIni()
    sla: SlaIni = SlaIni()
    assign: AssignIni = AssignIni()
    alerts: AlertsIni = AlertsIni()
    koko: KokoIni = KokoIni()
    logging: LoggingIni = LoggingIni()
    storage: StorageIni = StorageIni()
    modules: ModulesIni = ModulesIni()
    complaints: ComplaintsIni = ComplaintsIni()
    chat: ChatIni = ChatIni()
    leads: LeadsIni = LeadsIni()
    attendance: AttendanceIni = AttendanceIni()
    notifications: NotificationsIni = NotificationsIni()
    harvest: HarvestIni = HarvestIni()
    boards: BoardsIni = BoardsIni()
    analytics: AnalyticsIni = AnalyticsIni()
    site_insights: SiteInsightsIni = SiteInsightsIni()
    site_ui: SiteUiIni = SiteUiIni()

    @model_validator(mode="after")
    def job_timeout_covers_email_budget(self):
        # The jobs loop cancels a job at app.job_timeout_seconds; send_emails stops itself at its own budget.
        # A shorter timeout would cut a batch mid-send (rows stuck "sending", an email possibly sent twice).
        if self.app.job_timeout_seconds < self.notifications.email_time_budget_seconds + 30:
            raise ValueError("app.ini job_timeout_seconds must be at least notifications.ini "
                             "email_time_budget_seconds + 30")
        return self


# file name -> section it fills
FILES = {name: f"{name}.ini" for name in Config.model_fields}


def _is_list(annotation) -> bool:
    """list[...] or an optional list (list[str] | None)."""
    if typing.get_origin(annotation) is list:
        return True
    return any(typing.get_origin(a) is list for a in typing.get_args(annotation))


def _list_fields() -> set[tuple[str, str]]:
    """(section, key) pairs written as a comma list in the ini ("a, b, c"): every field typed as a list.
    Per section, so a key with the same name in another file is never split by mistake."""
    return {(section, name)
            for section, model in Config.model_fields.items()
            for name, field in model.annotation.model_fields.items() if _is_list(field.annotation)}


LIST_FIELDS = _list_fields()


# ---------- Loading ----------
def _read_raw() -> dict:
    """Read every ini file into {section: {key: value}} (strings), then apply env overrides."""
    raw: dict[str, dict] = {}
    for section, filename in FILES.items():
        path = CONFIG_DIR / filename
        values: dict = {}
        if path.exists():
            parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
            parser.optionxform = str  # keep key case (module names in [logging.levels])
            try:
                parser.read(path, encoding="utf-8")
            except configparser.Error as e:
                raise ValueError(f"{filename}: {e}") from e
            if parser.has_section(section):
                values.update(parser[section])
            if section == "logging" and parser.has_section("logging.levels"):
                values["levels"] = dict(parser["logging.levels"])
        raw[section] = values

    # KJS__SLA__RESPOND_MINUTES=15 overrides [sla] respond_minutes
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            parts = key[len(ENV_PREFIX):].lower().split("__")
            if len(parts) == 2 and parts[0] in raw:
                raw[parts[0]][parts[1]] = value

    for section, k in LIST_FIELDS:
        values = raw.get(section, {})
        if isinstance(values.get(k), str):
            values[k] = [x.strip() for x in values[k].split(",") if x.strip()]
    return raw


def _validate(raw: dict) -> Config:
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        loc = list(first["loc"])
        section = loc[0] if loc else "?"
        where = f" '{loc[1]}'" if len(loc) > 1 else ""  # a rule between two keys has no single key
        raise ValueError(f"config/{FILES.get(section, section)}:{where} {first['msg']}") from e


def _flatten(c: Config) -> dict[str, object]:
    return {f"{s}.{k}": v for s, sec in c.model_dump().items() for k, v in sec.items()}


class _Store:
    def __init__(self):
        self.config = Config()
        self.mtimes: dict[str, float] = {}
        self.checked_at = 0.0
        self.lock = threading.Lock()
        self.listeners: list[Callable[[Config], None]] = []
        self.loaded_from_files = False

    def _current_mtimes(self) -> dict[str, float]:
        out = {}
        for f in FILES.values():
            try:
                out[f] = (CONFIG_DIR / f).stat().st_mtime
            except OSError:  # missing, or being replaced right now: treat as absent
                pass
        return out

    def load(self, force: bool = False) -> None:
        with self.lock:
            mtimes = self._current_mtimes()
            if not force and mtimes == self.mtimes and self.loaded_from_files:
                return
            self.mtimes = mtimes
            try:
                new = _validate(_read_raw())
            except ValueError as e:
                log.error("config.invalid", extra={"reason": str(e)})
                return  # keep the last good config
            changed = {k: v for k, v in _flatten(new).items() if _flatten(self.config).get(k) != v}
            self.config, first = new, not self.loaded_from_files
            self.loaded_from_files = True
        for fn in self.listeners:
            try:  # a broken listener must never break cfg() for whoever called it
                fn(new)
            except Exception:
                log.exception("config.listener_failed")
        if changed and not first:
            log.info("config.reloaded", extra={"changed": changed})

    def get(self) -> Config:
        now = time.monotonic()
        if now - self.checked_at > CHECK_EVERY_SECONDS:
            self.checked_at = now
            self.load()
        return self.config


_store = _Store()


def cfg() -> Config:
    """The current tunable settings. Cheap: re-checks the files at most every few seconds."""
    return _store.get()


def on_reload(fn: Callable[[Config], None]) -> None:
    """Run fn(config) now and after every successful reload (e.g. to apply log levels)."""
    _store.listeners.append(fn)
    fn(cfg())


def reload_now() -> Config:
    """Force a re-read (tests, admin 'reload' button)."""
    _store.load(force=True)
    return _store.config


def public_config() -> dict:
    """Only values that are safe to show in a browser."""
    c = cfg()
    s = c.site_insights
    # The website's visitor tracker: off when the area is off (then nothing is sent at all)
    insights = {"on": c.modules.site_insights != "off", "send_every_seconds": s.send_every_seconds,
                "max_events_per_send": s.max_events_per_send, "search_pause_ms": s.search_pause_ms,
                "min_search_chars": s.min_search_chars, "buttons": s.buttons}
    return {"site_name": c.app.site_name, "features": c.features.model_dump(), "insights": insights,
            "site_ui": c.site_ui.model_dump()}  # display settings only (site_ui.ini)


def effective_with_sources() -> list[dict]:
    """Every tunable setting, its current value and where it came from (env / ini / default).
    For the admin Settings page. Nothing here is secret (secrets live in .env, not ini)."""
    current = _flatten(cfg())
    defaults = _flatten(Config())
    in_files: set[str] = set()
    for section, filename in FILES.items():
        path = CONFIG_DIR / filename
        if path.exists():
            parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
            parser.optionxform = str
            try:
                parser.read(path, encoding="utf-8")
            except configparser.Error:
                continue
            if parser.has_section(section):
                in_files |= {f"{section}.{k}" for k in parser[section]}
            if section == "logging" and parser.has_section("logging.levels"):
                in_files.add("logging.levels")
    out = []
    for key, value in current.items():
        section, name = key.split(".", 1)
        env = f"{ENV_PREFIX}{section.upper()}__{name.upper()}"
        source = "env" if env in os.environ else "ini" if key in in_files else "default"
        out.append({"key": key, "value": value, "default": defaults.get(key), "source": source,
                    "file": f"config/{FILES[section]}", "env_var": env})
    return out
