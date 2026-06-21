# reflex_locust_ws

[English](README.en.md) | 中文

Reflex 应用的 **WebSocket 压测库**（非官方）。基于 [Locust](https://locust.io/)，通过 Socket.IO 连接 Reflex 后端 `/_event`，发送 event 并统计延迟与失败率。

| 测什么 | 不测什么 |
|--------|----------|
| `@rx.event` handler 并发与响应时间 | HTTP 页面、静态资源 |
| WebSocket 最大连接数 | REST API（需另写 `HttpUser`） |
| 业务 state 更新往返（WSR） | 浏览器渲染与前端性能 |

---

## 目录

- [快速开始](#快速开始)
- [仓库结构](#仓库结构)
- [集成到你的项目](#集成到你的项目)
- [工作原理](#工作原理)
- [API 参考](#api-参考)
- [CLI 与环境变量](#cli-与环境变量)
- [报告与可视化](#报告与可视化)
- [常见问题](#常见问题)
- [参考](#参考)

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/JiaLiangChen99/reflex_locust_ws.git
cd reflex_locust_ws

# 任选其一
uv sync
# pip install -e ".[report]"
# poetry install
```

可选报告图表依赖：

```bash
uv pip install matplotlib
# 或 pip install "reflex-locust-ws[report]"
```

验证 CLI：

```bash
reflex-locust-ws discover --help
```

业务代码中 **只 import 装饰器**，不会把 Locust 拉进 Reflex 启动路径：

```python
from reflex_locust_ws.decorators import ws_loadtest  # 零运行时开销
```

### 2. 启动 Reflex 后端

压测只需 backend，**不需要**编译/启动前端（3000 端口）：

```bash
reflex run --backend-only --env prod
curl --noproxy '*' http://127.0.0.1:8000/ping   # 应返回 "pong"
```

> **国内网络提示：** 若 `reflex run`（含前端）卡在 `bun add`，压测仍可用 `--backend-only` 跳过前端。需要完整前端时，请将 `.web/bunfig.toml` 的 registry 改为国内镜像（如 `https://registry.npmmirror.com`），并设置 `HTTP_PROXY` / `HTTPS_PROXY`。Bun **不读取** `.npmrc`，以 `bunfig.toml` 为准。

### 3. 发现可压测事件

```bash
reflex-locust-ws discover --app reflex_locust_ws_demo.reflex_locust_ws_demo
```

示例输出：

```
Load-test atoms (@ws_loadtest) in reflex_locust_ws_demo.reflex_locust_ws_demo: 2

  [ok] weight=3 archetype=custom path='/' — 递增计数（模拟高频点击）
         locust: increment
         event:  reflex___state____state.reflex_locust_ws_demo___...increment
  ...
```

### 4. 运行压测

**推荐 — Python 脚本（适合本地与 CI）：**

```bash
python tests/load/run.py smoke          # 冒烟：5 用户 30 秒
python tests/load/run.py connections    # 纯 WebSocket 连接
python tests/load/run.py ui             # Locust Web UI → http://localhost:8089

python tests/load/run.py smoke --users 10 --run-time 1m
```

**或直接调用 Locust：**

```bash
locust -f tests/load/locustfile.py --host=http://127.0.0.1:8000
```

Headless 示例：

```bash
locust -f tests/load/locustfile.py \
  --host=http://127.0.0.1:8000 \
  --headless --users 50 --spawn-rate 5 --run-time 3m \
  --html tests/load/reports/run/report.html \
  --csv tests/load/reports/run/run
```

---

## 仓库结构

```
reflex_locust_ws/
├── reflex_locust_ws/          # 库源码
│   ├── user.py                # ReflexWebSocketUser
│   ├── decorators.py          # @ws_loadtest
│   ├── registry.py            # discover_atoms
│   ├── cli.py                 # discover / report
│   └── report.py              # dashboard 生成
├── reflex_locust_ws_demo/     # 示例 Reflex 应用（计数器）
├── tests/load/                # 压测脚本（Locust 场景 + 运行入口）
│   ├── config.py              # 解析 event 全名
│   ├── locustfile.py          # 业务场景
│   ├── locustfile_connections.py
│   └── run.py                 # python tests/load/run.py smoke
├── rxconfig.py
├── pyproject.toml
├── README.md
└── README.en.md
```

---

## 集成到你的项目

### 第一步：标记 event handler

在 `@rx.event` **上方**（更靠近函数）加 `@ws_loadtest`：

```python
from reflex_locust_ws.decorators import ws_loadtest
import reflex as rx

class MyState(rx.State):
    @ws_loadtest(
        weight=3,
        path="/",
        archetype="db_read",
        description="加载列表",
    )
    @rx.event
    def load_items(self):
        ...
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `name` | 函数名 | Locust 报告中的指标名 |
| `weight` | `1` | 相对权重（供 discover 展示） |
| `path` | `"/"` | `router_data` 路径模板，支持 `{id}` |
| `archetype` | `"custom"` | `db_read` / `db_write` / `broadcast` / `hydrate` / `custom` |
| `payload` | `{}` | 样例 payload |
| `description` | `""` | 人类可读说明 |

> 避免使用与 `rx.State` 内置方法同名的 handler（如 `reset`），请改用 `reset_count` 等名称。

带参数的 handler：

```python
@ws_loadtest(
    path="/workspace/{project_id}",
    payload={"project_id": 1},
    description="进入工作区",
)
@rx.event
async def load_workspace(self, project_id: int):
    ...
```

Reflex **内置** event（如 `set_is_hydrated`）无法加装饰器，在压测脚本里用 `event_full_name` 手动指定。

### 第二步：解析 event 名

Reflex 注册的 event 名是转义后的长字符串，用 CLI 或代码解析：

```bash
reflex-locust-ws discover --app myapp.myapp --format json
```

```python
# tests/load/config.py（复制到你的项目并修改 APP_MODULE）
from reflex.state import State
from reflex_locust_ws.registry import discover_atoms, format_path_template
from reflex_locust_ws.utils import event_full_name

APP_MODULE = "myapp.myapp"
_atoms = {a.locust_name: a for a in discover_atoms(APP_MODULE)}

LOAD_ITEMS = _atoms["load_items"].event_name
HYDRATE = event_full_name(State, "set_is_hydrated")
```

### 第三步：编写 Locust 场景

继承 `ReflexWebSocketUser`：

```python
from locust import between, task
from reflex_locust_ws import ReflexWebSocketUser
import config

class MyUser(ReflexWebSocketUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        super().on_start()  # 必须：建立 WebSocket
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

**只测连接数（不发业务 event）：**

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

大规模压测前提高文件描述符：`ulimit -n 65535`。

---

## 工作原理

```
┌─────────────┐     WebSocket (Socket.IO)      ┌──────────────────┐
│ Locust      │  ── connect /_event?token=… ──▶│ Reflex backend   │
│ ReflexWSUser│  ◀── "event" state update ──── │ (Starlette+SIO)  │
│             │  ── emit("event", {name,…}) ──▶│ @rx.event handlers│
└─────────────┘                                └──────────────────┘
       └── 记录 WSR 延迟到 Locust 统计
```

1. **`on_start`** — 每个虚拟用户建立一条持久 WebSocket（等同浏览器一个 tab）。
2. **`emit_and_wait`** — 发送 Reflex event，等待下一次 state 推送，耗时记入 Locust。
3. **`@ws_loadtest`** — 仅附加元数据供 `discover` 使用，**不改变生产行为**。

| Locust Type | 含义 |
|-------------|------|
| `WS` | WebSocket 连接建立 |
| `WSR` | 单次 event 往返（emit → state update） |

---

## API 参考

### `ReflexWebSocketUser`

| 方法 | 说明 |
|------|------|
| `on_start()` | 连接 `/_event`；子类必须先 `super().on_start()` |
| `on_stop()` | 断开连接 |
| `emit_and_wait(...)` | 发送 event 并等待 state 更新，记录 WSR |
| `router_for_path(path)` | 构造 `{"pathname", "query", "asPath"}` |

`emit_and_wait` 主要参数：`locust_name`、`event_name`、`payload`、`router_data`、`timeout`。

### 工具函数

```python
from reflex_locust_ws import discover_atoms, event_full_name, ReflexWebSocketUser
from reflex_locust_ws.registry import format_path_template

discover_atoms("myapp.myapp")
event_full_name(State, "set_is_hydrated")
format_path_template("/workspace/{project_id}", project_id=42)
```

---

## CLI 与环境变量

### CLI

```bash
reflex-locust-ws discover [--app MODULE] [--format text|json]
reflex-locust-ws report --dir tests/load/reports/smoke
```

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `LOADTEST_HOST` | `http://127.0.0.1:8000` | Reflex backend 地址 |
| `LOADTEST_EVENT_TIMEOUT` | `10` | 等待 state 更新超时（秒） |
| `LOADTEST_CONNECT_TIMEOUT` | `10` | WebSocket 连接超时（秒） |
| `LOADTEST_REFLEX_VERSION` | （自动） | `Sec-WebSocket-Protocol`，需与 backend 版本一致 |

Locust 常用参数：`--host`、`--users`、`--spawn-rate`、`--run-time`、`--processes`。

---

## 报告与可视化

Headless 跑完后：

```bash
reflex-locust-ws report --dir tests/load/reports/smoke
```

| 输出 | 内容 |
|------|------|
| `dashboard.html` | 汇总卡片 + 表格 + 图表 |
| `summary.json` | 机器可读统计 |
| `charts/latency_bars.png` | 各 event Median / P95 |
| `charts/timeline.png` | RPS 与延迟随时间变化 |
| `report.html` | Locust 原版（`--html` 生成） |

需要 `matplotlib`（`pip install "reflex-locust-ws[report]"`）。

---

## 常见问题

**discover 报 `MISSING` 或 event 名不对**

- handler 是否在 app 入口 import 链中（否则未注册）。
- 装饰器顺序：`@ws_loadtest` 在 `@rx.event` 上方。
- 对比 `discover` 输出的 `event:` 与 locustfile 中的字符串。

**大量 `TimeoutError`**

- backend 是否 `--backend-only` 且 `/ping` 正常。
- 增大 `LOADTEST_EVENT_TIMEOUT`。
- handler 是否阻塞过久；生产环境建议 Redis + 多 worker。

**`Sec-WebSocket-Protocol` 连接失败**

压测机与 server 的 Reflex 版本必须一致：

```bash
export LOADTEST_REFLEX_VERSION=0.9.5.post2
```

**延迟是否包含多次 yield？**

`emit_and_wait` 在收到**第一次** state 推送时结束计时。链式 `yield` 的 handler 需结合业务解读 P95。

**为什么不能用 HttpUser？**

Reflex 交互走 WebSocket `/_event`，普通 HTTP 压测无法模拟 event 往返。

---

## 参考

- [Reflex — How Reflex Works](https://reflex.dev/docs/advanced-onboarding/how-reflex-works/)
- [Reflex #3745 — Load Tests Using Locust](https://github.com/reflex-dev/reflex/issues/3745)
- [Locust 文档](https://docs.locust.io/)

---

## License

MIT（发布到 GitHub 前请按需补充 `LICENSE` 文件。）
