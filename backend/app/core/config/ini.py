"""Tunable settings from config/*.ini, applied live (no restart).

Secrets and per-environment values stay in .env (see __init__.py). Everything a person
may want to tune (SLA minutes, batch sizes, rate limits, log levels, feature on/off)
lives in the repo-root config/ folder, one file per area.

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
import threading
import time
from pathlib import Path
from typing import Callable, Literal

from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

log = logging.getLogger("app.config")

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR") or Path(__file__).resolve().parents[4] / "config")
CHECK_EVERY_SECONDS = 3
ENV_PREFIX = "KJS__"


# ---------- The shape of every file (types, ranges, defaults) ----------
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"  # 24-hour time like 09:30. A typo ("09.30") is refused, not used.


class AppIni(BaseModel):
    site_name: str = "KJS India"
    timezone: str = "Asia/Kolkata"
    page_size: int = Field(50, ge=1, le=500)
    lead_rate_per_hour: int = Field(5, ge=1)  # enquiries per IP per hour
    koko_rate_per_hour: int = Field(40, ge=1)  # chat messages per IP per hour
    login_failures_per_ip: int = Field(100, ge=1)  # wrong passwords per network per 15 min (all emails)
    signups_per_ip_per_hour: int = Field(30, ge=1)  # the office shares one address: go-live day
    jobs_enabled: bool = True
    jobs_interval_seconds: int = Field(60, ge=5)  # how often background checks run
    jobs_hours: str = Field("08:00-21:00", pattern=r"^\d{2}:\d{2}-\d{2}:\d{2}$")  # IST, Mon-Sat
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


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingIni(BaseModel):
    level: LogLevel = "INFO"  # a typo like "verbose" is refused; the last good config stays
    format: str = "pretty"  # pretty (dev) | json (staging, production)
    show_personal_data: bool = False  # true only on a dev machine
    levels: dict[str, LogLevel] = Field(default_factory=dict)  # [logging.levels] app.services.lead = DEBUG


class StorageIni(BaseModel):
    max_upload_mb: int = Field(25, ge=1, le=500)
    allowed_types: list[str] = Field(default_factory=lambda: [
        "pdf", "png", "jpg", "jpeg", "webp", "xlsx", "xls", "docx", "doc", "csv", "txt", "zip"])


class Config(BaseModel):
    app: AppIni = AppIni()
    features: FeaturesIni = FeaturesIni()
    sla: SlaIni = SlaIni()
    assign: AssignIni = AssignIni()
    alerts: AlertsIni = AlertsIni()
    koko: KokoIni = KokoIni()
    logging: LoggingIni = LoggingIni()
    storage: StorageIni = StorageIni()


# file name -> section it fills
FILES = {name: f"{name}.ini" for name in Config.model_fields}
LIST_FIELDS = {"thresholds", "channels", "allowed_types"}


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

    for values in raw.values():
        for k in LIST_FIELDS & values.keys():
            if isinstance(values[k], str):
                values[k] = [x.strip() for x in values[k].split(",") if x.strip()]
    return raw


def _validate(raw: dict) -> Config:
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        section, key = (list(first["loc"]) + ["?", "?"])[:2]
        raise ValueError(f"config/{FILES.get(section, section)}: '{key}' {first['msg']}") from e


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
    return {"site_name": c.app.site_name, "features": c.features.model_dump()}


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
