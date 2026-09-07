"""Repository base.

Repositories are the *only* modules that issue SQL.  Feeders and adapters never
import from `penn_events.db.models` and never hold a session -- that is what makes a
new source type cheap to add.
"""
from __future__ import annotations

from sqlalchemy.orm import Session


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session
