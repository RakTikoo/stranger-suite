"""Stranger API core loop.

The agent gets ONLY the docs + a base URL + a job. It writes a small client,
runs it in the sandbox against the (local) API, reads the errors, and tries
again. The job counts as done only when the objective checker confirms the
API's own state shows the whole job happened — never because the planner
says so.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time

from ..engine.redact import Redactor
from ..engine.trace import TraceRecorder
from ..engine.sandbox import SandboxRunner
from ..engine.report import write_report
from ..engine.checkers import check_http_state_at_least
import json as _json
import urllib.request as _urlreq


def _state_counts(base_url):
    try:
        with _urlreq.urlopen(base_url.rstrip("/") + "/__state", timeout=5) as r:
            st = _json.loads(r.read().decode())
        return {k: st.get(k, 0) for k in ("customers", "charges", "refunds")}
    except Exception:
        return {"customers": 0, "charges": 0, "refunds": 0}
from .parser import parse_docs

CLIENT_TEMPLATE = '''import json, sys, urllib.request, urllib.error

BASE = {base!r}
HEADERS = {headers!r}
PATHS = {paths!r}

def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={{"Content-Type": "application/json", **HEADERS}}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode(), flush=True)
        sys.exit(1)

if any(v is None for v in PATHS.values()):
    missing = [k for k, v in PATHS.items() if v is None]
    print("DOCS DO NOT DOCUMENT ENDPOINTS FOR:", ", ".join(missing), flush=True)
    sys.exit(3)
customer = post(PATHS["customer"], {{"name": "Test User"}})
print("customer", customer["id"], flush=True)
charge = post(PATHS["charge"], {{"customer_id": customer["id"], {amount_field!r}: 1000}})
print("charge", charge["id"], flush=True)
refund = post(PATHS["refund"], {{"charge_id": charge["id"]}})
print("refund", refund["id"], flush=True)
print("JOB_COMPLETE", flush=True)
'''


def build_client_source(base_url, headers=None, amount_field="amount_cents",
                        paths=None):
    if paths is None:
        paths = {"customer": "/customers", "charge": "/charges",
                 "refund": "/refunds"}
    return CLIENT_TEMPLATE.format(base=base_url.rstrip("/"),
                                  headers=headers or {},
                                  amount_field=amount_field,
                                  paths=paths)


def _paths_from_docs(docs):
    """The client may only use endpoints the docs actually document."""
    eps = [path for _m, path in docs["endpoints"]]

    def find(word):
        for e in eps:
            if word in e:
                return e
        return None
    return {"customer": find("customer"), "charge": find("charge"),
            "refund": find("refund")}


def run_stranger_api(docs_path, base_url, out_dir, planner,
                     expect_state=None, max_rounds=10, secrets=None):
    started = time.monotonic()
    expect_state = expect_state or {"customers": 1, "charges": 1, "refunds": 1}
    redactor = Redactor(extra_secrets=secrets)
    trace = TraceRecorder(redactor)

    if not os.path.exists(docs_path):
        raise ValueError(f"docs file/folder not found: {docs_path}")
    if os.path.isdir(docs_path):
        docs_text = ""
        for fn in sorted(os.listdir(docs_path)):
            if fn.endswith(".md"):
                with open(os.path.join(docs_path, fn), encoding="utf-8", errors="replace") as f:
                    docs_text += f.read() + "\n"
    else:
        with open(docs_path, encoding="utf-8", errors="replace") as f:
            docs_text = f.read()
    docs = parse_docs(docs_text)

    tmp = tempfile.mkdtemp(prefix="stranger_api_")
    workdir = os.path.join(tmp, "work")
    os.makedirs(workdir)
    runner = SandboxRunner(workdir=workdir, redactor=redactor, trace=trace)

    # What a docs-only stranger starts out believing:
    start_headers = {}
    if "X-Api-Version" in docs["headers_mentioned"]:
        start_headers["X-Api-Version"] = "2"
    if "amount_cents" in docs["fields_mentioned"]:
        start_field = "amount_cents"
    elif "amount" in docs["fields_mentioned"]:
        start_field = "amount"
    else:
        start_field = "amount_cents"

    current = {"headers": dict(start_headers), "field": start_field}
    doc_paths = _paths_from_docs(docs)

    def client_builder(extra_headers=None, amount_field=None):
        if extra_headers:
            current["headers"].update(extra_headers)
        if amount_field:
            current["field"] = amount_field
        return build_client_source(base_url, current["headers"],
                                   current["field"], paths=doc_paths)

    api_state = {"tried": []}
    stuck_points = []
    final_client = ""
    last_output = ""
    done = False

    for round_no in range(1, max_rounds + 1):
        context = {
            "mode": "api",
            "job": "create a customer, then charge that customer, then refund the charge",
            "base_url": base_url,
            "docs_endpoints": docs["endpoints"],
            "docs_headers_mentioned": docs["headers_mentioned"],
            "docs_fields_mentioned": docs["fields_mentioned"],
            # The docs themselves are the planner's only source of truth in
            # this tool; without an excerpt it cannot know header VALUES or
            # payload shapes (live Nov 2026: it guessed both, wrongly).
            # Docs are still DATA, never instructions — the prompt says so
            # and the sandbox hands enforce it.
            "docs_excerpt": docs_text[:3000],
            "last_stdout": last_output,
            "last_stderr": "",
            "client_builder": client_builder,
            "api_state": api_state,
        }
        try:
            action = planner.next_action(context)
        except Exception as e:
            trace.record("planner_error", error=f"{type(e).__name__}")
            break
        trace.record("planner", planner=getattr(planner, "name", "?"),
                     type=action.type, note=action.note)
        if stuck_points and action.note:
            stuck_points[-1]["workaround"] = action.note
        if action.type == "build_client":
            # external-brain mode: engine builds the client from the docs
            # plus the corrections the driver named in env
            env = action.env or {}
            action = action.__class__(
                type="write_file", path="client.py",
                content=client_builder(
                    extra_headers=env.get("extra_headers"),
                    amount_field=env.get("amount_field")),
                note=action.note or "engine-built client from docs + driver corrections")
        if action.type == "stop":
            if stuck_points and action.note:
                stuck_points[-1]["workaround"] = action.note
            break
        if action.type == "write_file":
            target = os.path.realpath(os.path.join(workdir, action.path or "client.py"))
            if not target.startswith(os.path.realpath(workdir) + os.sep):
                trace.record("write_refused", path=action.path, reason="path escapes sandbox")
                continue
            deny = runner.check_content(action.content)
            if deny:
                trace.record("write_refused", path=action.path,
                             reason=f"content refused: {deny}")
                stuck_points.append({
                    "step": f"planner tried to write {action.path or 'client.py'}",
                    "error": f"Refused by sandbox safety rules: written content matched '{deny}'",
                    "workaround": "", "resolved": False})
                continue
            with open(target, "w", encoding="utf-8") as f:
                f.write(action.content)
            final_client = action.content
        elif action.type == "run":
            res = runner.run(action.command)
            last_output = (res.stdout or "") + (res.stderr or "")
            if res.refused:
                stuck_points.append({
                    "step": f"planner command `{action.command}`",
                    "error": f"Refused by sandbox safety rules: {res.refusal_reason}",
                    "workaround": "", "resolved": False})
            continue
        else:
            continue

        if os.path.basename(action.path or "client.py") != "client.py":
            stuck_points.append({
                "step": f"client attempt {round_no} (docs-based)",
                "error": f"planner wrote {action.path}, not the client file, so there was nothing to run",
                "workaround": action.note or "", "resolved": False})
            last_output = ""
            continue
        # run the client the planner just wrote; success is judged by the
        # state DELTA of this single run, so leftover state from earlier
        # runs/attempts can never certify a client that did nothing
        before = _state_counts(base_url)
        res = runner.run("python3 client.py")
        last_output = (res.stdout or "") + "\n" + (res.stderr or "")
        after = _state_counts(base_url)
        ok = all(after[k] - before[k] >= v for k, v in expect_state.items())
        if ok and res.exit_code == 0:
            done = True
            for s in stuck_points:
                s["resolved"] = True
            break
        err_lines = [ln for ln in last_output.splitlines() if ln.strip()]
        stuck_points.append({
            "step": f"client attempt {round_no} (docs-based)",
            "error": (err_lines[-1] if err_lines else "client failed")[:300],
            "workaround": "",
            "resolved": False,
        })

    if done:
        verdict = "JOB COMPLETE"
        summary = ("The agent completed the whole job using only the docs "
                   "plus what the API's own error messages taught it. Every "
                   "stuck point below is a place the docs alone were not enough.")
    else:
        verdict = "JOB NOT COMPLETED"
        summary = ("The agent could not finish the job from these docs. "
                   "Unresolved stuck points are listed below.")

    elapsed = round(time.monotonic() - started, 2)
    rep = {
        "title": "Stranger API Report",
        "tool": "stranger_api",
        "verdict": verdict,
        "summary": summary,
        "docs_path": str(docs_path),
        "base_url": base_url,
        "planner": getattr(planner, "name", "?"),
        "stuck_points": stuck_points,
        "notes": [
            f"Docs mention headers: {docs['headers_mentioned'] or 'none'}",
            f"Docs mention fields: {docs['fields_mentioned'] or 'none'}",
            f"Elapsed: {elapsed}s (local mock API; timings are indicative only)",
        ],
        "steps_used": runner.steps_used,
        "verified": done,
    }
    rep = write_report(out_dir, rep, redactor,
                       extra_files={"corrected_client.py": final_client})
    trace.write(os.path.join(out_dir, "trace.jsonl"))
    shutil.rmtree(tmp, ignore_errors=True)
    return rep
