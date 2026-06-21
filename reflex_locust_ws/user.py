"""Locust User that speaks Reflex's Socket.IO /_event protocol."""

from __future__ import annotations

import time
import uuid
from typing import Any

import gevent
import socketio
from locust import User
from locust.exception import LocustError

from reflex_locust_ws.constants import (
    CONNECT_TIMEOUT,
    DEFAULT_HOST,
    EVENT_NAMESPACE,
    EVENT_RESPONSE_TIMEOUT,
    REFLEX_SUBPROTOCOL,
    SOCKETIO_PATH,
)
from reflex_locust_ws.utils import ensure_no_proxy, resolve_host, resolve_reflex_subprotocol


class ReflexWebSocketUser(User):
    """Virtual user with one persistent Reflex WebSocket session."""

    abstract = True

    token: str
    sio: socketio.Client
    namespace: str = EVENT_NAMESPACE

    def on_start(self) -> None:
        ensure_no_proxy()
        self.token = str(uuid.uuid4())
        self.sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
        self._awaiting: gevent.event.Event | None = None
        self._await_start: float = 0.0

        @self.sio.on("event", namespace=self.namespace)
        def _on_state_update(_data: Any) -> None:
            pending = self._awaiting
            if pending is not None and not pending.ready():
                pending.set()

        host = resolve_host(self)
        connect_url = f"{host}?token={self.token}"
        subprotocol = resolve_reflex_subprotocol(REFLEX_SUBPROTOCOL)
        start = time.perf_counter()
        try:
            self.sio.connect(
                connect_url,
                socketio_path=SOCKETIO_PATH,
                namespaces=[self.namespace],
                transports=["websocket"],
                wait_timeout=CONNECT_TIMEOUT,
                headers={"Sec-WebSocket-Protocol": subprotocol},
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.environment.events.request.fire(
                request_type="WS",
                name="connect",
                response_time=elapsed_ms,
                response_length=0,
                exception=exc,
                context=self.context(),
            )
            raise LocustError(f"WebSocket connect failed: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.environment.events.request.fire(
            request_type="WS",
            name="connect",
            response_time=elapsed_ms,
            response_length=0,
            exception=None,
            context=self.context(),
        )

    def on_stop(self) -> None:
        if getattr(self, "sio", None) and self.sio.connected:
            self.sio.disconnect()

    def emit_and_wait(
        self,
        *,
        locust_name: str,
        event_name: str,
        payload: dict[str, Any] | None = None,
        router_data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        """Send a Reflex event; record latency until the next state update."""
        if not self.sio.connected:
            raise LocustError("WebSocket is not connected")

        if router_data is None:
            router_data = {"pathname": "/", "query": {}, "asPath": "/"}
        if payload is None:
            payload = {}

        body = {
            "name": event_name,
            "router_data": router_data,
            "payload": payload,
        }

        self._awaiting = gevent.event.Event()
        self._await_start = time.perf_counter()
        wait_seconds = timeout or EVENT_RESPONSE_TIMEOUT
        exc: Exception | None = None

        try:
            self.sio.emit("event", body, namespace=self.namespace)
            if not self._awaiting.wait(timeout=wait_seconds):
                exc = TimeoutError(
                    f"No state update within {wait_seconds}s for {event_name}"
                )
        except Exception as caught:
            exc = caught
        finally:
            elapsed_ms = (time.perf_counter() - self._await_start) * 1000
            self.environment.events.request.fire(
                request_type="WSR",
                name=locust_name,
                response_time=elapsed_ms,
                response_length=len(event_name),
                exception=exc,
                context=self.context(),
            )
            self._awaiting = None

        if exc is not None:
            raise LocustError(str(exc)) from exc

    @staticmethod
    def router_for_path(path: str) -> dict[str, Any]:
        from reflex_locust_ws.utils import router_for_path

        return router_for_path(path)
