"""astrolift-sample-agent — the agent fixture for the validation campaign.

A minimal-but-real Python agent that exercises every agent run mode (spec
33 §4: Task families Once/Loop/Schedule/Trigger + Service). One entrypoint,
mode-aware via ``ASTROLIFT_WORKLOAD_KIND`` / ``RUN_FAMILY``:

* **Task family** (Once / Loop / Schedule / Trigger) — logs the spec 42
  §3.1 diagnostic block, echoes its brief + input, does a trivial unit of
  work, and exits 0. The platform backs this with a k8s **Job**.
* **Service family** — does the same boot work, then serves the spec 42
  §3.1 HTTP debug surface (``GET /health`` + ``GET /debug``) and stays up.
  The platform backs this with a k8s **Deployment** (+ Service + HPA).

Env contract (verified against astrolift-app backend 2026-06-22 — see
README "Env contract" for the discrepancy notes):

Injected by the deploy renderer (``astrolift_manifest/render.py`` →
``_render_agent``), present for a Service-family agent and on the
Deployment shape:
    ASTROLIFT_WORKLOAD_KIND   "agent"
    ASTROLIFT_MAX_RETRIES     int  (from Workload.max_retries, default 5)
    ASTROLIFT_TOOL_TIMEOUT    int  (from Workload.tool_timeout_seconds, 300)

Injected by the dispatch path (``astrolift_dispatch/brief_injector.py``)
into a Task's Job pod:
    ASTROLIFT_BRIEF_ID        the Brief guid (content-addressed snapshot)
    ASTROLIFT_BRIEF_HASH      the Brief content hash
    ASTROLIFT_TASK_ID         the AgentTask guid
    ASTROLIFT_CONTROLLER_URL  the Controller API base; the agent fetches
                              its brief at GET <url>/api/agents/v1/briefs/<id>/

Local / manual-run fallbacks (NOT injected by the platform today — input
→ pod env is spec 38 / #930, "separate, not yet wired"). The agent reads
these so it is runnable standalone and so a manual dispatch payload can be
threaded in once #930 lands:
    ASTROLIFT_BRIEF           inline brief text (fallback when no BRIEF_ID)
    ASTROLIFT_INPUT           the dispatch input payload (string or JSON)
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "info").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("sample-agent")

APP = "sample-agent"
PORT = int(os.environ.get("PORT", "8000"))
START = time.monotonic()

# Non-secret env keys we surface in /debug. Brief/input/secret VALUES are
# never echoed — only presence (spec 42 §3.1: "values redacted").
_REDACTED_KEYS = frozenset(
    {
        "ASTROLIFT_BRIEF",
        "ASTROLIFT_BRIEF_ID",
        "ASTROLIFT_BRIEF_HASH",
        "ASTROLIFT_INPUT",
        "ASTROLIFT_CONTROLLER_URL",
        "ASTROLIFT_TASK_ID",
    }
)
_VISIBLE_KEYS = (
    "LOG_LEVEL",
    "PORT",
    "ASTROLIFT_WORKLOAD_KIND",
    "ASTROLIFT_MAX_RETRIES",
    "ASTROLIFT_TOOL_TIMEOUT",
    "RUN_FAMILY",
    "RUN_MODE",
)


def _version() -> str:
    return os.environ.get("GIT_SHA") or os.environ.get("IMAGE_TAG") or "dev"


def _run_family() -> str:
    """task | service. Service is selected explicitly; everything else is a Task."""
    fam = os.environ.get("RUN_FAMILY", "").strip().lower()
    return "service" if fam == "service" else "task"


def _run_mode() -> str:
    return os.environ.get("RUN_MODE", "once").strip().lower() or "once"


def _read_brief() -> dict[str, str]:
    """Resolve the brief identity the platform handed us.

    Real dispatch hands an ID + hash and expects the agent SDK to GET the
    brief body from the Controller API. We surface the identity and fall
    back to inline ``ASTROLIFT_BRIEF`` text for standalone runs — we do not
    fetch (no SDK / no Controller in the fixture)."""
    brief_id = os.environ.get("ASTROLIFT_BRIEF_ID", "")
    brief_hash = os.environ.get("ASTROLIFT_BRIEF_HASH", "")
    inline = os.environ.get("ASTROLIFT_BRIEF", "")
    return {
        "id": brief_id,
        "hash": brief_hash,
        "source": "controller" if brief_id else ("inline" if inline else "none"),
        "inline_present": "yes" if inline else "no",
    }


def _read_input() -> object:
    """Decode the dispatch input. JSON if it parses, else the raw string."""
    raw = os.environ.get("ASTROLIFT_INPUT", "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def _env_seen() -> list[str]:
    seen = [k for k in _VISIBLE_KEYS if k in os.environ]
    # Presence of redacted keys is informative; their values are not shown.
    seen += [k for k in sorted(_REDACTED_KEYS) if k in os.environ]
    return seen


def _bindings() -> dict[str, str]:
    """Brief presence is the one binding an agent always cares about."""
    brief = _read_brief()
    return {
        "brief": "present" if brief["source"] != "none" else "absent",
        "input": "present" if os.environ.get("ASTROLIFT_INPUT") else "absent",
    }


def _diagnostic() -> dict[str, object]:
    """The spec 42 §3.1 diagnostic block."""
    return {
        "app": APP,
        "version": _version(),
        "kind": "agent",
        "run_family": _run_family(),
        "run_mode": _run_mode(),
        "hostname": socket.gethostname(),
        "uptime_s": round(time.monotonic() - START, 3),
        "now": datetime.now(timezone.utc).isoformat(),
        "env_seen": _env_seen(),
        "bindings": _bindings(),
        "dispatch_budget": {
            "max_retries": os.environ.get("ASTROLIFT_MAX_RETRIES", "unset"),
            "tool_timeout_s": os.environ.get("ASTROLIFT_TOOL_TIMEOUT", "unset"),
        },
        "build": {
            "image": os.environ.get("IMAGE_REF", "unset"),
            "built_at": os.environ.get("BUILT_AT", "unset"),
            "commit": _version(),
        },
    }


def _log_banner() -> None:
    """Structured startup banner (spec 42 §3.1) — logs are useful at boot."""
    d = _diagnostic()
    log.info(
        "starting %s version=%s family=%s mode=%s port=%s bindings=%s budget=%s",
        d["app"],
        d["version"],
        d["run_family"],
        d["run_mode"],
        PORT,
        d["bindings"],
        d["dispatch_budget"],
    )


def perform() -> dict[str, object]:
    """The trivial unit of work: echo the brief + input, return a result.

    A real agent would assemble its brief + skills and act; this fixture
    just proves the dispatch reached it with the right context, then
    produces a deterministic, inspectable result."""
    brief = _read_brief()
    agent_input = _read_input()

    log.info("brief: source=%s id=%s hash=%s", brief["source"], brief["id"] or "-", brief["hash"] or "-")
    log.info("input: %s", json.dumps(agent_input) if agent_input is not None else "<none>")

    # Trivial work: word-count the input if it's text, else echo it back.
    work: dict[str, object]
    if isinstance(agent_input, str):
        work = {"echo": agent_input, "word_count": len(agent_input.split())}
    elif isinstance(agent_input, (dict, list)):
        work = {"echo": agent_input, "keys": len(agent_input)}
    else:
        work = {"echo": None, "note": "no ASTROLIFT_INPUT provided"}

    result = {"ok": True, "brief": brief, "work": work}
    log.info("result: %s", json.dumps(result))
    return result


def run_task() -> int:
    """Task family: diagnostic block, perform, exit 0 (or per RUN_MODE)."""
    _log_banner()
    log.info("diagnostic: %s", json.dumps(_diagnostic()))

    mode = _run_mode()
    if mode == "loop":
        # Loop mode is platform-orchestrated re-dispatch (spec 33 §4 — the
        # controller re-launches the Task up to a concurrency cap). A single
        # process performs one unit and exits; the platform loops it. We do
        # NOT busy-loop in-process — that would defeat the cap + retry model.
        log.info("run_mode=loop: performing one unit; platform re-dispatches")
    perform()
    log.info("task complete, exiting 0")
    return 0


def serve_service() -> int:
    """Service family: serve /health + /debug, stay up."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    _log_banner()
    log.info("diagnostic: %s", json.dumps(_diagnostic()))
    # Do the work once at boot so the service has a result to report, then
    # keep serving its debug surface (a real agent service would loop on a
    # queue / trigger; the fixture just stays healthy + inspectable).
    boot_result = perform()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: object) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 (http.server contract)
            if self.path == "/health":
                self._send(200, {"status": "ok"})
            elif self.path == "/debug":
                self._send(200, {**_diagnostic(), "boot_result": boot_result})
            else:
                self._send(404, {"error": "not found", "paths": ["/health", "/debug"]})

        def log_message(self, fmt: str, *args: object) -> None:
            log.info("http %s", fmt % args)

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("serving on :%s (GET /health, GET /debug)", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        server.shutdown()
    return 0


def main() -> int:
    return serve_service() if _run_family() == "service" else run_task()


if __name__ == "__main__":
    sys.exit(main())
