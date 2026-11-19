# Changelog

All notable changes to Stranger Suite, newest first. Everything so far
is the 0.1.0 line (`__version__` in `stranger_suite/__init__.py`).

## v0.1.1 — 2026-11-19

- **GitHub Marketplace:** the Action's `action.yml` description is
  shortened to fit the Marketplace 125-character limit and
  `branding` (icon/colour) is added, so the Action can be listed
  on the GitHub Marketplace. No behaviour changes.

- **Packaging:** `pyproject.toml` added — `pip install
  git+https://github.com/RakTikoo/stranger-suite` (or `pipx install …`)
  installs the package plus `fresh-eyes` and `stranger-api` console
  commands; the version is read from `stranger_suite.__version__`.
  Still stdlib only, zero dependencies. The README's "there is no
  packaging yet" note is gone, replaced by a real install section;
  CONTRIBUTING.md's matching stale lines (and its test count) were
  corrected to match.
- **GitHub Action:** new `action.yml` — Stranger Suite was the only
  tool in the workshop without one. The composite action runs
  Fresh-Eyes (offline heuristic planner by default; optional LLM
  planner with your own key), writes the report to the job summary,
  uploads it as an artifact, and exposes `verdict` / `stuck-points`
  outputs; `fail-on-stuck-points` turns stuck points into a failing
  check.
- **Library API surfaced:** the engine's public API (`SandboxRunner`,
  planners, `build_report`, checkers, …) and both tools' entry points
  (`run_fresh_eyes`, `run_stranger_api`) are now re-exported from the
  top-level `stranger_suite` package and documented in a new README
  "Use as a library" section, with a worked example. The API itself is
  unchanged.

## v0.1.0 — 2026-11-12

First tagged release, at the merge of PR #3. Includes the Fresh-Eyes
missing-input-file fixture (`fixtures/fresh_missing_file/`) contributed
in that PR; entries below are dated by when they landed on `main`.

## 2026-11-10 — Preset fixes

- `gemini-free`: model `gemini-2.5-flash` → `gemini-3.5-flash-lite`
  (Google deprecated 2.5 Flash; this is its documented replacement).
- `openrouter-free`: model `qwen/qwen3-coder:free` →
  `google/gemma-4-31b-it:free` (the old model was removed from
  OpenRouter's live list). Verified present, not yet live-tested.
- `cerebras-free` renamed to **`cerebras-trial`**: Cerebras no longer
  offers a standing free tier (one-time $5 trial credit, payment method
  required, 30-day expiry). Model `qwen-3-32b` → `qwen-3.8-27b`.
  The old preset name now errors as unknown; no alias is kept.
- README preset table and wording updated to match reality.

## 2026-11-09 — Phase C live-test fixes

- LLM transport: send a named `User-Agent` (Groq/Cloudflare rejected
  the default Python one with HTTP 403).
- `groq-free` preset model updated to `qwen/qwen3.8-27b`
  (`qwen/qwen3-32b` had been removed from Groq's live list).
- Both CLIs gained `--model` to override a preset's model.
- Planner retries HTTP 429/5xx (honouring `Retry-After`) and errors
  now include the HTTP status.
- Stranger API: the planner context now includes the job, the real
  `base_url`, and a docs excerpt; the prompt teaches the engine's
  `build_client` action and forbids guessed URLs/curl. The LLM reply's
  `env` object is now actually applied (it was parsed, then dropped).
- README: live-test results added (Groq free tier, three-brain
  scoreboard), replacing the earlier "live testing not done" wording.

## 2026-11-09 — Initial public release (0.1.0)

- One shared hands-vs-brain engine with two CLIs: **Fresh-Eyes**
  (follows a project's README literally in a sandbox and reports stuck
  points, with a corrected-README draft) and **Stranger API**
  (completes a job from API docs alone).
- Deterministic offline heuristic planner, plus an LLM planner for any
  OpenAI-compatible endpoint with free-tier presets (Groq, Gemini AI
  Studio, OpenRouter `:free`, Cerebras, keyless local Ollama).
- Fixture exam corpus (good / missing-dependency / missing-env /
  wrong-command / old-project / malicious-README, plus good-docs and
  lying-docs API jobs) and a 27-test offline suite.
- Safety model: sandboxed execution, refusal of malicious README
  instructions, secret redaction in reports, verdicts only ever from
  objective engine runs. MIT licence.
