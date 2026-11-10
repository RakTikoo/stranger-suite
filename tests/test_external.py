import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stranger_suite.engine.external import ExternalPlanner


def test_external_planner_file_boundary_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p = ExternalPlanner(d, timeout=10)

        def driver():
            # wait for context_1.json, then answer it
            import time
            for _ in range(100):
                cpath = os.path.join(d, "context_1.json")
                if os.path.exists(cpath):
                    ctx = json.load(open(cpath))
                    assert ctx["last_stderr"] == "boom"
                    with open(os.path.join(d, "action_1.json"), "w") as f:
                        json.dump({"type": "stop", "note": "driver says stop"}, f)
                    return
                time.sleep(0.1)
            raise AssertionError("context file never appeared")

        t = threading.Thread(target=driver)
        t.start()
        act = p.next_action({"mode": "fresh", "last_stderr": "boom",
                             "client_builder": lambda **k: "x"})
        t.join()
        assert act.type == "stop" and act.note == "driver says stop"
