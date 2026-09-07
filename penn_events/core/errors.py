"""Exception hierarchy for the ingestion platform."""
from __future__ import annotations


class PennEventsError(Exception):
    """Base class for every error raised by this package."""


class ConfigError(PennEventsError):
    """The master YAML is malformed, or references something that does not exist."""


class UnknownFeederTypeError(ConfigError):
    """A feeder spec names a `type` that no module has registered."""


class FetchError(PennEventsError):
    """A feeder could not retrieve its payload."""

    def __init__(self, url: str, message: str, status_code: int | None = None) -> None:
        self.url = url
        self.status_code = status_code
        super().__init__(f"{message} ({url})")


class AdaptError(PennEventsError):
    """A raw record could not be turned into events."""


class SkipRecord(PennEventsError):
    """Raised by an adapter to drop a single record without failing the run."""
