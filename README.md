# Stranger Suite

Two small tools that test the instructions, not the code. Both are powered
by one shared engine: deterministic "hands" (a sandbox that runs things
safely and keeps an honest diary) plus a replaceable "brain" (a planner
that decides what to try next).

## See it work — a real captured run

The fixture project `fixtures/fresh_missing_dep` ships a README that says
only `python3 app.py` — but the app needs a helper library vendored in
`local_deps/`, a step the README never mentions. Here is an actual
Fresh-Eyes run against it (offline heuristic planner, no API key),
captured 2026-11-11:

```
$ python3 -m stranger_suite.fresh_eyes fixtures/fresh_missing_dep --out report/ --expect HELLO_FROM_SAMPLELIB
{
  "verdict": "RUNS WITH STUCK POINTS",
  "stuck_points": 1,
  "report": "report/report.md"
}
```

From the report it wrote:

> ### 1. README line 8: `python3 app.py`
> - What went wrong: ModuleNotFoundError: No module named 'samplelib'
> - What the agent tried: module 'samplelib' found vendored under local_deps; retry with PYTHONPATH
> - Fixed: yes

That stuck point is the product: it is the exact place a real new user
would likely have given up, found and named automatically.

## Fresh-Eyes — "Does your README actually work?" (lead tool)

You know the feeling: you clone a project, follow its README exactly, and
it breaks at step two — because the author already had something installed
and forgot to write it down. Fresh-Eyes is the new user who never gives up
silently:

Run everything from the repo root (there is no packaging yet — the tools
run as modules):

```
python3 -m stranger_suite.fresh_eyes <project-folder> --out report/ [--expect MARKER] [--resurrect]
```

`--expect MARKER` is strongly recommended: it is the text a successful run
must print, and without it "success" means only "the run command exited 0".
Exit codes: 0 = the project runs (cleanly or with stuck points), 1 = it
could not run / the API job did not complete, 2 = bad input (missing
folder, bad URL, unknown preset) with a one-line error, never a traceback.

It copies the project into a clean sandbox, runs every README command
literally, and each time it gets stuck it asks the planner for the next
sensible step. At the end it checks — objectively, by running the project —
whether it works, and writes a plain-language report:

- **RUNS CLEAN** — a stranger could follow the README exactly. Zero stuck points.
- **RUNS WITH STUCK POINTS** — it runs, but only after workarounds. Each
  stuck point is a place a real new user would likely quit.
- **COULD NOT RUN** — with the reasons, in order.

It also writes a corrected README draft. Add `--resurrect` for old
projects: the report then emphasises rot (Python-2 syntax, dead package
pins, and friends).

## Stranger API — "If an agent can't use your API from the docs alone, it's broken"

Give the agent **only** your API docs, a local/sandbox base URL, and one
job (the demo job: create a customer → charge them → refund them):

```
# first start the demo API (or your own sandbox API) on a local port:
python3 fixtures/api/mock_api.py 8765
python3 -m stranger_suite.stranger_api --docs docs.md --base-url http://127.0.0.1:8765 --out report/
```

`--docs` accepts a single Markdown file, or a folder (all its .md files
are merged — beware: merging a good and a bad doc set tests the union, not
either one).

The agent writes a client strictly from the docs, runs it, reads the API's
own error messages, and retries. The job counts as complete only when the
API's own state proves it happened. The report lists every place the docs
alone were not enough (an undocumented header, a renamed field…) plus a
corrected client example that actually ran. This spike's CLI refuses
non-localhost base URLs on purpose: never practise on a production API.

## The brain: bring your own key — free tiers are fine, no paid key required

Live mode works on **free tiers** (plus one trial route — see the
Cerebras row); you do not need a paid API key. The
planner talks to any OpenAI-compatible endpoint. Presets (limits checked
Nov 2026 — they can change; keys are never stored in this repo, they come
from your own environment variable `STRANGER_LLM_API_KEY`):

| Preset | Endpoint | Example model | Free limits (Nov 2026) |
|---|---|---|---|
| `groq-free` | api.groq.com/openai/v1 | qwen/qwen3.8-27b | ~30 RPM, ~1,000 req/day |
| `gemini-free` | generativelanguage.googleapis.com/v1beta/openai/ | gemini-3.5-flash-lite | AI Studio free tier — **warning:** on the free tier Google may use prompts to improve its products. Fine for public test fixtures; do not send private code. (Model updated Nov 10, 2026: gemini-2.5-flash was deprecated by Google; this is its documented replacement.) |
| `openrouter-free` | openrouter.ai/api/v1 | google/gemma-4-31b-it:free | ~50 req/day on an unfunded account (model verified present in OpenRouter's live list Nov 10, 2026; the :free lineup rotates often — override with `--model`) |
| `cerebras-trial` | api.cerebras.ai/v1 | qwen-3.8-27b | **No standing free tier anymore** — one-time $5 trial credit, payment method required, expires 30 days after activation. (Renamed from `cerebras-free` on Nov 10, 2026: it is a trial, not a free tier.) |
| `ollama-local` | localhost:11434/v1 | qwen3:8b | **Keyless.** Runs on your own machine via Ollama. Zero cost forever, nothing leaves the machine. |

```
export STRANGER_LLM_API_KEY=<your free-tier key>        # not needed for ollama-local
python3 -m stranger_suite.fresh_eyes <project> --out report/ --planner llm --preset groq-free
```

**Honest status of this spike:** the LLM planner has now been run live
against a real provider (Groq free tier, qwen/qwen3.8-27b, Nov 2026).
Headline: Fresh-Eyes passed 4 of 5 fixtures at the 2-of-3 bar (the
resurrect fixture runs and its Python-2 fix lands, but the LLM reports
the dead package pin instead of removing it — the rule-based stand-in
planner resolves that step every time). Stranger API completed the job
3/3 on honest docs and 2/3 on lying docs, finding both planted lies in
every trial. The live exam also caught real bugs the offline tests
could not: Groq rejects this client's default User-Agent (HTTP 403),
the original preset model had been removed from Groq's list, and the
API planner was missing the context it needed — all fixed, with the
offline suite still green. Full results, including the failures, were
recorded at exam time.

**Three-brain scoreboard** (same fixture exams, objective verdicts;
a free-tier Groq key was used for Phase C and is not stored anywhere):
- **Phase A — a strong LLM agent as the planner:** 4/4 exams passed,
  5 planner actions total.
- **Phase B — a small local model (Ollama qwen2.5-coder:1.5b):** 1/4 —
  valid JSON every time, wrong strategies; the engine stayed honest
  throughout. Conclusion: ~8B is the realistic local floor.
- **Phase C — Groq free tier (qwen/qwen3.8-27b, Nov 2026):** 4/4 on
  the Phase A/B exam set at the 2-of-3 bar, 5 planner actions on clean
  passes, no malformed-JSON replies and no false success claims —
  plus the resurrect-fixture partial above, stated exactly as observed.
  As originally shipped it scored 0/6 on the API exam for the context
  reasons described in the status note; the fixes are in this repo.

## How it is tested (including with weak brains)

A tool that tests other people's instructions has to be testable itself,
without spending money per test run:

1. **Deterministic tests, no LLM, no cost** — sandbox refusals (curl|bash,
   `rm -rf`, secret printing…), redaction with a planted canary key that
   must never appear in any trace or report, budgets that stop a planner
   that loops forever, parsers, objective checkers.
2. **Scripted + heuristic planners in CI** — a recorded planner and a
   small rule-based planner play the brain's part, so end-to-end runs are
   reproducible offline against a fixture corpus: a GOOD project that must
   run clean with **zero invented stuck points**, BROKEN projects with
   exactly one planted bug each, an OLD Python-2 project, and a mock API
   whose docs either tell the truth or lie (undocumented header, renamed
   field). Scoring is objective: did the thing actually run, and were the
   planted bugs — and only those — found?
3. **Weak-brain live tests** — the interesting question is whether the
   *loop* is robust when the brain is weak, because free-tier users will
   run weak brains. Two substitutes for a paid key:
   - **An LLM agent as the planner.** The engine has an "external planner"
     mode: it writes the planner context as JSON to a file boundary and
     reads back one action JSON at a time. A real LLM (a separate agent
     process that sees only what a planner would see — no fixture answers)
     drives the engine through the exam that way.
   - **A small local model via Ollama** (~1B-parameter class) pointed at
     the same fixtures through the normal LLM planner.
   Results for both, including failures, are recorded in the review report.
4. **Live LLM tests** — same corpus, real key, cheap/free model, each
   fixture 3×, pass = 2 of 3, hard caps on steps, time and tokens, model
   + temperature pinned, full redacted traces saved. First run: Groq
   free tier, Nov 2026 (see the status note above).

Safety rule that never depends on the brain: documentation and READMEs are
treated as data, never as instructions. Prompt-injection fixtures (a README
and a docs file that order the agent to curl|bash a URL, print its key, or
delete files) are part of the corpus, and the sandbox hands must refuse all
of it no matter what any planner says.

## Layout

```
stranger_suite/engine/      sandbox, trace, redactor, checkers, report, planners
stranger_suite/fresh_eyes/  README parser + install-agent loop + CLI
stranger_suite/stranger_api/ docs parser + API-agent loop + CLI
fixtures/                   the exam corpus (good / broken / old / malicious, mock API + docs)
tests/                      offline suites: python3 tests/run_tests.py  (or pytest)
```

MIT licensed. This is a spike: Python projects and localhost APIs only,
no GUI apps, no network installs (the sandbox forces pip offline; local /
vendored packages only).

## What the sandbox is — and is not

Honest scope, because a security-adjacent tool must not overclaim: the
sandbox is a **throwaway copy** of the project, a scrubbed environment
(no inherited secrets), a command denylist that is also applied to files a
planner writes, secret redaction (including base64/hex encodings of known
secrets), step/time/output budgets, and writes confined to the copy. It is
**defense in depth, not an OS-level jail**: the project's own code runs as
the same user, so a determined hostile *project* (as opposed to a hostile
README or planner) could still misuse the machine it runs on. Do not point
these tools at code you would not run inside a disposable VM. Real
isolation (containers/namespaces) is the top item on the hardening list.


---

**More from this workshop:** [SkillScan](https://github.com/RakTikoo/skillscan) · [KiCad Preflight](https://github.com/RakTikoo/kicad-preflight) · [Expiry Radar](https://github.com/RakTikoo/expiry-radar) · [CI Command Truth](https://github.com/RakTikoo/ci-command-truth) · [PhantomDep PR Gate](https://github.com/RakTikoo/phantomdep-pr-gate) · [Living Contract Diff](https://github.com/RakTikoo/living-contract-diff) · [Handoff Reconciler](https://github.com/RakTikoo/handoff-reconciler)
