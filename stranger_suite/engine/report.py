"""Report generation: one dict -> Markdown + JSON. All text redacted."""

from __future__ import annotations

import json
import os


def build_report(redactor, **fields):
    rep = {}
    for k, v in fields.items():
        if isinstance(v, str):
            v = redactor.redact(v)
        rep[k] = v
    return rep


def _redact_obj(redactor, obj):
    if isinstance(obj, str):
        return redactor.redact(obj)
    if isinstance(obj, dict):
        return {k: _redact_obj(redactor, v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_obj(redactor, v) for v in obj]
    return obj


def render_markdown(rep):
    lines = [f"# {rep.get('title', 'Report')}", ""]
    lines.append(f"**Verdict: {rep.get('verdict', '?')}**")
    lines.append("")
    if rep.get("summary"):
        lines.append(rep["summary"])
        lines.append("")
    if rep.get("time_to_first_run_s") is not None:
        lines.append(f"- Time to first successful run: {rep['time_to_first_run_s']}s")
    if rep.get("steps_used") is not None:
        lines.append(f"- Sandbox steps used: {rep['steps_used']}")
    stuck = rep.get("stuck_points") or []
    lines.append(f"- Stuck points: {len(stuck)}")
    lines.append("")
    if stuck:
        lines.append("## Where it got stuck")
        lines.append("")
        for i, s in enumerate(stuck, 1):
            lines.append(f"### {i}. {s.get('step', 'step')}")
            if s.get("error"):
                lines.append(f"- What went wrong: {s['error']}")
            if s.get("workaround"):
                lines.append(f"- What the agent tried: {s['workaround']}")
            lines.append(f"- Fixed: {'yes' if s.get('resolved') else 'no'}")
            lines.append("")
    notes = rep.get("notes") or []
    if notes:
        lines.append("## Notes")
        lines.append("")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines)


def write_report(out_dir, rep, redactor, extra_files=None):
    os.makedirs(out_dir, exist_ok=True)
    rep = _redact_obj(redactor, rep)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, default=str)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(redactor.redact(render_markdown(rep)))
    for name, content in (extra_files or {}).items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(redactor.redact(content))
    return rep
