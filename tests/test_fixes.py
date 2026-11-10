"""Regression tests for the adversarial review findings (Nov 2026)."""
import os, sys, tempfile, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures", "api"))
from mock_api import make_server
from stranger_suite.engine.redact import Redactor
from stranger_suite.engine.trace import TraceRecorder
from stranger_suite.engine.sandbox import SandboxRunner
from stranger_suite.engine.planners import HeuristicPlanner, ScriptedPlanner, Action
from stranger_suite.fresh_eyes.core import run_fresh_eyes
from stranger_suite.stranger_api.core import run_stranger_api

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")
CANARY = "CANARY-SECRET-98765"

def _mkproj(files):
    d = tempfile.mkdtemp()
    proj = os.path.join(d, "proj"); os.makedirs(proj)
    for name, content in files.items():
        path = os.path.join(proj, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(content)
    return proj

def test_echo_substitution_cannot_certify_broken_app():
    proj = _mkproj({
        "README.md": "# X\n\n```bash\npython3 app.py\n```\n",
        "app.py": "import sys; sys.exit(3)\n"})
    planner = ScriptedPlanner([Action("run", command="echo HELLO_FROM_GOOD", note="cheat")])
    rep = run_fresh_eyes(proj, tempfile.mkdtemp(), planner, expect_marker="HELLO_FROM_GOOD")
    assert rep["verdict"] == "COULD NOT RUN", rep
    assert not rep["stuck_points"][0]["resolved"]

def test_export_readme_no_invented_stuck():
    proj = _mkproj({
        "README.md": "# X\n\n```bash\nexport DEMO_GREETING=World\npython3 app.py\n```\n",
        "app.py": "import os,sys\nn=os.environ.get('DEMO_GREETING')\nassert n, 'Missing env var: DEMO_GREETING'\nprint('HELLO_'+n.upper())\n"})
    rep = run_fresh_eyes(proj, tempfile.mkdtemp(), HeuristicPlanner(), expect_marker="HELLO_WORLD")
    assert rep["verdict"] == "RUNS CLEAN", rep
    assert rep["stuck_points"] == []

def test_planner_error_does_not_crash_fresh():
    from stranger_suite.engine.planners import Planner, PlannerError
    class Bad(Planner):
        name = "bad"
        def next_action(self, ctx): raise PlannerError("boom")
    rep = run_fresh_eyes(os.path.join(FIX, "fresh_missing_env"), tempfile.mkdtemp(), Bad())
    assert rep["verdict"] == "COULD NOT RUN"
    assert "planner itself failed" in rep["stuck_points"][0]["workaround"]

def _with_server(fn):
    srv = make_server(0); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try: return fn(base)
    finally: srv.shutdown()

def test_leftover_state_cannot_certify_print_only_client():
    def go(base):
        out = tempfile.mkdtemp()
        good = run_stranger_api(os.path.join(FIX, "api", "good_docs.md"), base, out, HeuristicPlanner())
        assert good["verdict"] == "JOB COMPLETE"
        # second run on the SAME server: a client that only prints the marker
        planner = ScriptedPlanner([Action("write_file", path="client.py",
            content='print("JOB_COMPLETE")\n', note="fake client")])
        rep = run_stranger_api(os.path.join(FIX, "api", "good_docs.md"), base, tempfile.mkdtemp(), planner)
        assert rep["verdict"] == "JOB NOT COMPLETED", rep
    _with_server(go)

def test_docs_with_wrong_paths_are_detected():
    def go(base):
        docs = os.path.join(tempfile.mkdtemp(), "docs.md")
        open(docs, "w").write("# API\n\nPOST /payments\n\nPOST /v2/refund\n\nPOST /customers\n")
        rep = run_stranger_api(docs, base, tempfile.mkdtemp(), HeuristicPlanner())
        assert rep["verdict"] == "JOB NOT COMPLETED", rep
        assert rep["stuck_points"], rep
    _with_server(go)

def test_sandbox_hardening_batch():
    with tempfile.TemporaryDirectory() as d:
        red = Redactor(extra_secrets=[CANARY]); tr = TraceRecorder(red)
        r = SandboxRunner(workdir=d, redactor=red, trace=tr)
        for cmd in ["cat /proc/self/environ", "cat ../../etc/hostname",
                    "echo x > /etc/cron.d/x", "nohup sleep 5", "sleep 5 &",
                    "rm plainfile", "find . -delete", "ln -s /etc/passwd link"]:
            assert r.run(cmd).refused, cmd
        # env override cannot defeat offline pip (checked via a project
        # script file: project code is data the tool runs, unlike commands)
        with open(os.path.join(d, "showenv.py"), "w") as f:
            f.write("import os; print(os.environ.get('PIP_NO_INDEX'))\n")
        res = r.run("python3 showenv.py", env_delta={"PIP_NO_INDEX": "0"})
        assert res.stdout.strip() == "1", res
        # base64 of the canary is redacted too
        import base64
        b64 = base64.b64encode(CANARY.encode()).decode()
        with open(os.path.join(d, "n.txt"), "w") as f: f.write(CANARY)
        res = r.run("base64 n.txt")
        assert CANARY not in res.stdout and b64 not in res.stdout
        # huge output is capped, not OOM
        res = r.run("python3 -c \"print('A'*5000000)\"")
        assert len(res.stdout) <= 210000

def test_write_file_content_scan_and_symlink():
    proj = _mkproj({
        "README.md": "# X\n\n```bash\npython3 app.py\n```\n",
        "app.py": "import sys; sys.exit(2)\n"})
    planner = ScriptedPlanner([
        Action("write_file", path="evil.py", content="import os\nos.system('id')\n", note="evil write"),
        Action("stop", note="done")])
    out = tempfile.mkdtemp()
    rep = run_fresh_eyes(proj, out, planner)
    assert rep["verdict"] == "COULD NOT RUN"
    trace = open(os.path.join(out, "trace.jsonl")).read()
    assert "write_refused" in trace
