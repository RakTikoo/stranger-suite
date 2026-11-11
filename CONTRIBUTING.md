# Contributing to Stranger Suite

Thanks for your interest. This is a small, deliberately simple project:
pure Python standard library, no packaging yet, no dependencies to
install. Contributions that keep it that way are very welcome.

## Running the project

Everything runs from the repo root, as modules:

```
python3 -m stranger_suite.fresh_eyes <project-folder> --out report/ [--expect MARKER]
python3 -m stranger_suite.stranger_api --docs <docs-file> --base-url <local-api-url> --out report/
```

## Running the tests

```
python3 tests/run_tests.py
```

All tests must pass (currently 27). The suite is fully offline and
deterministic — no network, no API keys. If your change fixes a bug or
adds behaviour, add a test that would have caught it; several existing
tests encode attacks found in adversarial review, and that pattern is
the house style.

## Ground rules

- **Standard library only.** No new dependencies, no packaging changes
  without a discussion first.
- **No secrets, ever.** API keys come only from the user's own
  `STRANGER_LLM_API_KEY` environment variable. Never commit a key, a
  log containing one, or test data built from private code.
- **Honesty is the product.** Verdicts come only from objective engine
  runs (exit codes, expected markers, final clean verification runs).
  Never make a report claim something the engine did not observe —
  a false "it runs" is the worst bug this project can ship.
- **The sandbox is safety-critical.** Fresh-Eyes executes instructions
  from untrusted READMEs. Changes to command allow/deny rules, file
  writing, environment handling, or output redaction need a test that
  demonstrates the attack they defend against, and extra care in
  review. Malicious-input fixtures must stay refused.
- **Keep the CLI contract.** Exit codes: 0 = success, 1 = could not
  run / job incomplete, 2 = bad input with a one-line error (never a
  traceback).

## Adding a Fresh-Eyes fixture

Fixtures are the exam this project is graded by, and new ones are the
most valuable small contribution:

1. Create `fixtures/fresh_<name>/` with a tiny `app.py`, a `README.md`,
   and any supporting files.
2. The README should contain exactly one planted fault of a class the
   existing fixtures do not cover (current classes: missing dependency
   step, missing environment variable, wrong command, old/rotted
   project, malicious instructions) — or a genuinely clean project.
3. Add the matching expectations in `tests/test_fresh.py` (verdict and
   stuck points) and make sure the full suite passes.

## Pull requests

- Keep changes small and single-purpose; say what you verified, not
  just what you changed.
- Update `CHANGELOG.md` (top section) and the README if behaviour or
  presets change. Preset models and free-tier limits rot quickly —
  if you touch a preset, verify the model still exists in the
  provider's own list/docs and say when you checked.
