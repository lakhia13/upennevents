"""The factory seam.

Every feeder module registers itself with `@register_feeder` on import.
`FeederFactory.build(spec, http)` looks up the class by `spec.type`, validates
`spec.config` against that class's declared `config_model`, and constructs it.

Adding a new source type never touches this file: import the new module once
(from `penn_events.feeders` `__init__.py`) and it is available by name in
`master.yaml`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Type

from pydantic import ValidationError

from penn_events.core.errors import ConfigError, UnknownFeederTypeError
from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Feeder

if TYPE_CHECKING:
    from penn_events.config.schema import FeederSpec

log = logging.getLogger(__name__)

_REGISTRY: dict[str, Type[Feeder]] = {}


def register_feeder(feeder_class: Type[Feeder]) -> Type[Feeder]:
    """Class decorator: `@register_feeder` under `feeder_class.type`."""
    type_name = feeder_class.type
    if not type_name:
        raise ValueError(f"{feeder_class.__name__} must set a non-empty `type`")
    existing = _REGISTRY.get(type_name)
    if existing is not None and existing is not feeder_class:
        raise ValueError(
            f"feeder type {type_name!r} already registered to {existing.__name__}, "
            f"cannot also register {feeder_class.__name__}"
        )
    _REGISTRY[type_name] = feeder_class
    return feeder_class


def known_types() -> list[str]:
    return sorted(_REGISTRY)


class FeederFactory:
    """Builds a `Feeder` instance from a validated `FeederSpec`."""

    @staticmethod
    def build(spec: "FeederSpec", http: HttpClient) -> Feeder:
        feeder_class = _REGISTRY.get(spec.type)
        if feeder_class is None:
            raise UnknownFeederTypeError(
                f"feeder {spec.id!r} has unknown type {spec.type!r}; "
                f"known types: {known_types()}"
            )
        try:
            config = feeder_class.config_model(**spec.config)
        except ValidationError as exc:
            raise ConfigError(f"feeder {spec.id!r} ({spec.type}) has invalid config: {exc}") from exc
        return feeder_class(spec, config, http)
