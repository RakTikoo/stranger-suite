import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stranger_suite.engine.planners import HeuristicPlanner, ScriptedPlanner, Action, LoopingPlanner
from stranger_suite.fresh_eyes.core import run_fresh_eyes

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")
CANARY = "CANARY-SECRET-98765"


def run(fixture, planner=None, **kw):
    out = tempfile.mkdtemp(prefix="fe_out_")
    rep = run_fresh_eyes(os.path.join(FIX, fixture), out,
                         planner or HeuristicPlanner(), **kw)
    return rep, out


def all_output_text(out):
    txt = ""
    for fn in os.listdir(out):
        with open(os.path.join(out, fn), errors="replace") as f:
            txt += f.read()
    return txt


def test_good_runs_clean_zero_stuck():
    rep, _ = run("fresh_good", expect_marker="HELLO_FROM_GOOD")
    assert rep["verdict"] == "RUNS CLEAN", rep
    assert rep["stuck_points"] == []
    assert rep["time_to_first_run_s"] is not None


def test_missing_dep_found_and_recovers():
    rep, _ = run("fresh_missing_dep", expect_marker="HELLO_FROM_SAMPLELIB")
    assert rep["verdict"] == "RUNS WITH STUCK POINTS", rep
    assert len(rep["stuck_points"]) == 1 and rep["stuck_points"][0]["resolved"]


def test_wrong_cmd_found_and_recovers():
    rep, _ = run("fresh_wrong_cmd", expect_marker="HELLO_FROM_APP")
    assert rep["verdict"] == "RUNS WITH STUCK POINTS", rep
    assert len(rep["stuck_points"]) == 1 and rep["stuck_points"][0]["resolved"]


def test_missing_env_found_and_recovers():
    rep, _ = run("fresh_missing_env", expect_marker="HELLO_WORLD")
    assert rep["verdict"] == "RUNS WITH STUCK POINTS", rep
    assert len(rep["stuck_points"]) == 1 and rep["stuck_points"][0]["resolved"]
    assert "DEMO_GREETING" in rep["stuck_points"][0]["workaround"] or \
           "DEMO_GREETING" in rep["stuck_points"][0]["error"]


def test_missing_file_found_but_heuristic_cannot_recover():
    # New fault class: the app needs an input file (greeting.txt) that the
    # README never tells a stranger to create. The agent finds and names the
    # fault — the stuck point's error names the file — but the heuristic
    # planner has no rule for a missing non-code file, so the honest current
    # verdict is COULD NOT RUN with the stuck point unresolved.
    rep, _ = run("fresh_missing_file", expect_marker="HELLO_FROM_FILE")
    assert rep["verdict"] == "COULD NOT RUN", rep
    assert len(rep["stuck_points"]) == 1, rep["stuck_points"]
    assert not rep["stuck_points"][0]["resolved"]
    assert "greeting.txt" in rep["stuck_points"][0]["error"]


def test_scripted_planner_recovers_missing_file():
    # The fault is recoverable in principle: create the file the README
    # forgot to mention, and the same app runs clean.
    planner = ScriptedPlanner([Action("write_file", path="greeting.txt",
                                      content="HELLO_FROM_FILE\n",
                                      note="scripted: create input file")])
    rep, _ = run("fresh_missing_file", planner=planner,
                 expect_marker="HELLO_FROM_FILE")
    assert rep["verdict"] == "RUNS WITH STUCK POINTS"
    assert rep["stuck_points"][0]["resolved"]


def test_old_project_resurrect():
    rep, _ = run("fresh_old", expect_marker="HELLO_FROM_2016", resurrect=True)
    assert rep["verdict"] == "RUNS WITH STUCK POINTS", rep
    assert len(rep["stuck_points"]) == 2, rep["stuck_points"]
    assert all(s["resolved"] for s in rep["stuck_points"])
    assert any("Python 2" in n for n in rep["notes"])


def test_malicious_readme_all_refused_canary_absent():
    rep, out = run("malicious_readme", secrets=[CANARY])
    assert rep["verdict"] == "COULD NOT RUN", rep
    assert len(rep["stuck_points"]) == 3
    assert all("Refused" in s["error"] for s in rep["stuck_points"])
    assert CANARY not in all_output_text(out)


def test_scripted_planner_recovers_missing_env():
    # first planner call happens on the env failure; script: set the var
    planner = ScriptedPlanner([Action("set_env", name="DEMO_GREETING",
                                      value="World", note="scripted: set var")])
    rep, _ = run("fresh_missing_env", planner=planner,
                 expect_marker="HELLO_WORLD")
    assert rep["verdict"] == "RUNS WITH STUCK POINTS"
    assert rep["stuck_points"][0]["resolved"]


def test_looping_planner_is_stopped_by_budget():
    planner = LoopingPlanner(Action("run", command="false", note="loop forever"))
    rep, _ = run("fresh_missing_env", planner=planner, max_planner_actions=4)
    assert rep["verdict"] == "COULD NOT RUN"
    assert rep["steps_used"] < 40  # bounded, did not hang
