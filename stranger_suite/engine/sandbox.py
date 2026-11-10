"""Sandbox runner (HANDS).

Runs shell commands inside ONE temp work directory with:
- a scrubbed environment (no inherited secrets; pip forced offline)
- a hard command denylist, checked before anything executes — the planner
  (scripted, heuristic, or a live LLM) can never override a refusal
- per-command timeout, global step budget and global time budget
- every byte of output passed through the Redactor
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field

# (pattern, human reason). Checked against the whole command string.
DENY_RULES = [
    (r"curl[^\n|]*\|\s*(bash|sh)\b", "pipe a downloaded script into a shell (curl|bash)"),
    (r"wget[^\n|]*\|\s*(bash|sh)\b", "pipe a downloaded script into a shell (wget|bash)"),
    (r"\bcurl\b", "network download tool (curl) is not allowed in the sandbox"),
    (r"\bwget\b", "network download tool (wget) is not allowed in the sandbox"),
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "recursive/forced delete (rm -rf)"),
    (r"\brm\s+-[rf]", "delete with rm -r/-f"),
    (r"\bsudo\b", "privilege escalation (sudo)"),
    (r"\bssh\b|\bscp\b|\bsftp\b", "remote shell/copy tool"),
    (r"\bnc\b|\bnetcat\b|\btelnet\b", "raw network tool"),
    (r"\bmkfs\b|\bdd\b[^\n]*of=/dev/", "disk-destroying command"),
    (r"chmod\s+777\s+/", "chmod on system paths"),
    (r">\s*/(etc|usr|bin|sbin|boot)/", "write to a system directory"),
    (r"/etc/(passwd|shadow)", "system credential file"),
    (r"\.ssh\b", "ssh key directory"),
    (r"STRANGER_LLM_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY", "references a secret env var name"),
    (r"\bprintenv\b|\benv\s*(;|$|\|)", "dump the process environment"),
    (r"\bos\.environ\b|\bos\.getenv\b", "read the process environment from code"),
    (r":\(\)\s*\{", "fork bomb"),
    (r"\bshutdown\b|\breboot\b|\bpoweroff\b", "power control"),
    (r"kill\s+-9\s+1\b", "kill init"),
    (r"/proc/", "proc filesystem (process environments live there)"),
    (r"\brm\b", "file deletion (rm) is not needed by any legitimate step"),
    (r"find\b[^\n]*-delete", "find -delete"),
    (r"\bunlink\b|\bshred\b", "file deletion tool"),
    (r"\bnohup\b|\bsetsid\b", "detached/background process"),
    (r"export\s+-p|declare\s+-x|/usr/bin/env\b", "dump the process environment"),
    (r"\bln\s+-s\b[^\n]*/", "symlink to an absolute path"),
    (r"\bos\.fork\b|\bfork\s*\(", "process forking"),
]


@dataclass
class RunResult:
    command: str
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    refused: bool = False
    refusal_reason: str = ""
    timed_out: bool = False
    duration_s: float = 0.0

    @property
    def ok(self):
        return (not self.refused) and self.exit_code == 0


@dataclass
class SandboxRunner:
    workdir: str
    redactor: object
    trace: object = None
    max_steps: int = 40
    max_seconds: float = 300.0
    per_command_timeout: float = 20.0
    extra_env: dict = field(default_factory=dict)
    steps_used: int = 0
    _started: float = field(default_factory=time.monotonic)

    def check_command(self, command):
        """Return a refusal reason, or None if the command may run."""
        for pat, reason in DENY_RULES:
            if re.search(pat, command):
                return reason
        # Writes/reads must stay inside the sandbox: block absolute paths
        # outside a small allowlist of system binary dirs in command text,
        # when the path is a file target (crude but effective for the spike).
        if ".." in command:
            return "parent-directory traversal (..)"
        for m in re.finditer(r"(?<![\w.])/(home|root|tmp|var|opt|etc|proc|sys|dev)/[^\s'\"]*", command):
            if not m.group(0).startswith(self.workdir):
                return f"path outside the sandbox: {m.group(0)}"
        for m in re.finditer(r"(?<![\w.])/[A-Za-z0-9_][^\s'\"]*", command):
            tok = m.group(0)
            if tok.startswith(self.workdir):
                continue
            if tok.startswith(("/usr/", "/bin/", "/sbin/")) or tok in ("/dev/null",):
                continue
            return f"absolute path outside the sandbox: {tok}"
        if re.search(r"(^|\s)&\s*$", command.strip()):
            return "background process (&) is not allowed"
        return None

    # Content written into the sandbox by a planner is scanned with the
    # same rules plus code-level dangers. (The project's OWN code is not
    # scanned: running it is the tool's job, in a throwaway copy.)
    def check_content(self, content):
        for pat, reason in DENY_RULES:
            if re.search(pat, content):
                return reason
        for pat, reason in [
            (r"/proc/", "proc filesystem"),
            (r"shutil\.rmtree", "recursive delete from code"),
            (r"os\.system", "shell from code"),
            (r"os\.fork", "process forking from code"),
            (r"__import__", "dynamic import"),
            (r"\beval\s*\(|\bexec\s*\(", "eval/exec"),
            (r"socket\.", "raw sockets from code"),
        ]:
            if re.search(pat, content):
                return reason
        return None

    def run(self, command, env_delta=None):
        started = time.monotonic()
        if self.steps_used >= self.max_steps:
            res = RunResult(command, None, refused=True,
                            refusal_reason="step budget exhausted")
            self._log(command, res)
            return res
        if started - self._started > self.max_seconds:
            res = RunResult(command, None, refused=True,
                            refusal_reason="time budget exhausted")
            self._log(command, res)
            return res
        reason = self.check_command(command)
        if reason:
            res = RunResult(command, None, refused=True, refusal_reason=reason)
            self.steps_used += 1
            self._log(command, res)
            return res

        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.workdir,
            "LANG": "C.UTF-8",
            "PIP_NO_INDEX": "1",               # offline: local installs only
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_BREAK_SYSTEM_PACKAGES": "1",  # the sandbox is disposable
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        env.update(self.extra_env)
        if env_delta:
            protected = {"PATH", "HOME", "LD_PRELOAD", "LD_LIBRARY_PATH",
                         "PIP_NO_INDEX", "PIP_BREAK_SYSTEM_PACKAGES"}
            env.update({k: v for k, v in env_delta.items()
                        if k not in protected})
        self.steps_used += 1
        res = self._run_capped(command, env, started)
        self._log(command, res)
        return res

    MAX_OUTPUT_BYTES = 2_000_000   # kill a command that floods output
    READ_BYTES = 200_000           # keep at most this much per stream

    def _run_capped(self, command, env, started):
        import signal
        import tempfile
        out_f = tempfile.TemporaryFile()
        err_f = tempfile.TemporaryFile()
        proc = subprocess.Popen(
            command, shell=True, cwd=self.workdir, env=env,
            stdout=out_f, stderr=err_f, start_new_session=True)
        timed_out = flooded = False
        while True:
            rc = proc.poll()
            if rc is not None:
                break
            if time.monotonic() - started > self.per_command_timeout:
                timed_out = True
                break
            if out_f.tell() + err_f.tell() > self.MAX_OUTPUT_BYTES:
                flooded = True
                break
            time.sleep(0.05)
        if timed_out or flooded:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            proc.wait()

        def read_back(fh):
            fh.seek(0)
            data = fh.read(self.READ_BYTES)
            return data.decode("utf-8", errors="replace")
        stdout = read_back(out_f)
        stderr = read_back(err_f)
        out_f.close(); err_f.close()
        if flooded:
            stderr += "\n[engine: output exceeded the cap; command killed]"
        return RunResult(
            command, None if (timed_out or flooded) else proc.returncode,
            stdout=self.redactor.redact(stdout),
            stderr=self.redactor.redact(stderr),
            timed_out=timed_out,
            duration_s=round(time.monotonic() - started, 3),
        )

    def _log(self, command, res):
        if self.trace is not None:
            self.trace.record(
                "run", command=command, exit=res.exit_code,
                refused=res.refused, refusal_reason=res.refusal_reason,
                timed_out=res.timed_out,
                stdout=(res.stdout or "")[-2000:], stderr=(res.stderr or "")[-2000:],
            )
