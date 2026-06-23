#!/usr/bin/env python3
"""echo-input skill script — echo ASTROLIFT_INPUT as a structured result.

Bundled executable for the ``echo-input`` local skill. Maps to a
``ToolDef`` under the skill at registration (agentskills.io ``scripts/``
convention). Standalone-runnable so it can be tested in isolation.
"""

from __future__ import annotations

import json
import os
import sys


def echo(raw: str) -> dict[str, object]:
    if not raw:
        return {"echo": None, "note": "no ASTROLIFT_INPUT"}
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {"echo": raw, "word_count": len(raw.split())}
    if isinstance(value, (dict, list)):
        return {"echo": value, "keys": len(value)}
    return {"echo": value, "word_count": len(str(value).split())}


def main() -> int:
    result = echo(os.environ.get("ASTROLIFT_INPUT", ""))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
