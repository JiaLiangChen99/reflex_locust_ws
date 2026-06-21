"""WebSocket load testing for Reflex apps via Locust (/_event only).

Import lightweight symbols from submodules in app code to avoid loading Locust::

    from reflex_locust_ws.decorators import ws_loadtest
"""

from reflex_locust_ws.decorators import LoadTestMeta, ws_loadtest

__all__ = [
    "LoadTestMeta",
    "ReflexWebSocketUser",
    "discover_atoms",
    "event_full_name",
    "router_for_path",
    "ws_loadtest",
]


def __getattr__(name: str):
    if name == "ReflexWebSocketUser":
        from reflex_locust_ws.user import ReflexWebSocketUser

        return ReflexWebSocketUser
    if name == "discover_atoms":
        from reflex_locust_ws.registry import discover_atoms

        return discover_atoms
    if name == "event_full_name":
        from reflex_locust_ws.utils import event_full_name

        return event_full_name
    if name == "router_for_path":
        from reflex_locust_ws.utils import router_for_path

        return router_for_path
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
