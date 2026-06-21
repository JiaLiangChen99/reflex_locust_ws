"""Resolve Reflex event names once at import (used by locustfiles)."""

from reflex.state import State

from reflex_locust_ws.registry import discover_atoms
from reflex_locust_ws.utils import event_full_name

APP_MODULE = "reflex_locust_ws_demo.reflex_locust_ws_demo"

_atoms = {a.locust_name: a for a in discover_atoms(APP_MODULE)}

INCREMENT = _atoms["increment"].event_name
RESET = _atoms["reset_count"].event_name
HYDRATE = event_full_name(State, "set_is_hydrated")
