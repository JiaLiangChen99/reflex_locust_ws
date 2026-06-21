"""Discover ``@ws_loadtest``-decorated handlers in a Reflex app."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from typing import Any

import reflex as rx

from reflex_locust_ws.decorators import LoadTestMeta, get_loadtest_meta
from reflex_locust_ws.utils import event_full_name


@dataclass(frozen=True)
class LoadTestAtom:
    """One discoverable WebSocket load-test target."""

    locust_name: str
    event_name: str
    state_class: str
    handler: str
    weight: int
    path: str
    archetype: str
    payload: dict[str, Any]
    description: str
    registered: bool


def _handler_fn(member: Any) -> Any | None:
    """Extract the underlying Python function from a State class member."""
    if inspect.isfunction(member) or inspect.ismethod(member):
        return member
    fn = getattr(member, "fn", None)
    if callable(fn):
        return fn
    return None


def _iter_state_classes_in_module(module: Any) -> list[type[rx.State]]:
    classes: list[type[rx.State]] = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, rx.State) or obj is rx.State:
            continue
        try:
            if inspect.isabstract(obj):
                continue
        except TypeError:
            pass
        classes.append(obj)
    return classes


def _modules_to_scan(app_module: str) -> list[Any]:
    root = importlib.import_module(app_module)
    modules = [root]

    # Also scan sibling packages (e.g. roomdesign.components.*).
    parts = app_module.split(".")
    if len(parts) >= 2:
        parent_name = ".".join(parts[:-1])
        leaf = parts[-1]
        try:
            parent = importlib.import_module(parent_name)
            sub_pkg = getattr(parent, leaf, None)
            if sub_pkg is not None and hasattr(sub_pkg, "__path__"):
                prefix = sub_pkg.__name__ + "."
                for _importer, mod_name, ispkg in pkgutil.walk_packages(
                    sub_pkg.__path__, prefix=prefix
                ):
                    if not ispkg:
                        modules.append(importlib.import_module(mod_name))
        except ImportError:
            pass

        components = getattr(parent, "components", None)
        if components is not None and hasattr(components, "__path__"):
            prefix = components.__name__ + "."
            for _importer, mod_name, ispkg in pkgutil.walk_packages(
                components.__path__, prefix=prefix
            ):
                if not ispkg:
                    modules.append(importlib.import_module(mod_name))

    return modules


def _handlers_from_app(app_module: str) -> list[tuple[type[rx.State], str, LoadTestMeta]]:
    importlib.import_module(app_module)
    found: list[tuple[type[rx.State], str, LoadTestMeta]] = []
    seen: set[tuple[str, str, str]] = set()

    for module in _modules_to_scan(app_module):
        for state_cls in _iter_state_classes_in_module(module):
            for handler_name, member in state_cls.__dict__.items():
                if handler_name.startswith("_"):
                    continue
                fn = _handler_fn(member)
                if fn is None:
                    continue
                meta = get_loadtest_meta(fn)
                if meta is None:
                    continue
                key = (state_cls.__module__, state_cls.__name__, handler_name)
                if key in seen:
                    continue
                seen.add(key)
                found.append((state_cls, handler_name, meta))

    return found


def discover_atoms(app_module: str = "roomdesign.roomdesign") -> list[LoadTestAtom]:
    """Import the app and list handlers decorated with ``@ws_loadtest``."""
    importlib.import_module(app_module)

    try:
        from reflex_base.registry import RegistrationContext

        registered = set(RegistrationContext.get().event_handlers.keys())
    except LookupError:
        registered = set()
    atoms: list[LoadTestAtom] = []

    for state_cls, handler_name, meta in _handlers_from_app(app_module):
        full_name = event_full_name(state_cls, handler_name)
        atoms.append(
            LoadTestAtom(
                locust_name=meta.name,
                event_name=full_name,
                state_class=f"{state_cls.__module__}.{state_cls.__name__}",
                handler=handler_name,
                weight=meta.weight,
                path=meta.path,
                archetype=meta.archetype,
                payload=dict(meta.payload),
                description=meta.description,
                registered=full_name in registered,
            )
        )

    return sorted(atoms, key=lambda a: (a.archetype, a.locust_name))


def format_path_template(path: str, **values: Any) -> str:
    """Replace ``{project_id}``-style placeholders in a path template."""
    try:
        return path.format(**values)
    except KeyError:
        return path
