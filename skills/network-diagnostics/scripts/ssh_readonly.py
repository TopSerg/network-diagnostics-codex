#!/usr/bin/env python3
"""Small safety-oriented wrapper around the system OpenSSH client.

The script is deliberately conservative:
- it expects an SSH alias/host already configured by the operator;
- it never stores credentials;
- it defaults to dry-run;
- it blocks common state-changing/destructive command tokens;
- it keeps normal SSH host-key checking enabled.

This is a convenience guard, not a security boundary. Use least-privilege
network accounts and device-side authorization as the real control.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys


BLOCKED_PATTERNS = [
    r"(^|[\s;/])reload($|[\s;/])",
    r"(^|[\s;/])reboot($|[\s;/])",
    r"write\s+(erase|memory|mem)",
    r"erase\s+(startup-config|configuration|config)",
    r"factory[- ]?reset",
    r"(^|[\s;/])format($|[\s;/])",
    r"(^|[\s;/])delete($|[\s;/])",
    r"(^|[\s;/])shutdown($|[\s;/])",
    r"(^|[\s;/])no\s+shutdown($|[\s;/])",
    r"(^|[\s;/])configure($|[\s;/])",
    r"configure\s+terminal",
    r"(^|[\s;/])conf\s+t($|[\s;/])",
    r"(^|[\s;/])system-view($|[\s;/])",
    r"(^|[\s;/])clear($|[\s;/])",
    r"(^|[\s;/])reset($|[\s;/])",
    r"(^|[\s;/])set($|[\s;/])",
    r"(^|[\s;/])add($|[\s;/])",
    r"(^|[\s;/])remove($|[\s;/])",
    r"(^|[\s;/])disable($|[\s;/])",
    r"(^|[\s;/])enable($|[\s;/])",
]


SAFE_STARTS = (
    "show ",
    "show?",
    "display ",
    "display?",
    "get ",
    "get?",
    "diagnose ip arp list",
    "diagnose sys session list",
    "diagnose vpn tunnel list",
    "/system identity print",
    "/system resource print",
    "/system package print",
    "/interface ",
    "/ip ",
)


def normalize(command: str) -> str:
    return " ".join(command.strip().split()).lower()


def validate(command: str) -> tuple[bool, str]:
    c = normalize(command)
    if not c:
        return False, "empty command"

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, c, flags=re.IGNORECASE):
            return False, f"blocked by safety pattern: {pattern}"

    if not c.startswith(SAFE_STARTS):
        return False, "command is not in the conservative read-only prefix set"

    # RouterOS: only allow read-oriented forms.
    if c.startswith(("/interface ", "/ip ")):
        if " print" not in c and not c.endswith(" print") and " monitor " not in c:
            return False, "RouterOS command must use print or a bounded monitor form"
        if " monitor " in c and " once" not in c:
            return False, "RouterOS monitor must include 'once'"

    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="actually run SSH; default is dry-run")
    parser.add_argument("--connect-timeout", type=int, default=10)
    parser.add_argument("host", help="SSH host or alias from ~/.ssh/config")
    parser.add_argument("command", help="single read-only network CLI command")
    args = parser.parse_args()

    ok, reason = validate(args.command)
    if not ok:
        print(f"REFUSED: {reason}", file=sys.stderr)
        return 2

    argv = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={args.connect_timeout}",
        args.host,
        args.command,
    ]

    print("SSH command:", " ".join(shlex.quote(x) for x in argv))
    if not args.execute:
        print("Dry-run only. Add --execute to run it.")
        return 0

    completed = subprocess.run(argv, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
