"""Stranger Suite: Fresh-Eyes Install Agent + Stranger API Agent.

Two tools, one shared engine. The engine's HANDS are deterministic
(sandbox, trace, redaction, objective checkers). The BRAIN is a replaceable
Planner (scripted / heuristic / LLM-by-API-key).

Library use: the engine's public API and both tools' entry points are
re-exported here, so `from stranger_suite import SandboxRunner,
HeuristicPlanner, run_fresh_eyes` works without reaching into
subpackages. See the README's "Use as a library" section.
"""

from .engine import (
    DENY_RULES,
    Action,
    ExternalPlanner,
    HeuristicPlanner,
    LLMPlanner,
    LoopingPlanner,
    Planner,
    PlannerError,
    Redactor,
    RunResult,
    SandboxRunner,
    ScriptedPlanner,
    TraceRecorder,
    build_report,
    check_exit_and_marker,
    check_http_state,
    write_report,
)
from .fresh_eyes import ReadmeCommand, parse_readme_commands, run_fresh_eyes
from .stranger_api import build_client_source, parse_docs, run_stranger_api

__version__ = "0.1.1"

__all__ = [
    "__version__",
    # Engine (the hands + the planner interface)
    "SandboxRunner",
    "RunResult",
    "DENY_RULES",
    "TraceRecorder",
    "Redactor",
    "Action",
    "Planner",
    "ScriptedPlanner",
    "HeuristicPlanner",
    "LLMPlanner",
    "PlannerError",
    "ExternalPlanner",
    "LoopingPlanner",
    "build_report",
    "write_report",
    "check_exit_and_marker",
    "check_http_state",
    # Fresh-Eyes as a function
    "run_fresh_eyes",
    "parse_readme_commands",
    "ReadmeCommand",
    # Stranger API as a function
    "run_stranger_api",
    "parse_docs",
    "build_client_source",
]
