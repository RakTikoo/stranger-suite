"""CLI: python -m stranger_suite.fresh_eyes <project> --out <dir>"""

from __future__ import annotations

import argparse
import json
import sys

from ..engine.planners import HeuristicPlanner, LLMPlanner, PlannerError
from .core import run_fresh_eyes


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="fresh_eyes",
        description="Follow a project's README like a brand-new user and "
                    "report every place a stranger gets stuck.")
    p.add_argument("project", help="project folder to test")
    p.add_argument("--out", required=True, help="output folder for the report")
    p.add_argument("--expect", default=None,
                   help="text the final run must print to count as success")
    p.add_argument("--resurrect", action="store_true",
                   help="old project? emphasise age/rot in the report")
    p.add_argument("--planner", default="heuristic",
                   choices=["heuristic", "llm"],
                   help="heuristic = free offline stand-in; llm = your own API key (see README presets)")
    p.add_argument("--preset", default=None,
                   help="LLM free-tier preset name (groq-free, gemini-free, openrouter-free, cerebras-free, ollama-local)")
    args = p.parse_args(argv)
    if args.planner == "llm":
        try:
            planner = LLMPlanner(preset=args.preset)
        except PlannerError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    else:
        planner = HeuristicPlanner()
    try:
        rep = run_fresh_eyes(args.project, args.out, planner,
                             expect_marker=args.expect, resurrect=args.resurrect)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": rep["verdict"],
                      "stuck_points": len(rep["stuck_points"]),
                      "report": args.out + "/report.md"}, indent=2))
    return 0 if rep["verdict"] != "COULD NOT RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
