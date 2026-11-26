from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.schemas.common import OneLine
from app.services.harvest_net import check_env_name, check_url

SourceType = Literal["api", "open_data", "rss", "scrape"]
# The security rules (harvest_net), written once for creating AND editing (R57.ii: they were written twice):
# a HARVEST_ setting name only; https and public addresses only
EnvName = Annotated[str, AfterValidator(check_env_name)]
SourceUrl = Annotated[str, AfterValidator(check_url)]


class HarvestSourceIn(BaseModel):
    name: OneLine = Field(min_length=2, max_length=120)
    source_type: SourceType
    url: SourceUrl = Field(min_length=5, max_length=500)
    auth_env_var: EnvName = Field(default="", max_length=100)
    category: str = Field(default="all", max_length=60)
    is_active: bool = True
    terms_checked: bool = False
    schedule_interval_minutes: int = Field(default=15, ge=1, le=43200)

    @model_validator(mode="after")
    def validate_rules(self):
        # Scraping sources stay off until the admin ticks "terms checked"
        if self.source_type == "scrape" and self.is_active and not self.terms_checked:
            raise ValueError("Scrape source stays off until terms are checked.")
        return self


class HarvestSourceUpdate(BaseModel):
    name: OneLine | None = Field(default=None, min_length=2, max_length=120)
    url: SourceUrl | None = Field(default=None, min_length=5, max_length=500)  # editing: the same checks
    auth_env_var: EnvName | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None
    terms_checked: bool | None = None
    schedule_interval_minutes: int | None = Field(default=None, ge=1, le=43200)


class HarvestSourceOut(BaseModel):
    id: int
    name: str
    source_type: str
    url: str
    auth_env_var: str
    category: str
    is_active: bool
    terms_checked: bool
    schedule_interval_minutes: int
    last_run_at: datetime | None
    last_status: str
    created_at: datetime


class HarvestRunOut(BaseModel):
    id: int
    source_id: int
    source_name: str = ""
    source_type: str = ""
    status: str
    found_count: int
    accepted_count: int
    dropped_count: int
    drop_reasons: dict
    error_message: str
    started_at: datetime
    finished_at: datetime | None
