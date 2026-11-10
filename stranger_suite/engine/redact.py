"""Secret redaction: every string that leaves the engine passes through here."""

from __future__ import annotations

import os
import re

# Env var names whose VALUES are treated as secrets wherever they appear.
SECRET_ENV_NAMES = (
    "STRANGER_LLM_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "API_KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
)

_GENERIC_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{8,}"),
]


class Redactor:
    def __init__(self, extra_secrets=None):
        self._secrets = set()
        for name in SECRET_ENV_NAMES:
            val = os.environ.get(name)
            if val and len(val) >= 4:
                self._secrets.add(val)
        for s in extra_secrets or []:
            if s and len(str(s)) >= 4:
                self._secrets.add(str(s))

    def add(self, secret):
        if secret and len(str(secret)) >= 4:
            self._secrets.add(str(secret))

    def _forms(self, secret):
        import base64
        b = secret.encode()
        forms = {secret, secret[::-1], b.hex(),
                 base64.b64encode(b).decode(),
                 base64.urlsafe_b64encode(b).decode(),
                 base64.b64encode(b).decode().rstrip("=")}
        return forms

    def redact(self, text):
        if text is None:
            return ""
        out = str(text)
        forms = set()
        for s in self._secrets:
            forms |= self._forms(s)
        for s in sorted(forms, key=len, reverse=True):
            if len(s) >= 4:
                out = out.replace(s, "[REDACTED]")
        for pat in _GENERIC_PATTERNS:
            out = pat.sub("[REDACTED]", out)
        return out
