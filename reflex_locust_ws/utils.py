"""Shared helpers (no Locust import — safe for Reflex app startup)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from locust import User


def ensure_no_proxy() -> None:
    """Bypass HTTP proxies for localhost Reflex backends."""
    existing = os.environ.get("NO_PROXY", "")
    for host in ("127.0.0.1", "localhost"):
        if host not in existing:
            existing = f"{existing},{host}".strip(",")
    os.environ["NO_PROXY"] = existing
    os.environ["no_proxy"] = existing


def resolve_host(user: User, *, default_host: str | None = None) -> str:
    from reflex_locust_ws.constants import DEFAULT_HOST

    host = (user.host or default_host or DEFAULT_HOST).rstrip("/")
    if not host.startswith("http"):
        host = f"http://{host}"
    return host


def router_for_path(path: str) -> dict[str, Any]:
    return {"pathname": path, "query": {}, "asPath": path}


def event_full_name(state_cls: type, handler: str) -> str:
    """Registered Reflex event name (State.get_full_name(), not format_state_name)."""
    return f"{state_cls.get_full_name()}.{handler}"


def resolve_reflex_subprotocol(explicit: str = "") -> str:
    if explicit:
        return explicit
    from reflex.constants import Reflex

    return Reflex.VERSION
