"""Objective success checkers. A job is done only when these say so —
never because a planner believes it is done."""

from __future__ import annotations

import json
import urllib.request


def check_exit_and_marker(result, expect_marker=None):
    if result is None or result.refused or result.exit_code != 0:
        return False
    if expect_marker:
        return expect_marker in (result.stdout or "")
    return True


def check_http_state(base_url, expect):
    """GET base_url/__state and compare selected keys exactly.

    Used against the local mock API fixture. Returns (ok, state_dict).
    """
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/__state", timeout=5) as resp:
            state = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return False, {}
    for k, v in (expect or {}).items():
        if state.get(k) != v:
            return False, state
    return True, state


def check_http_state_at_least(base_url, expect):
    """Like check_http_state, but counts are minimums: a retrying agent may
    legitimately create more than one customer on its way to success."""
    ok, state = check_http_state(base_url, {})
    if not ok and not state:
        return False, state
    for k, v in (expect or {}).items():
        if not isinstance(state.get(k), int) or state.get(k) < v:
            return False, state
    return True, state
