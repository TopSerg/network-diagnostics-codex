"""Operational prompt transport only; no persistence, networking or agent imports.

Windows automated PTY input can drop punctuation such as @. Explicit hex mode
transports UTF-8 bytes using ASCII digits, then decodes them only in memory.
Hex is reversible secret material, not encryption.
"""
from __future__ import annotations

import getpass
import re
import warnings


def decode_prompt_password(value, encoding='plain'):
    if encoding == 'plain':
        return value
    if encoding != 'hex' or not re.fullmatch(r'(?:[0-9a-fA-F]{2})+', value):
        raise ValueError('Invalid encoded password input')
    try:
        decoded = bytes.fromhex(value).decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('Invalid encoded password input') from None
    if not decoded or any(char in decoded for char in '\r\n\x00'):
        raise ValueError('Invalid encoded password input')
    return decoded


def prompt_secret(label, encoding='plain', *, redactions=None):
    if encoding not in ('plain', 'hex'):
        raise ValueError('Unsupported prompt input encoding')
    suffix = ' (hidden UTF-8 hex transport)' if encoding == 'hex' else ''
    # getpass otherwise falls back to visible stdin when echo control fails.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            entered = getpass.getpass(label + suffix + ': ')
        except getpass.GetPassWarning:
            raise ValueError('Hidden input unavailable; use a secure credential source') from None
    if redactions is not None:
        redactions.append(entered)
    decoded = decode_prompt_password(entered, encoding)
    if redactions is not None:
        redactions.append(decoded)
    return decoded


def prompt_username(label='RADIUS username', encoding='plain'):
    # Email-style logins can lose @ through the same PTY input path.
    if encoding == 'plain':
        return input(label + ': ')
    return prompt_secret(label, encoding)


def add_prompt_encoding_argument(parser):
    parser.add_argument('--prompt-input-encoding', '--password-input-encoding',
                        choices=('plain', 'hex'), default='plain',
                        help='Hidden prompt transport only; use hex for automated Windows PTY. '
                             'Never pass secret values or their hex in arguments.')
