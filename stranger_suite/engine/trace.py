"""Trace/diary recorder: append-only JSONL, always redacted."""

from __future__ import annotations

import json
import time


class TraceRecorder:
    def __init__(self, redactor):
        self.redactor = redactor
        self.events = []

    def record(self, kind, **fields):
        ev = {"t": round(time.time(), 3), "kind": kind}
        for k, v in fields.items():
            if isinstance(v, str):
                v = self.redactor.redact(v)
            ev[k] = v
        self.events.append(ev)
        return ev

    def to_jsonl(self):
        lines = []
        for ev in self.events:
            lines.append(self.redactor.redact(json.dumps(ev, default=str)))
        return "\n".join(lines) + ("\n" if lines else "")

    def write(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_jsonl())
