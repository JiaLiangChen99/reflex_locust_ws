# reflex_locust_ws

English | [中文](README.md)

An **unofficial WebSocket load-testing adapter** for [Reflex](https://reflex.dev/) apps. Built on [Locust](https://locust.io/), it connects to the Reflex backend `/_event` endpoint via Socket.IO, emits events, and records latency and failure rates.

| What it tests | What it does not test |
|---------------|----------------------|
| `@rx.event` handler concurrency & latency | HTTP pages, static assets |
| Max WebSocket connections | REST APIs (use a separate `HttpUser`) |
| State-update round trips (WSR) | Browser rendering & frontend performance |

---

## Table of contents

- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Integrate into your project](#integrate-into-your-project)
- [How it works](#how-it-works)
- [API reference](#api-reference)
- [CLI & environment variables](#cli--environment-variables)
- [Reports & visualization](#reports--visualization)
- [FAQ](#faq)
- [References](#references)

---

## Quick start

### 1. Install

```bash
git clone https://github.com/JiaLiangChen99/reflex_locust_ws.git
cd reflex_locust_ws

# pick one
uv sync
# pip install -e ".[report]"
# poetry install
```

Optional chart dependencies:

```bash
uv pip install matplotlib
# or: pip install "reflex-locust-ws[report]"
```

Verify the CLI:

```bash
reflex-locust-ws discover --help
```

In application code, **import only the decorator** — Locust is not loaded on the Reflex startup path:

```python
from reflex_locust_ws.decorators import ws_loadtest  # zero runtime overhead
```

### 2. Start the Reflex backend

Load tests need only the backend — **no** frontend compile or port 3000:

```bash
reflex run --backend-only --env prod
curl --noproxy '*' http://127.0.0.1:8000/ping   # expect "pong"
```

> **Slow frontend installs:** If `reflex run` hangs on `bun add`, use `--backend-only` for load testing. For full frontend dev, point `.web/bunfig.toml` at a fast registry (e.g. `https://registry.npmmirror.com`) and set `HTTP_PROXY` / `HTTPS_PROXY`. Bun reads **`bunfig.toml`**, not `.npmrc`.

### 3. Discover load-testable events

```bash
reflex-locust-ws discover --app reflex_locust_ws_demo.reflex_locust_ws_demo
```

Example output:

```
Load-test atoms (@ws_loadtest) in reflex_locust_ws_demo.reflex_locust_ws_demo: 2

  [ok] weight=3 archetype=custom path='/' — increment counter (simulated clicks)
         locust: increment
         event:  reflex___state____state.reflex_locust_ws_demo___...increment
  ...
```

### 4. Run load tests

**Recommended — Python runner (local & CI):**

```bash
python tests/load/run.py smoke          # smoke: 5 users, 30s
python tests/load/run.py connections    # WebSocket connections only
python tests/load/run.py ui             # Locust Web UI → http://localhost:8089

python tests/load/run.py smoke --users 10 --run-time 1m
```

**Or invoke Locust directly:**

```bash
locust -f tests/load/locustfile.py --host=http://127.0.0.1:8000
```

Headless example:

```bash
locust -f tests/load/locustfile.py \
  --host=http://127.0.0.1:8000 \
  --headless --users 50 --spawn-rate 5 --run-time 3m \
  --html tests/load/reports/run/report.html \
  --csv tests/load/reports/run/run
```

---

## Repository layout

```
reflex_locust_ws/
├── reflex_locust_ws/          # library source
│   ├── user.py                # ReflexWebSocketUser
│   ├── decorators.py          # @ws_loadtest
│   ├── registry.py            # discover_atoms
│   ├── cli.py                 # discover / report
│   └── report.py              # dashboard generation
├── reflex_locust_ws_demo/     # sample Reflex app (counter)
├── tests/load/                # load-test scripts
│   ├── config.py              # resolve full event names
│   ├── locustfile.py          # business scenario
│   ├── locustfile_connections.py
│   └── run.py                 # python tests/load/run.py smoke
├── rxconfig.py
├── pyproject.toml
├── README.md
└── README.en.md
```

---

## Integrate into your project

### Step 1 — Mark event handlers

Place `@ws_loadtest` **above** `@rx.event` (closer to the function):

```python
from reflex_locust_ws.decorators import ws_loadtest
import reflex as rx

class MyState(rx.State):
    @ws_loadtest(
        weight=3,
        path="/",
        archetype="db_read",
        description="Load item list",
    )
    @rx.event
    def load_items(self):
        ...
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | function name | Metric name in Locust reports |
| `weight` | `1` | Relative weight (shown by `discover`) |
| `path` | `"/"` | `router_data` path template; `{id}` placeholders OK |
| `archetype` | `"custom"` | `db_read` / `db_write` / `broadcast` / `hydrate` / `custom` |
| `payload` | `{}` | Sample payload |
| `description` | `""` | Human-readable note |

> Avoid handler names that shadow built-in `rx.State` methods (e.g. use `reset_count` instead of `reset`).

Parameterized handler:

```python
@ws_loadtest(
    path="/workspace/{project_id}",
    payload={"project_id": 1},
    description="Enter workspace",
)
@rx.event
async def load_workspace(self, project_id: int):
    ...
```

Built-in Reflex events (e.g. `set_is_hydrated`) cannot be decorated — resolve them with `event_full_name` in your load-test config.

### Step 2 — Resolve event names

Reflex registers escaped long event names. Use the CLI or code:

```bash
reflex-locust-ws discover --app myapp.myapp --format json
```

```python
# tests/load/config.py — copy into your project and set APP_MODULE
from reflex.state import State
from reflex_locust_ws.registry import discover_atoms, format_path_template
from reflex_locust_ws.utils import event_full_name

APP_MODULE = "myapp.myapp"
_atoms = {a.locust_name: a for a in discover_atoms(APP_MODULE)}

LOAD_ITEMS = _atoms["load_items"].event_name
HYDRATE = event_full_name(State, "set_is_hydrated")
```

### Step 3 — Write Locust scenarios

Subclass `ReflexWebSocketUser`:

```python
from locust import between, task
from reflex_locust_ws import ReflexWebSocketUser
import config

class MyUser(ReflexWebSocketUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        super().on_start()  # required: open WebSocket
        self.emit_and_wait(
            locust_name="hydrate",
            event_name=config.HYDRATE,
            payload={"value": True},
            router_data=self.router_for_path("/"),
        )

    @task(3)
    def load_items(self) -> None:
        self.emit_and_wait(
            locust_name="load_items",
            event_name=config.LOAD_ITEMS,
            router_data=self.router_for_path("/"),
        )
```

**Connection-only test (no business events):**

```python
import gevent
from locust import between, task
from reflex_locust_ws import ReflexWebSocketUser

class ConnectionOnlyUser(ReflexWebSocketUser):
    wait_time = between(30, 60)

    @task
    def hold(self) -> None:
        gevent.sleep(120)
```

Before large runs: `ulimit -n 65535`.

---

## How it works

```
┌─────────────┐     WebSocket (Socket.IO)      ┌──────────────────┐
│ Locust      │  ── connect /_event?token=… ──▶│ Reflex backend   │
│ ReflexWSUser│  ◀── "event" state update ──── │ (Starlette+SIO)  │
│             │  ── emit("event", {name,…}) ──▶│ @rx.event handlers│
└─────────────┘                                └──────────────────┘
       └── WSR latency recorded in Locust stats
```

1. **`on_start`** — each virtual user opens one persistent WebSocket (one browser tab).
2. **`emit_and_wait`** — sends a Reflex event, waits for the next state push, records elapsed time.
3. **`@ws_loadtest`** — attaches metadata for `discover` only; **no production behavior change**.

| Locust type | Meaning |
|-------------|---------|
| `WS` | WebSocket connect |
| `WSR` | One event round trip (emit → state update) |

---

## API reference

### `ReflexWebSocketUser`

| Method | Description |
|--------|-------------|
| `on_start()` | Connect to `/_event`; subclasses must call `super().on_start()` first |
| `on_stop()` | Disconnect |
| `emit_and_wait(...)` | Emit event, wait for state update, record WSR |
| `router_for_path(path)` | Build `{"pathname", "query", "asPath"}` |

Main `emit_and_wait` args: `locust_name`, `event_name`, `payload`, `router_data`, `timeout`.

### Utilities

```python
from reflex_locust_ws import discover_atoms, event_full_name, ReflexWebSocketUser
from reflex_locust_ws.registry import format_path_template

discover_atoms("myapp.myapp")
event_full_name(State, "set_is_hydrated")
format_path_template("/workspace/{project_id}", project_id=42)
```

---

## CLI & environment variables

### CLI

```bash
reflex-locust-ws discover [--app MODULE] [--format text|json]
reflex-locust-ws report --dir tests/load/reports/smoke
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOADTEST_HOST` | `http://127.0.0.1:8000` | Reflex backend URL |
| `LOADTEST_EVENT_TIMEOUT` | `10` | State-update wait timeout (seconds) |
| `LOADTEST_CONNECT_TIMEOUT` | `10` | WebSocket connect timeout (seconds) |
| `LOADTEST_REFLEX_VERSION` | (auto) | `Sec-WebSocket-Protocol`; must match backend Reflex version |

Common Locust flags: `--host`, `--users`, `--spawn-rate`, `--run-time`, `--processes`.

---

## Reports & visualization

After a headless run:

```bash
reflex-locust-ws report --dir tests/load/reports/smoke
```

| Output | Content |
|--------|---------|
| `dashboard.html` | Summary cards, table, charts |
| `summary.json` | Machine-readable stats |
| `charts/latency_bars.png` | Per-event Median / P95 |
| `charts/timeline.png` | RPS & latency over time |
| `report.html` | Locust native report (`--html`) |

Requires `matplotlib` (`pip install "reflex-locust-ws[report]"`).

---

## FAQ

**`discover` shows `MISSING` or wrong event names**

- Is the handler imported from the app entry module chain?
- Decorator order: `@ws_loadtest` above `@rx.event`.
- Compare `discover` `event:` output with strings in your locustfile.

**Many `TimeoutError`s**

- Is the backend running with `--backend-only` and does `/ping` return `pong`?
- Increase `LOADTEST_EVENT_TIMEOUT`.
- Is the handler blocking too long? Production setups often need Redis + multiple workers.

**`Sec-WebSocket-Protocol` connection failures**

Load generator and server must use the same Reflex version:

```bash
export LOADTEST_REFLEX_VERSION=0.9.5.post2
```

**Does latency include multiple yields?**

`emit_and_wait` stops the timer on the **first** state push. Handlers that chain `yield` updates need careful interpretation of P95.

**Why not `HttpUser`?**

Reflex user interaction goes through WebSocket `/_event`; HTTP load tests cannot simulate event round trips.

---

## References

- [Reflex — How Reflex Works](https://reflex.dev/docs/advanced-onboarding/how-reflex-works/)
- [Reflex #3745 — Load Tests Using Locust](https://github.com/reflex-dev/reflex/issues/3745)
- [Locust documentation](https://docs.locust.io/)

---

## License

MIT (add a `LICENSE` file before publishing to GitHub if needed.)
