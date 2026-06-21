"""Decorators to mark Reflex event handlers for WebSocket load tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

LOADTEST_META_ATTR = "_reflex_locust_ws_meta"


@dataclass(frozen=True)
class LoadTestMeta:
    """Metadata attached by ``@ws_loadtest`` to an event handler."""

    name: str
    weight: int = 1
    path: str = "/"
    archetype: str = "custom"
    payload: dict[str, Any] = field(default_factory=dict)
    description: str = ""


def ws_loadtest(
    *,
    name: str | None = None,
    weight: int = 1,
    path: str = "/",
    archetype: str = "custom",
    payload: dict[str, Any] | None = None,
    description: str = "",
) -> Callable[[F], F]:
    """Mark an ``@rx.event`` handler as a load-test atom (single WebSocket event).

    Apply **above** ``@rx.event`` (closer to the function)::

        @ws_loadtest(weight=3, path="/", archetype="db_read")
        @rx.event
        def load_projects(self):
            ...

    Args:
        name: Locust metric name (defaults to the handler function name).
        weight: Relative weight when generating tasks from the registry.
        path: ``router_data`` path template (``{project_id}`` allowed).
        archetype: Category: ``idle``, ``hydrate``, ``db_read``, ``db_write``,
            ``broadcast``, ``custom``.
        payload: Static sample payload for the event (optional).
        description: Human-readable note shown by ``discover``.
    """

    def decorator(fn: F) -> F:
        meta = LoadTestMeta(
            name=name or fn.__name__,
            weight=weight,
            path=path,
            archetype=archetype,
            payload=dict(payload or {}),
            description=description,
        )
        setattr(fn, LOADTEST_META_ATTR, meta)
        return fn

    return decorator


def get_loadtest_meta(fn: Any) -> LoadTestMeta | None:
    """Return load-test metadata from a handler function, if present."""
    return getattr(fn, LOADTEST_META_ATTR, None)
