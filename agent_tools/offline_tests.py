"""Run explicit offline test suites under a process-wide network/process deny guard."""
from __future__ import annotations

import argparse
import contextlib
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch


def forbidden(*args, **kwargs):
    raise AssertionError('Offline test guard: network or external process execution forbidden')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operational', action='store_true', help='Also run mocked RU DC / SSH tests; install requirements-operational.txt')
    args = parser.parse_args()
    # Existing root runner tests import live-default/UI modules; intentionally exclude them.
    patterns = ['test_agent_*.py', 'test_xnet_parsing.py', 'test_wlc_ssh.py',
                'test_ssid_manager.py', 'test_daktela_tickets.py']
    if args.operational:
        patterns += ['test_network_ssh.py', 'test_ru_dc_vpn.py']
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, 'connect', forbidden))
        stack.enter_context(patch.object(socket.socket, 'connect_ex', forbidden))
        stack.enter_context(patch.object(socket, 'getaddrinfo', forbidden))
        stack.enter_context(patch.object(socket, 'create_connection', forbidden))
        stack.enter_context(patch.object(subprocess, 'Popen', forbidden))
        suite = unittest.TestSuite()
        for pattern in patterns:
            suite.addTests(unittest.defaultTestLoader.discover('tests', pattern=pattern))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
