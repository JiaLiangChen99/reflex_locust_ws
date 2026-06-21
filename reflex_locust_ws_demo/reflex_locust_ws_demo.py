"""Demo Reflex app with @ws_loadtest handlers for reflex_locust_ws."""

import reflex as rx

from reflex_locust_ws.decorators import ws_loadtest


class CounterState(rx.State):
    """Minimal state with load-testable event handlers."""

    count: int = 0
    last_action: str = ""

    @ws_loadtest(
        weight=3,
        path="/",
        archetype="custom",
        description="递增计数（模拟高频点击）",
    )
    @rx.event
    def increment(self) -> None:
        self.count += 1
        self.last_action = "increment"

    @ws_loadtest(
        weight=1,
        path="/",
        archetype="custom",
        name="reset_count",
        description="重置计数",
    )
    @rx.event
    def reset_count(self) -> None:
        self.count = 0
        self.last_action = "reset"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("reflex_locust_ws Demo", size="8"),
            rx.text("计数器示例 — 用 WebSocket 压测 @rx.event handler"),
            rx.heading(CounterState.count, size="9"),
            rx.text(CounterState.last_action, color="gray"),
            rx.hstack(
                rx.button("Increment", on_click=CounterState.increment),
                rx.button("Reset", on_click=CounterState.reset_count, variant="outline"),
                spacing="4",
            ),
            spacing="5",
            align="center",
            min_height="85vh",
            justify="center",
        ),
        padding="2rem",
    )


app = rx.App()
app.add_page(index)
