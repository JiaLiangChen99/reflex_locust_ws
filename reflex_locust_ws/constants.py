"""Default connection settings for Reflex WebSocket load tests."""

from __future__ import annotations

import os

# Reflex Socket.IO mount (see reflex.constants.Endpoint.EVENT).
EVENT_NAMESPACE = "/_event"
SOCKETIO_PATH = "/_event"

DEFAULT_HOST = os.getenv("LOADTEST_HOST", "http://127.0.0.1:8000")
EVENT_RESPONSE_TIMEOUT = float(os.getenv("LOADTEST_EVENT_TIMEOUT", "10"))
CONNECT_TIMEOUT = float(os.getenv("LOADTEST_CONNECT_TIMEOUT", "10"))

# Must match the Reflex version running on the backend (Sec-WebSocket-Protocol).
REFLEX_SUBPROTOCOL = os.getenv("LOADTEST_REFLEX_VERSION", "")
