"""Parse API docs (Markdown) into the only context the agent may use.

Docs-only means: endpoints, headers and field names mentioned in the docs.
If the docs don't mention it, the agent starts out not knowing it — that is
the whole point of the test.
"""

from __future__ import annotations

import re


def parse_docs(docs_text):
    endpoints = []
    for m in re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-/]+)", docs_text):
        ep = (m.group(1), m.group(2))
        if ep not in endpoints:
            endpoints.append(ep)
    headers = sorted(set(re.findall(r"(X-[A-Za-z\-]+)\s*:", docs_text)))
    fields = sorted(set(re.findall(r'"(\w+)":', docs_text)))
    return {
        "endpoints": endpoints,
        "headers_mentioned": headers,
        "fields_mentioned": fields,
        "raw": docs_text,
    }
