"""Importing this package registers every feeder type with the factory.

`penn_events.pipeline.runner` and `penn_events.cli` import `penn_events.feeders`
(not the individual modules) so that adding a new feeder type only requires adding
the import line below -- nothing else changes.
"""
from .factory import FeederFactory, known_types, register_feeder  # noqa: F401

from . import ics  # noqa: F401,E402
from . import tec_rest  # noqa: F401,E402
from . import jsonld  # noqa: F401,E402
from . import html_css  # noqa: F401,E402
from . import rss  # noqa: F401,E402

__all__ = ["FeederFactory", "known_types", "register_feeder"]
