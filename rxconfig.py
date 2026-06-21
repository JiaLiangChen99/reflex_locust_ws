import reflex as rx

config = rx.Config(
    app_name="reflex_locust_ws_demo",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)