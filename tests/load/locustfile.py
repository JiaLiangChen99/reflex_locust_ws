"""Locust scenario: hydrate + increment/reset events."""

from locust import between, task

from reflex_locust_ws import ReflexWebSocketUser

import config


class DemoUser(ReflexWebSocketUser):
    """Simulates one browser tab on the demo counter page."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        super().on_start()
        self.emit_and_wait(
            locust_name="hydrate",
            event_name=config.HYDRATE,
            payload={"value": True},
            router_data=self.router_for_path("/"),
        )

    @task(3)
    def increment(self) -> None:
        self.emit_and_wait(
            locust_name="increment",
            event_name=config.INCREMENT,
            router_data=self.router_for_path("/"),
        )

    @task(1)
    def reset_count(self) -> None:
        self.emit_and_wait(
            locust_name="reset_count",
            event_name=config.RESET,
            router_data=self.router_for_path("/"),
        )
