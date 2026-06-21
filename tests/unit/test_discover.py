"""Smoke tests that do not require a running Reflex server."""

from reflex_locust_ws.registry import discover_atoms


def test_discover_demo_handlers() -> None:
    atoms = discover_atoms("reflex_locust_ws_demo.reflex_locust_ws_demo")
    names = {a.locust_name for a in atoms}
    assert "increment" in names
    assert "reset_count" in names
    assert all(a.registered for a in atoms)
