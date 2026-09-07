"""Pydantic schema for the master YAML.

The whole document is validated on load, so a typo in `master.yaml` fails at
start-up with a pointed message rather than halfway through a scrape.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Defaults(BaseModel):
    """Applied to every feeder that does not override them."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = "America/New_York"
    user_agent: str = "PennEventsBot/1.0 (+https://github.com/upennevents)"
    timeout_seconds: float = 30.0
    retries: int = 3
    rate_limit_per_host: float = 0.5
    horizon_days: int = 180
    schedule: str = "0 */6 * * *"


class FeederSpec(BaseModel):
    """One configured calendar: what to fetch, how to fetch it, what to call it."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    enabled: bool = True

    # Links this feeder to its row in the `calendars` table (table 1).
    registry_url: str | None = None

    host: str | None = None
    source: str | None = None
    source_calendar_name: str | None = None
    tags: list[str] = Field(default_factory=list)

    schedule: str | None = None
    timezone: str | None = None
    horizon_days: int | None = None

    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, value: str) -> str:
        if not value or any(c.isspace() for c in value):
            raise ValueError(f"feeder id must be a non-empty slug, got {value!r}")
        return value

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return sorted({v.strip().lower().replace(" ", "-") for v in values if v.strip()})


class GeneratorSpec(BaseModel):
    """Expands one template over a list of items into many `FeederSpec`s.

    College Houses (13), PSOM LiveWhale groups (37) and varsity teams (31) are
    identical patterns over a slug list; hand-writing them would make the YAML
    unmaintainable.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    enabled: bool = True
    host: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    schedule: str | None = None
    timezone: str | None = None
    horizon_days: int | None = None
    for_each: list[Any]
    template: dict[str, Any]

    @model_validator(mode="after")
    def _template_has_id(self) -> "GeneratorSpec":
        if "id" not in self.template:
            raise ValueError(f"generator {self.id!r}: template must define an 'id'")
        return self


class MasterConfig(BaseModel):
    """The parsed, generator-expanded master YAML."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    defaults: Defaults = Field(default_factory=Defaults)
    feeders: list[FeederSpec] = Field(default_factory=list)
    generators: list[GeneratorSpec] = Field(default_factory=list)

    def enabled_feeders(self) -> list[FeederSpec]:
        return [f for f in self.feeders if f.enabled]

    def by_id(self, feeder_id: str) -> FeederSpec | None:
        return next((f for f in self.feeders if f.id == feeder_id), None)

    def schedule_for(self, spec: FeederSpec) -> str:
        return spec.schedule or self.defaults.schedule

    def timezone_for(self, spec: FeederSpec) -> str:
        return spec.timezone or self.defaults.timezone

    def horizon_for(self, spec: FeederSpec) -> int:
        return spec.horizon_days if spec.horizon_days is not None else self.defaults.horizon_days
