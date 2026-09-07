from __future__ import annotations

from pathlib import Path

import pytest

from penn_events.config.loader import load_config
from penn_events.core.errors import ConfigError


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def test_generator_expands_one_feeder_per_item(tmp_path):
    config_path = _write(
        tmp_path,
        "master.yaml",
        """
version: 1
feeders: []
generators:
  - id: teams
    type: ics
    host: Penn Athletics
    tags: [athletics]
    for_each: [baseball, soccer]
    template:
      id: "athletics-{item}"
      registry_url: "https://pennathletics.com/sports/{item}/schedule"
      config:
        url: "https://pennathletics.com/sports/{item}/schedule.ics"
""",
    )
    config = load_config(config_path)
    assert {f.id for f in config.feeders} == {"athletics-baseball", "athletics-soccer"}
    baseball = config.by_id("athletics-baseball")
    assert baseball.config["url"] == "https://pennathletics.com/sports/baseball/schedule.ics"
    assert baseball.host == "Penn Athletics"
    assert baseball.tags == ["athletics"]


def test_duplicate_feeder_ids_are_rejected(tmp_path):
    config_path = _write(
        tmp_path,
        "master.yaml",
        """
version: 1
feeders:
  - id: dup
    type: ics
    config: {url: "https://example.upenn.edu/a.ics"}
  - id: dup
    type: ics
    config: {url: "https://example.upenn.edu/b.ics"}
""",
    )
    with pytest.raises(ConfigError, match="duplicate feeder ids"):
        load_config(config_path)


def test_unknown_top_level_key_is_rejected(tmp_path):
    config_path = _write(tmp_path, "master.yaml", "version: 1\nnot_a_real_field: true\n")
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_missing_config_file_is_reported_clearly(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "does-not-exist.yaml")
