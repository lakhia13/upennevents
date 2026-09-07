"""Tag assignment.

Tags come from three layers, unioned:

1. registry-derived -- the calendar's School/Division and Category columns, so every
   event gets meaningful tags even from a source that publishes none;
2. static -- the `tags:` list on the feeder in master.yaml;
3. rule-based -- regexes from tag_rules.yaml matched against title, description
   and location.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Pattern

from penn_events.config.loader import load_tag_rules

from .text import slugify

log = logging.getLogger(__name__)

# Registry columns are free text; these fold the common variants onto stable tags.
SCHOOL_TAGS = {
    "medicine": "medicine",
    "penn medicine": "health-system",
    "sas": "arts-and-sciences",
    "wharton": "business",
    "athletics": "athletics",
    "engineering": "engineering",
    "libraries": "libraries",
    "university life": "student-life",
    "university": "university-wide",
    "law": "law",
    "design": "design",
    "college houses": "residential",
    "gse": "education",
    "vet": "veterinary",
    "sp2": "social-policy",
    "annenberg": "communication",
    "dental": "dental",
    "arts": "arts",
    "nursing": "nursing",
    "penn global": "global",
    "museum": "museum",
    "srfs": "student-services",
    "hr": "human-resources",
    "provost": "administration",
    "admissions": "admissions",
}

CATEGORY_TAGS = {
    "center": "research-center",
    "center / institute": "research-center",
    "institute": "research-center",
    "department": "academic-department",
    "athletics (team schedule)": "athletics",
    "library": "libraries",
    "school": "school-wide",
    "student life": "student-life",
    "program": "program",
    "residential": "residential",
    "initiative": "initiative",
    "academic deadlines": "deadline",
    "office": "administration",
    "lab": "research-lab",
    "university-wide": "university-wide",
    "graduate group": "graduate",
    "student services": "student-services",
    "alumni": "alumni",
    "museum": "museum",
    "continuing ed": "continuing-education",
    "religious life": "religious-life",
    "global": "global",
}


def registry_tags(school_division: str | None, category: str | None) -> list[str]:
    """Tags implied by a calendar's row in the registry table."""
    tags = []
    if school_division:
        tags.append(SCHOOL_TAGS.get(school_division.strip().lower(), slugify(school_division)))
    if category:
        tags.append(CATEGORY_TAGS.get(category.strip().lower(), slugify(category)))
    return [t for t in tags if t]


class Tagger:
    """Compiles tag_rules.yaml once and applies it to every event."""

    def __init__(self, rules: dict[str, list[str]] | None = None) -> None:
        raw_rules = load_tag_rules() if rules is None else rules
        self._rules: list[tuple[str, Pattern[str]]] = []
        for tag, patterns in raw_rules.items():
            for pattern in patterns:
                try:
                    self._rules.append((slugify(tag), re.compile(pattern, re.IGNORECASE)))
                except re.error as exc:
                    log.warning("bad tag regex for %s: %s -- %s", tag, pattern, exc)
        log.debug("tagger loaded %d patterns", len(self._rules))

    def keyword_tags(self, *texts: str | None) -> list[str]:
        haystack = " \n".join(t for t in texts if t)
        if not haystack:
            return []
        return [tag for tag, pattern in self._rules if pattern.search(haystack)]

    def tags_for(
        self,
        *,
        title: str | None,
        description: str | None,
        location: str | None,
        inherited: Iterable[str] = (),
    ) -> list[str]:
        """Final, deduplicated, sorted tag list for one event."""
        tags = {slugify(t) for t in inherited if t}
        tags.update(self.keyword_tags(title, description, location))
        return sorted(t for t in tags if t)
