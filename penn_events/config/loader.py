"""Loads `master.yaml`: parse, expand generators, validate.

Expansion happens before validation of the final feeder list so that a broken
template surfaces as a normal config error.
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from penn_events.core.errors import ConfigError

from .schema import FeederSpec, GeneratorSpec, MasterConfig

log = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).with_name("master.yaml")
DEFAULT_TAG_RULES_PATH = Path(__file__).with_name("tag_rules.yaml")


def _interpolate(value: Any, variables: dict[str, Any]) -> Any:
    """Recursively substitute `{placeholder}` in every string of a template."""
    if isinstance(value, str):
        try:
            return value.format(**variables)
        except KeyError as exc:
            raise ConfigError(
                f"template references unknown placeholder {exc} "
                f"(available: {sorted(variables)})"
            ) from exc
    if isinstance(value, dict):
        return {k: _interpolate(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, variables) for v in value]
    return value


def expand_generator(generator: GeneratorSpec) -> list[FeederSpec]:
    """Turn one generator into concrete feeder specs.

    Each `for_each` entry may be a bare string (available as `{item}`) or a mapping
    whose keys become placeholders in their own right.
    """
    specs: list[FeederSpec] = []
    inherited = {
        "type": generator.type,
        "enabled": generator.enabled,
        "host": generator.host,
        "source": generator.source,
        "tags": generator.tags,
        "schedule": generator.schedule,
        "timezone": generator.timezone,
        "horizon_days": generator.horizon_days,
    }

    for item in generator.for_each:
        variables = {"item": item} if not isinstance(item, dict) else {"item": item, **item}
        rendered = _interpolate(generator.template, variables)

        merged: dict[str, Any] = {k: v for k, v in inherited.items() if v is not None}
        # Generator tags and per-item tags are additive, not overriding.
        merged["tags"] = sorted(set(generator.tags) | set(rendered.pop("tags", [])))
        merged.update(rendered)

        try:
            specs.append(FeederSpec(**merged))
        except Exception as exc:  # pydantic ValidationError
            raise ConfigError(f"generator {generator.id!r} produced an invalid feeder: {exc}") from exc

    log.debug("generator %s expanded to %d feeders", generator.id, len(specs))
    return specs


def load_config(path: str | Path | None = None) -> MasterConfig:
    """Read, expand and validate the master configuration."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")

    try:
        document = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path} is not valid YAML: {exc}") from exc

    try:
        config = MasterConfig(**document)
    except Exception as exc:
        raise ConfigError(f"{config_path} failed validation: {exc}") from exc

    for generator in config.generators:
        config.feeders.extend(expand_generator(generator))

    duplicates = [i for i, n in Counter(f.id for f in config.feeders).items() if n > 1]
    if duplicates:
        raise ConfigError(f"duplicate feeder ids in {config_path}: {sorted(duplicates)}")

    log.info(
        "loaded %d feeders (%d enabled) from %s",
        len(config.feeders),
        len(config.enabled_feeders()),
        config_path,
    )
    return config


def load_tag_rules(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load `tag_rules.yaml` as {tag: [regex, ...]}."""
    rules_path = Path(path) if path else DEFAULT_TAG_RULES_PATH
    if not rules_path.exists():
        log.warning("no tag rules at %s; keyword tagging disabled", rules_path)
        return {}
    document = yaml.safe_load(rules_path.read_text()) or {}
    rules = document.get("rules", document)
    if not isinstance(rules, dict):
        raise ConfigError(f"{rules_path}: expected a mapping of tag -> patterns")
    return {str(tag): list(patterns) for tag, patterns in rules.items()}
