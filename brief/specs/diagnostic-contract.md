# Diagnostic contract (spec 42 §3.1)

A sibling context file referenced by the brief README. Loaded as
additional context at dispatch so the agent knows the exact diagnostic
surface it must emit.

Non-HTTP (Task-family) runs log this block to stdout once per run.
Service-family runs additionally expose it at `GET /debug`.

```json
{
  "app": "sample-agent",
  "version": "<git-sha>",
  "kind": "agent",
  "run_family": "task | service",
  "run_mode": "once | loop | schedule | trigger",
  "hostname": "<pod>",
  "uptime_s": 0.12,
  "now": "<iso8601>",
  "env_seen": ["LOG_LEVEL", "PORT", "ASTROLIFT_WORKLOAD_KIND", "..."],
  "bindings": { "brief": "present | absent", "input": "present | absent" },
  "dispatch_budget": { "max_retries": "5", "tool_timeout_s": "300" },
  "build": { "image": "...", "built_at": "...", "commit": "..." }
}
```

Rules:
- Brief/input/secret **values** are never echoed — only presence
  (`bindings`) and non-secret keys (`env_seen`).
- `GET /health` returns `200 {"status":"ok"}` when ready (drives the
  `healthcheck.kind="http"`, `value="/health"` probe).
