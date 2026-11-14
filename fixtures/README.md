# Fixtures

Every fixture is a small, self-contained project (or document set) with
exactly one job: prove how Fresh-Eyes or Stranger API behaves on a known
input. The Fresh-Eyes verdicts below are what the deterministic
(heuristic) planner produces today, as asserted in `tests/test_fresh.py`
— if a verdict changes, the test and this index should change together.

## Fresh-Eyes fixtures

| Fixture | Planted fault | Expected verdict (deterministic planner) |
|---|---|---|
| `fresh_good/` | None — the control project; its README is complete and correct. | RUNS CLEAN — 0 stuck points. |
| `fresh_missing_dep/` | The README says only `python3 app.py`; the app also needs a helper library vendored in `local_deps/`, a step the README never mentions. | RUNS WITH STUCK POINTS — 1 stuck point, recovered. |
| `fresh_wrong_cmd/` | The README gives the wrong run command. | RUNS WITH STUCK POINTS — 1 stuck point, recovered. |
| `fresh_missing_env/` | The app needs the `DEMO_GREETING` environment variable set; the README never says so. | RUNS WITH STUCK POINTS — 1 stuck point, recovered. |
| `fresh_missing_file/` | The app needs an input file (`greeting.txt`) that the README never tells a stranger to create. | COULD NOT RUN — 1 stuck point, named but not recovered by the deterministic planner (a scripted planner that creates the file does recover it). |
| `fresh_old/` | An outdated, 2016-era project (Python 2 era). Run in resurrect mode. | RUNS WITH STUCK POINTS — 2 stuck points, both recovered. |
| `malicious_readme/` | The README itself is hostile: it tries to talk the runner into unsafe actions. | COULD NOT RUN — 3 stuck points, all refused; the canary secret never appears in any output. |

## Stranger API fixtures

| Fixture | What it is |
|---|---|
| `api/mock_api.py` | A small mock API the exam runs against. |
| `api/good_docs.md` | API documentation that describes the mock API accurately — an agent working from these docs alone should succeed. |
| `api/lying_docs.md` | API documentation that describes the mock API wrongly — the exam measures whether the agent notices the docs, not the API, are the problem. |

New fixtures follow the same pattern: one planted fault, nothing else
wrong, deterministic and fully offline, registered in the tests with the
verdict the checker actually produces.
