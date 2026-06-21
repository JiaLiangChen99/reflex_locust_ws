"""Locust scenario: hold WebSocket connections only (no business events)."""

import gevent
from locust import between, task

from reflex_locust_ws import ReflexWebSocketUser


class ConnectionOnlyUser(ReflexWebSocketUser):
    wait_time = between(30, 60)

    @task
    def hold_connection(self) -> None:
        gevent.sleep(120)
