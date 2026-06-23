# astrolift-sample-agent

The **agent fixture** (R8) for the Astrolift validation campaign
([spec 42](https://github.com/calliopeai/astrolift-spec) §2, §3, §5). A
minimal-but-real Python agent (`kind=agent` workload) that echoes its
brief + input, emits the §3.1 diagnostic block, and exercises **every
agent run mode** (spec 33 §4: Task families Once/Loop/Schedule/Trigger +
Service, incl. scheduled scaling).

> ⚠️ **Read [Spec-vs-code](#spec-vs-code) first.** The spec-33 agent
> *run-spec* (`run_family` / `run_mode` / `run_cron_expression` /
> `run_paused` / `run_max_parallel`) is **designed but not yet built** in
> the backend — it is spec 33's unbuilt PR-1. The run-mode manifest
> variants here are authored against that documented target, with the
> spec'd-but-absent fields **commented** and the closest *verified*
> mechanism live. Every manifest parses against the real backend parser
> today.

## Topology

```
astrolift-sample-agent/
├── agent/main.py              # the agent: mode-aware entrypoint
│   └── __init__.py
├── brief/                     # spec-38 brief folder
│   ├── README.md              # entry (system prompt + role)
│   └── specs/
│       └── diagnostic-contract.md   # sibling context ref
├── skills/echo-input/         # spec-38/39 LOCAL skill (agentskills.io)
│   ├── SKILL.md               # frontmatter: name + description
│   └── scripts/echo.py        # bundled script → ToolDef at registration
├── astrolift.toml             # kind=agent manifest + brief/skills
├── manifests/                 # run-mode variants (spec 42 §5)
│   ├── once.toml      loop.toml      schedule.toml
│   ├── trigger.toml   service.toml   scaled.toml
├── Dockerfile                 # python:3.12-slim
├── requirements.txt           # stdlib-only (empty)
└── .github/workflows/build.yml  # → docker.io/calliopeai/astrolift-sample-agent
```

The agent is **one entrypoint, mode-aware** (`agent/main.py`):

- **Task family** (`RUN_FAMILY` unset / `task`) — logs the diagnostic
  block, echoes brief + input, performs one trivial unit of work, **exits
  0**. The platform backs this with a k8s **Job**.
- **Service family** (`RUN_FAMILY=service`) — same boot work, then serves
  the debug surface and **stays up**. The platform backs this with a k8s
  **Deployment** (+ Service + HPA).

## Debug surface (spec 42 §3.1)

Service-family exposes:

| Endpoint | Returns |
|---|---|
| `GET /health` | `200 {"status":"ok"}` — drives the `healthcheck.kind="http"`, `value="/health"` probe |
| `GET /debug` | the diagnostic block (app, version, kind, hostname, uptime, `env_seen`, `bindings`, `dispatch_budget`, `build`) + `boot_result` |

Task-family logs the same diagnostic block to stdout once per run. Brief /
input / secret **values are never echoed** — only presence (`bindings`)
and non-secret keys (`env_seen`).

## Run modes (spec 33 §4) → manifest variants (spec 42 §5)

| Variant | Family | Mode | k8s shape | Status today |
|---|---|---|---|---|
| `manifests/once.toml` | Task | Once | Job | **live** — the only end-to-end-wired mode |
| `manifests/loop.toml` | Task | Loop | Job (re-dispatched) | run-spec **unbuilt** (PR-1 + PR-6) |
| `manifests/schedule.toml` | Task | Schedule | Job (cron-fired) | run-spec **unbuilt** (PR-1 + PR-4) |
| `manifests/trigger.toml` | Task | Trigger | Job (webhook/event) | run-spec **unbuilt** (PR-1 + PR-6) |
| `manifests/service.toml` | Service | — | Deployment + Service + HPA | **live shape** (family selector unbuilt) |
| `manifests/scaled.toml` | Service | scheduled-scaling | Deployment + cron→replica patch | scaling **unbuilt** (PR-1 + PR-5) |

The in-pod entrypoint reads `RUN_FAMILY` / `RUN_MODE` from container env
(set in each variant) so it behaves correctly **now**, independent of the
platform run-spec. For Loop, the process still performs one unit and exits
0 — the *looping* is the platform's job (re-dispatch up to a cap), never
an in-process busy-loop.

## Brief + skills (spec 38 / spec 39)

`astrolift.toml` points (it does not inline) at:

- **`brief = "brief/README.md"`** — a spec-38 brief folder; the README is
  the entry, `brief/specs/diagnostic-contract.md` is a sibling context ref
  loaded at dispatch.
- **`skills = [{ echo-input = "skills/echo-input" }, "shell"]`** —
  - `echo-input` is a **local** skill (a folder in this repo,
    agentskills.io `SKILL.md` + `scripts/`), exercising the local-skill
    resolution path.
  - `"shell"` is a **bare name** → resolves from the built-in
    `astrolift-skills` baseline catalogue (spec 39 §"v0.1 starter set").

## Env contract

The agent reads three groups of env vars. Verified against the
astrolift-app backend (`astrolift_manifest/render.py`,
`astrolift_dispatch/brief_injector.py`), 2026-06-22:

**Injected by the deploy renderer** (`_render_agent`) — present on the
Deployment shape (Service-family agents):

| Var | Source |
|---|---|
| `ASTROLIFT_WORKLOAD_KIND` | literal `"agent"` |
| `ASTROLIFT_MAX_RETRIES` | `Workload.max_retries` (default 5) |
| `ASTROLIFT_TOOL_TIMEOUT` | `Workload.tool_timeout_seconds` (default 300) |

**Injected by the dispatch path** (`brief_injector`) — present in a
Task's Job pod:

| Var | Source |
|---|---|
| `ASTROLIFT_BRIEF_ID` | the Brief guid |
| `ASTROLIFT_BRIEF_HASH` | the Brief content hash |
| `ASTROLIFT_TASK_ID` | the AgentTask guid |
| `ASTROLIFT_CONTROLLER_URL` | Controller API base — the agent fetches its brief at `GET <url>/api/agents/v1/briefs/<id>/` |

**Local / manual-run fallbacks** — NOT injected by the platform today
(input → pod env is spec 38 / #930, "separate, not yet wired"). Read so
the agent is runnable standalone:

| Var | Meaning |
|---|---|
| `ASTROLIFT_BRIEF` | inline brief text (fallback when no `ASTROLIFT_BRIEF_ID`) |
| `ASTROLIFT_INPUT` | dispatch input payload (string or JSON) |

> The fixture does **not** fetch the brief from the Controller API (no SDK
> / no Controller in a fixture) — it surfaces the brief *identity*
> (`id` / `hash` / `source`) and falls back to inline `ASTROLIFT_BRIEF`.

## Run it locally

```bash
# Task family (Once) — performs once, exits 0
python -m agent.main

# Task family with brief identity + JSON input
ASTROLIFT_BRIEF_ID=abc ASTROLIFT_BRIEF_HASH=def \
  ASTROLIFT_INPUT='{"task":"echo"}' python -m agent.main

# Service family — serves /health + /debug
RUN_FAMILY=service PORT=8000 python -m agent.main
curl localhost:8000/health
curl localhost:8000/debug

# Docker
docker build -t astrolift-sample-agent .
docker run --rm -e ASTROLIFT_INPUT='hi' astrolift-sample-agent          # Task
docker run --rm -p 8000:8000 -e RUN_FAMILY=service astrolift-sample-agent  # Service
```

## Build & publish

`.github/workflows/build.yml` builds on push to `main` and pushes to
**`docker.io/calliopeai/astrolift-sample-agent`** tagged `main-<sha7>` +
`latest`, using the org-level secrets `DOCKERHUB_USERNAME` /
`DOCKERHUB_TOKEN` (mirrors `astrolift-agents/build-images.yml`). Deploys
pin the deterministic `main-<sha7>` tag (campaign blocker B3). The
workflow also runs a Task-family smoke test (exits 0) before pushing.

## Spec-vs-code

The single most important thing to know about this fixture. Spec 33's
agent **run-spec** is **designed, not built**. Spec 33 itself says
*"Status: design — agreed in dialogue 2026-06-17, not yet built"*, and its
entire "Sequenced PR Build Plan" (PR-1 … PR-12) is forward-looking. (A
prior note claimed PR #924–929 merged the run-spec — that is **stale**;
the run-spec is spec-33 PR-1, unmerged as of 2026-06-22.)

**Verified present on `Workload` (`models/workload.py`), used by these
fixtures:**

| Field | Default | Injected as |
|---|---|---|
| `kind = "agent"` | — | pod annotation `astrolift.dev/workload-kind: agent` |
| `max_retries` | 5 | `ASTROLIFT_MAX_RETRIES` |
| `tool_timeout_seconds` | 300 | `ASTROLIFT_TOOL_TIMEOUT` |
| `result_ttl_hours` | 72 | (AgentRun retention) |
| `agent_variant` / `agent_runtime` | "" | (base-image / runtime preset selectors) |
| `replicas`, `hpa_*`, `cpu_*`, `memory_*` | — | Deployment shape (Service family) |

**Spec'd (spec 33 §4 / PR-1, PR-4, PR-5, PR-6) but ABSENT in code** — the
run-mode variants carry these **commented**, with a verified fallback live:

| Spec field | Run mode it gates | Spec 33 PR | In code? | Fixture stand-in |
|---|---|---|---|---|
| `run_family` (`task`/`service`) | family selector | PR-1 | ❌ | `RUN_FAMILY` container env + always-Deployment render |
| `run_mode` (`once`/`loop`/`schedule`/`trigger`) | Task mode | PR-1 | ❌ | `RUN_MODE` container env |
| `run_cron_expression` | Schedule | PR-1 (read by PR-4) | ❌ | `schedule` field (inert — see below) |
| `run_paused` | Schedule/Loop/Trigger pause | PR-1 | ❌ | — (documented) |
| `run_max_parallel` | Loop concurrency cap | PR-1 (enforced PR-6) | ❌ | — (documented) |
| scheduled-scaling cron pair (`scale_up/down_cron` + targets) | Service scaled-scaling | PR-5 (explicitly deferred from PR-1) | ❌ | CPU HPA (`hpa_*`) |
| trigger binding (webhook/event → agent + input map) | Trigger | PR-6 | ❌ (no manifest key planned — platform-side `/webhooks` config) | — (documented) |

**Authored speculatively (commented in the variants, not in code):** all
seven rows above. None of the `run_*` fields can be set in a manifest
today without being silently ignored or — for `run_cron_expression` —
needing the unbuilt agent-cron tick.

**One sharper-than-expected finding:** `Workload.schedule` *is* a verified
field, but the parser **drops it for any kind ≠ `cronjob`**
(`parser.py:127`: `schedule = d.get("schedule") if kind == "cronjob" else
None`). So on `kind=agent` the `schedule` key in `schedule.toml` parses
without error but is **discarded at parse time** — not merely unused. The
spec-intended Schedule path is `kind=agent` + `run_cron_expression` (an
agent-Task dispatch), *not* a CronJob.

**All seven manifests parse cleanly** against the live backend parser
(`astrolift_manifest/parser.parse_raw`, verified 2026-06-22): `kind=agent`
with `max_retries` / `tool_timeout_seconds` / `result_ttl_hours`,
one `is_primary` container, `http` healthcheck.
