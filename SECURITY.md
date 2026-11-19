# Security policy

Stranger Suite's job is running other projects' instructions in a
sandbox, so vulnerabilities in the sandbox itself matter: a fixture
README or project that can escape the sandbox, reach the network when
it should not, or leak the canary secret into output defeats the
tool's purpose.

## Reporting a vulnerability

Please report security issues **privately**, not as a public issue:

- Use GitHub's private vulnerability reporting for this repository:
  **Security → Report a vulnerability** on
  https://github.com/RakTikoo/stranger-suite
  (GitHub Security Advisories). This keeps the report visible only to
  the reporter and the maintainer until a fix is available.

If private vulnerability reporting is not available to you, open a
minimal public issue saying you have a security report and asking for
a private contact route — do not post the details in the issue.

Please include, as far as you can:

- the Stranger Suite version and your Python version,
- a minimal fixture project (or a description of its structure) that
  triggers the issue,
- what you expected to happen and what actually happened (sandbox
  escape, network access, canary leak, crash, …).

Do **not** include real credentials or anyone else's private data in a
report. The project's own fixtures use a fake canary secret — that is
all a report needs too.

## Supported versions

Stranger Suite is pre-1.0. Only the **latest release on the `main`
branch** is supported with security fixes; older checkouts should be
updated rather than patched.
