"""External planner mode: the engine <-> brain boundary as files/stdin.

The engine writes the planner context as JSON to a boundary file and reads
back ONE action JSON at a time (same schema as LLMPlanner). This lets any
external brain drive the engine: a human, another agent, or a test driver.

Protocol (file mode):
- engine writes  <boundary_dir>/context_<n>.json   (the planner context,
  with non-serialisable helpers such as client_builder REMOVED — an
  external brain must say what to write; for the API tool the engine
  offers a `build_client` action, see below)
- driver writes  <boundary_dir>/action_<n>.json    (one action object)
- engine polls for the action file (timeout), applies it through the HANDS.

Extra action type for external mode:
  build_client {extra_headers?, amount_field?} — Stranger API only: the
  engine itself builds the client snippet from the docs (plus the driver's
  corrections) and writes it. This keeps the docs-only rule enforceable.
"""

from __future__ import annotations

import json
import os
import time

from .planners import Action, Planner, PlannerError


class ExternalPlanner(Planner):
    name = "external"

    def __init__(self, boundary_dir, timeout=600, poll=0.25):
        self.dir = boundary_dir
        self.timeout = timeout
        self.poll = poll
        self.round = 0
        os.makedirs(boundary_dir, exist_ok=True)

    def next_action(self, context):
        self.round += 1
        safe = {k: v for k, v in context.items() if k != "client_builder"}
        ctx_path = os.path.join(self.dir, f"context_{self.round}.json")
        act_path = os.path.join(self.dir, f"action_{self.round}.json")
        with open(ctx_path, "w", encoding="utf-8") as f:
            json.dump(safe, f, indent=2, default=str)
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if os.path.exists(act_path):
                with open(act_path, encoding="utf-8") as f:
                    obj = json.load(f)
                return Action(
                    type=obj.get("type", "stop"),
                    command=obj.get("command", "") or "",
                    path=obj.get("path", "") or "",
                    content=obj.get("content", "") or "",
                    name=obj.get("name", "") or "",
                    value=obj.get("value", "") or "",
                    env=obj.get("env", {}) or {},
                    note=obj.get("note", "") or "",
                )
            time.sleep(self.poll)
        raise PlannerError(f"external planner timed out on round {self.round}")
