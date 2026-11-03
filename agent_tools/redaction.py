"""Best-effort local redaction; never a substitute for disclosure review."""
from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY = re.compile(
    r"password|passwd|passphrase|secret|token|community|authorization|cookie|"
    r"private.?key|api.?key|credential|session.?id|auth.?key|enc.?key", re.I
)
SENSITIVE_LINE = re.compile(
    r"password|passwd|passphrase|secret|community|authorization\s*:|"
    r"(?:api.?key|token|cookie|session.?id|auth.?key|enc.?key)\s*[:=]|"
    r"radius[- ]server.*\bkey\b|snmp-server|https?://[^\s/]+:[^\s/]+@", re.I
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): "[redacted]" if SENSITIVE_KEY.search(str(k)) else redact(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
                       "[redacted private key]", value, flags=re.S)
        value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b",
                       "[redacted token]", value)
        return "\n".join("[redacted sensitive line]" if SENSITIVE_LINE.search(line) else line
                         for line in value.splitlines())
    return value
