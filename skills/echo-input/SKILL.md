---
name: echo-input
description: Echo the agent's dispatch input back as a structured result and count its tokens. A trivial local skill used by the sample-agent fixture to exercise the local-skill resolution path (agentskills.io format) at registration.
---

# echo-input

A minimal **local** skill (agentskills.io format) bundled with
`astrolift-sample-agent`. It exists to exercise the spec 38 / spec 39
*local skill* resolution path — a `{ name = "relative/path" }` entry in
`astrolift.toml` `skills` that resolves to a folder in the agent's own
repo and upserts a `Skill` record (+ its `scripts/` → `ToolDef` rows).

## When to use

When you need to confirm a dispatch reached the agent with the expected
input payload, without performing real work. Echo the input back and
report its size.

## Instructions

1. Read the dispatch input from `ASTROLIFT_INPUT` (string or JSON).
2. If it is text, return `{ "echo": <text>, "word_count": N }`.
3. If it is JSON, return `{ "echo": <value>, "keys": N }`.
4. If absent, return `{ "echo": null, "note": "no ASTROLIFT_INPUT" }`.

The bundled `scripts/echo.py` implements this and maps to a `ToolDef`
under this skill at registration.
