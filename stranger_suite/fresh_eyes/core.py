"""Fresh-Eyes core loop.

Copy the project into a sandbox, run each README command literally, and
when one fails, ask the planner for the next action. Success is decided
OBJECTIVELY at the end: the project's run command is executed once more
and must exit 0 (and print the expected marker, if one was given).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time

from ..engine.redact import Redactor
from ..engine.trace import TraceRecorder
from ..engine.sandbox import SandboxRunner
from ..engine.report import write_report
from ..engine.checkers import check_exit_and_marker
from .parser import parse_readme_commands

_IGNORE = {".git", "__pycache__", ".venv", "node_modules"}


def _list_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            out.append(rel)
    return sorted(out)


def _read_small_files(root, files, limit=4000):
    contents = {}
    for f in files:
        if f.endswith((".py", ".txt", ".md", ".toml", ".cfg")):
            try:
                with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
                    contents[f] = fh.read(limit)
            except OSError:
                pass
    return contents


def _rot_notes(root, files, contents):
    notes = []
    for f, c in contents.items():
        if f.endswith(".py") and re.search(r"^\s*print\s+[^(\s]", c, re.M):
            notes.append(f"{f}: Python 2 print syntax (dead since Python 3.0)")
    req = contents.get("requirements.txt", "")
    for ln in req.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            notes.append(f"requirements.txt pin kept as written: {ln} "
                         "(existence checked only when the install step runs)")
    return notes


def run_fresh_eyes(project_dir, out_dir, planner, expect_marker=None,
                   resurrect=False, max_planner_actions=12, secrets=None):
    if not os.path.isdir(project_dir):
        raise ValueError(f"project folder not found or not a folder: {project_dir}")
    started = time.monotonic()
    redactor = Redactor(extra_secrets=secrets)
    trace = TraceRecorder(redactor)
    tmp = tempfile.mkdtemp(prefix="fresh_eyes_")
    workdir = os.path.join(tmp, "project")
    shutil.copytree(project_dir, workdir,
                    ignore=shutil.ignore_patterns(*_IGNORE))
    runner = SandboxRunner(workdir=workdir, redactor=redactor, trace=trace)

    readme_text = ""
    for cand in ("README.md", "readme.md", "Readme.md", "README.MD"):
        rp = os.path.join(workdir, cand)
        if os.path.exists(rp):
            with open(rp, encoding="utf-8", errors="replace") as f:
                readme_text = f.read()
            break
    commands = parse_readme_commands(readme_text)
    files = _list_files(workdir)
    contents = _read_small_files(workdir, files)

    stuck_points = []
    env_state = {}
    time_to_first = None
    py_cmds = [c.command for c in commands if ".py" in c.command]
    run_command = py_cmds[-1] if py_cmds else (commands[-1].command if commands else "")
    planner_actions_used = 0

    def context_for(cmd, result):
        return {
            "mode": "fresh",
            "current_command": cmd,
            "last_stdout": result.stdout if result else "",
            "last_stderr": (result.stderr if result else "") +
                            (("REFUSED: " + result.refusal_reason) if result and result.refused else ""),
            "last_exit": result.exit_code if result else None,
            "files": _list_files(workdir),
            "file_contents": _read_small_files(workdir, _list_files(workdir)),
            "env_state": dict(env_state),
        }

    def apply_action(action, cmd, result):
        """Execute one planner action through the HANDS. Returns a RunResult
        if the action ran something, else None."""
        trace.record("planner_action", type=action.type, note=action.note,
                     command=action.command, path=action.path, name=action.name)
        if action.type == "run":
            env = dict(env_state)
            env.update(action.env or {})
            return runner.run(action.command, env_delta=env)
        if action.type == "retry":
            return runner.run(cmd, env_delta=dict(env_state))
        if action.type == "set_env":
            env_state[action.name] = action.value
            return runner.run(cmd, env_delta=dict(env_state))
        if action.type == "write_file":
            # writes are confined to the sandbox workdir (realpath defeats
            # symlink tricks) and their content is scanned like a command
            target = os.path.realpath(os.path.join(workdir, action.path))
            if not target.startswith(os.path.realpath(workdir) + os.sep):
                trace.record("write_refused", path=action.path,
                             reason="path escapes sandbox")
                return None
            deny = runner.check_content(action.content)
            if deny:
                trace.record("write_refused", path=action.path,
                             reason=f"content refused: {deny}")
                return None
            with open(target, "w", encoding="utf-8") as f:
                f.write(action.content)
            return runner.run(cmd, env_delta=dict(env_state))
        return None

    def is_substantive(action, original_cmd):
        """A planner action only 'resolves' a stuck point if it plausibly
        runs the project itself — an unrelated successful command (an echo,
        a version print) must never certify anything."""
        if action.type in ("retry", "set_env", "write_file"):
            return True
        if action.type == "run":
            if action.command == original_cmd:
                return True
            files_now = _list_files(workdir)
            return any(tok.endswith(".py") and tok in files_now
                       or (tok.endswith(".py") and os.path.basename(tok) in
                           [os.path.basename(f) for f in files_now])
                       for tok in action.command.replace("'", " ").replace('"', " ").split())
        return False

    last_result = None
    for rc in commands:
        # shell-session state: `export X=Y` and `cd dir` are instructions
        # to the session, not programs; honour them across steps
        m_exp = re.match(r"^export\s+([A-Z][A-Z0-9_]*)=(.*)$", rc.command)
        if m_exp:
            env_state[m_exp.group(1)] = m_exp.group(2).strip("'\"")
            continue
        m_cd = re.match(r"^cd\s+(\S+)$", rc.command)
        if m_cd:
            target = os.path.normpath(os.path.join(workdir, m_cd.group(1)))
            if os.path.isdir(target):
                runner.workdir = target
                continue
        result = runner.run(rc.command, env_delta=dict(env_state))
        last_result = result
        if check_exit_and_marker(result, None):
            continue
        # --- stuck: hand over to the planner ---------------------------
        stuck = {
            "step": f"README line {rc.line}: `{rc.command}`",
            "error": ((result.stderr or result.stdout or result.refusal_reason or "")
                      .strip().splitlines() or ["command failed"])[-1][:300]
                     .replace(workdir, "."),
            "workaround": "",
            "resolved": False,
        }
        if result.refused:
            stuck["error"] = f"Refused by sandbox safety rules: {result.refusal_reason}"
            stuck_points.append(stuck)
            continue
        attempts = 0
        while attempts < max_planner_actions and planner_actions_used < max_planner_actions * len(commands):
            try:
                action = planner.next_action(context_for(rc.command, result))
            except Exception as e:
                stuck["workaround"] = f"the planner itself failed ({type(e).__name__}); no fix attempted"
                trace.record("planner_error", error=type(e).__name__)
                break
            planner_actions_used += 1
            attempts += 1
            trace.record("planner", planner=getattr(planner, "name", "?"),
                         type=action.type, note=action.note)
            if action.type == "stop":
                stuck["workaround"] = action.note or "planner stopped"
                break
            new_result = apply_action(action, rc.command, result)
            if action.note:
                stuck["workaround"] = action.note
            if new_result is not None:
                result = new_result
                last_result = new_result
                if check_exit_and_marker(new_result, None) and is_substantive(action, rc.command):
                    stuck["resolved"] = True
                    if action.type == "run" and action.command and ".py" in action.command:
                        run_command = action.command
                        env_state.update(action.env or {})
                    if action.type == "run" and action.command != rc.command:
                        stuck["fix"] = f"Change this command to `{action.command}`"
                    elif action.type == "set_env":
                        stuck["fix"] = f"Add `export {action.name}={action.value}` before this step"
                    elif action.type == "write_file":
                        stuck["fix"] = f"Edit {action.path} — the agent's corrected version ran successfully"
                    break
        stuck_points.append(stuck)

    # --- objective final verification ----------------------------------
    verified = False
    verify_passes = 0
    notes_pre = []
    if run_command and not (last_result and last_result.refused and run_command == last_result.command):
        for _ in range(3):
            vr = runner.run(run_command, env_delta=dict(env_state))
            ok = (not vr.refused and vr.exit_code == 0 and
                  (expect_marker is None or
                   expect_marker in ((vr.stdout or "") + (vr.stderr or ""))))
            if ok:
                verify_passes += 1
        verified = verify_passes >= 1
        if verified:
            time_to_first = round(time.monotonic() - started, 2)
        if 0 < verify_passes < 3:
            notes_pre.append(f"Flaky: the verification run succeeded {verify_passes} of 3 times — "
                             "this project does not run reliably.")
    if expect_marker and verified and not py_cmds:
        verified = False
        notes_pre.append("The README never runs a project file, so the expected "
                         "marker cannot be credited to the project itself.")

    if verified and not stuck_points:
        verdict = "RUNS CLEAN"
        summary = ("A complete stranger could install and run this project "
                   "by following the README exactly. No stuck points.")
    elif verified:
        verdict = "RUNS WITH STUCK POINTS"
        summary = ("The project does run, but its README contains steps that "
                   "fail as written. Each stuck point below is a place a real "
                   "new user would likely give up.")
    else:
        verdict = "COULD NOT RUN"
        summary = ("The agent could not get this project running by "
                   "following its README. The stuck points below are the "
                   "reasons, in the order they happened.")

    notes = list(notes_pre)
    if not commands:
        notes.append("The README contains no runnable command block at all — "
                     "there was nothing for a stranger to follow.")
    if resurrect:
        notes.extend(_rot_notes(workdir, files, contents))
        notes.append("Resurrect mode: emphasis is on age/rot — what in this "
                     "old project no longer matches the modern world.")
    if expect_marker and not verified:
        notes.append(f"Expected success marker {expect_marker!r} was not seen "
                     "in a clean final run, so success is NOT claimed.")

    corrected = _corrected_readme(readme_text, stuck_points, verdict)

    rep = {
        "title": "Fresh-Eyes Install Report",
        "tool": "fresh_eyes",
        "verdict": verdict,
        "summary": summary,
        "project": os.path.basename(os.path.abspath(project_dir)),
        "planner": getattr(planner, "name", "?"),
        "stuck_points": stuck_points,
        "notes": notes,
        "time_to_first_run_s": time_to_first,
        "steps_used": runner.steps_used,
        "verified_run_command": run_command,
        "verified": verified,
    }
    extra = {"corrected_README.md": corrected}
    rep = write_report(out_dir, rep, redactor, extra_files=extra)
    trace.write(os.path.join(out_dir, "trace.jsonl"))
    shutil.rmtree(tmp, ignore_errors=True)
    return rep


def _corrected_readme(original, stuck_points, verdict):
    lines = [original.rstrip("\n"), "", "---", "",
             "<!-- Added by Fresh-Eyes: what a stranger actually hit -->",
             f"## Fresh-Eyes corrections (verdict: {verdict})", ""]
    if not stuck_points:
        lines.append("No corrections needed — the README worked exactly as written.")
    for i, s in enumerate(stuck_points, 1):
        lines.append(f"{i}. At {s['step']}: {s['error']}")
        if s.get("workaround"):
            lines.append(f"   Workaround that worked: {s['workaround']}"
                         if s["resolved"] else
                         f"   Tried: {s['workaround']} (did not fix it)")
        if s.get("fix"):
            lines.append(f"   README should change: {s['fix']}")
    lines.append("")
    return "\n".join(lines)
