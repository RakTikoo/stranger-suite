"""CLI: python -m stranger_suite.stranger_api --docs <file> --base-url <url> --out <dir>"""

from __future__ import annotations

import argparse
import json
import sys

from ..engine.planners import HeuristicPlanner, LLMPlanner, PlannerError
from .core import run_stranger_api


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="stranger_api",
        description="Give an agent ONLY your API docs and one job. "
                    "If it can't do the job, your docs are the problem.")
    p.add_argument("--docs", required=True, help="docs Markdown file or folder")
    p.add_argument("--base-url", required=True,
                   help="base URL of a LOCAL / sandbox API (never a live production API)")
    p.add_argument("--out", required=True, help="output folder for the report")
    p.add_argument("--planner", default="heuristic",
                   choices=["heuristic", "llm"])
    p.add_argument("--preset", default=None,
                   help="LLM free-tier preset name (see README)")
    p.add_argument("--model", default=None,
                   help="override the preset's model (providers rotate model names; the preset may lag)")
    args = p.parse_args(argv)
    from urllib.parse import urlparse
    host = urlparse(args.base_url).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("error: this spike only runs against local/sandbox APIs "
              "(base URL hostname must be exactly localhost/127.0.0.1)",
              file=sys.stderr)
        return 2
    if args.planner == "llm":
        try:
            planner = LLMPlanner(preset=args.preset, model=args.model)
        except PlannerError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    else:
        planner = HeuristicPlanner()
    try:
        rep = run_stranger_api(args.docs, args.base_url, args.out, planner)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": rep["verdict"],
                      "stuck_points": len(rep["stuck_points"]),
                      "report": args.out + "/report.md"}, indent=2))
    return 0 if rep["verdict"] == "JOB COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
