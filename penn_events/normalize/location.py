"""Meeting links and virtual-event detection.

Most Penn calendars have no "meeting link" field; the Zoom URL is buried in the
description or stuffed into the location.  This pulls it out for every source.
"""
from __future__ import annotations

import re

MEETING_HOST_RE = re.compile(
    r"""https?://
    (?:[\w.-]*\.)?
    (?:
        zoom\.us | zoom\.com | [\w-]+\.zoom\.us
      | teams\.microsoft\.com | teams\.live\.com
      | meet\.google\.com
      | [\w-]*\.?webex\.com
      | bluejeans\.com
      | gotomeeting\.com | gotomeet\.me
      | bbb\.[\w.-]+ | whereby\.com
    )
    /[^\s<>"')\]]*""",
    re.IGNORECASE | re.VERBOSE,
)

_VIRTUAL_WORDS = re.compile(
    r"\b(virtual|online|via zoom|zoom only|webinar|livestream|live stream|"
    r"remote(?:ly)?|hybrid|teleconference)\b",
    re.IGNORECASE,
)

_TRAILING_PUNCT = ".,;:)]}>\"'"


def extract_meeting_link(*sources: str | None) -> str | None:
    """First conferencing URL found across the given texts, in priority order."""
    for source in sources:
        if not source:
            continue
        match = MEETING_HOST_RE.search(source)
        if match:
            return match.group(0).rstrip(_TRAILING_PUNCT)
    return None


def looks_virtual(
    location: str | None, description: str | None = None, meeting_link: str | None = None
) -> bool:
    """A meeting link is proof; otherwise fall back to keywords in the location field.

    Description keywords alone are deliberately not enough -- plenty of in-person
    talks mention that slides will be posted online.
    """
    if meeting_link:
        return True
    if location and _VIRTUAL_WORDS.search(location):
        return True
    if location is None and description and _VIRTUAL_WORDS.search(description):
        return True
    return False


def clean_location(value: str | None) -> str | None:
    """Drop a bare URL masquerading as a location, and tidy separators."""
    if not value:
        return None
    text = value.strip().strip(",;|-").strip()
    if not text or text.lower() in {"tbd", "tba", "n/a", "none"}:
        return None
    if text.lower().startswith(("http://", "https://")) and " " not in text:
        return None
    return re.sub(r"\s*[,|]\s*", ", ", text)
