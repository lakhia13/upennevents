"""The interface seam.

`Feeder` says how to get bytes off the internet.  `Adapter` says how to turn those
bytes into events.  Nothing else in the pipeline needs to know about either.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator, ClassVar, Iterable, Type

from pydantic import BaseModel

from .http import HttpClient
from .models import FeedContext, NormalizedEvent, RawRecord

if TYPE_CHECKING:  # avoids a config <-> core import cycle at runtime
    from penn_events.config.schema import FeederSpec


class Adapter(ABC):
    """Maps one source format onto `NormalizedEvent`.

    Adapters do field mapping only.  Timezone resolution, meeting-link extraction,
    tagging and hashing are cross-cutting and run once for every source in
    `penn_events.normalize.pipeline`.
    """

    @abstractmethod
    def adapt(self, record: RawRecord, ctx: FeedContext) -> Iterable[NormalizedEvent]:
        """Yield zero or more events from a single fetched record."""


class Feeder(ABC):
    """Retrieves raw content for one configured calendar.

    Subclasses declare `type` (the YAML discriminator) and `config_model` (a Pydantic
    model for their `config:` block), then register themselves with the factory.
    """

    type: ClassVar[str]
    config_model: ClassVar[Type[BaseModel]]

    def __init__(self, spec: "FeederSpec", config: BaseModel, http: HttpClient) -> None:
        self.spec = spec
        self.config = config
        self.http = http

    @property
    def id(self) -> str:
        return self.spec.id

    @abstractmethod
    def fetch(self) -> AsyncIterator[RawRecord]:
        """Yield raw records.  Implement as `async def` with `yield`."""

    @abstractmethod
    def adapter(self) -> Adapter:
        """The adapter that understands this feeder's output format."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.spec.id!r}>"
