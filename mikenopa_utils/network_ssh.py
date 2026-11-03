"""Operational SSH authentication only; never imported by the offline agent.

No commands, password persistence in files, or import-time network operations.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

import paramiko
from paramiko.ssh_exception import BadAuthenticationType, PartialAuthentication

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / 'config/network_diagnostics.json'


@dataclass(frozen=True)
class Credentials:
    username: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self):
        if not self.username or not self.password:
            raise ValueError('Empty credentials')


def load_policy(path=DEFAULT_POLICY):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if value.get('schema_version') != 1 or value.get('auth_order') != ['xnet', 'radius']:
        raise ValueError('Required authentication order: XNet then RADIUS')
    if set(value) != {'schema_version', 'auth_order', 'radius', 'timeouts', 'workers'}:
        raise ValueError('Unexpected policy fields')
    if set(value['radius']) != {'credential_target', 'username_env', 'password_env'}:
        raise ValueError('RADIUS policy contains only credential references')
    if any(not isinstance(x, str) or not x for x in value['radius'].values()):
        raise ValueError('Invalid credential references')
    if set(value['timeouts']) != {'connect', 'banner', 'auth'} or any(
            not isinstance(x, (int, float)) or not 0 < x <= 30 for x in value['timeouts'].values()):
        raise ValueError('Timeouts must be bounded to 30 seconds')
    if not isinstance(value['workers'], int) or not 1 <= value['workers'] <= 6:
        raise ValueError('Workers must be bounded to 1..6')
    return value


def fingerprint(key):
    return base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')


class HostKeyError(RuntimeError):
    pass


class VerifiedHostKey(paramiko.MissingHostKeyPolicy):
    def __init__(self, pins):
        self.pins = dict(pins)

    def missing_host_key(self, client, hostname, key):
        expected = self.pins.get(hostname, '').removeprefix('SHA256:')
        if not expected or fingerprint(key) != expected:
            raise HostKeyError('SSH host key is not trusted; credentials withheld')


class CredentialsUnavailable(RuntimeError):
    pass


class AuthenticationChallengeError(RuntimeError):
    pass


class PasswordAuthentication:
    """SSHClient auth strategy: never answer OTP/password-change challenges."""
    def __init__(self, credentials):self.credentials=credentials

    def authenticate(self, transport):
        creds=self.credentials
        try:
            remaining=transport.auth_password(creds.username,creds.password,fallback=False)
        except BadAuthenticationType as error:
            if 'keyboard-interactive' not in error.allowed_types:raise
            answered=False
            def answer(title,instructions,prompts):
                nonlocal answered
                if answered or len(prompts)!=1 or not re.fullmatch(r'\s*password\s*:\s*',prompts[0][0],re.I):
                    raise AuthenticationChallengeError('Unexpected authentication challenge; no response sent')
                answered=True
                return [creds.password]
            remaining=transport.auth_interactive(creds.username,answer)
        if not transport.is_authenticated():raise PartialAuthentication(remaining or [])
        return []


class PasswordOnlyTransport(paramiko.Transport):
    """Keep the proven SSHClient password flow; bound interactive fallback.

    Empty informational challenges are allowed (Paramiko's legacy flow supports
    them too), but only one ordinary password question can receive a response.
    """
    def auth_interactive(self, username, handler, submethods=''):
        answered=False
        def guarded(title,instructions,prompts):
            nonlocal answered
            if not prompts:return []
            if answered or len(prompts)!=1 or not re.fullmatch(r'\s*password\s*:\s*',prompts[0][0],re.I):
                raise AuthenticationChallengeError('Unexpected authentication challenge; no response sent')
            answered=True
            return handler(title,instructions,prompts)
        return super().auth_interactive(username,guarded,submethods)


class KeyboardInteractiveTransport(PasswordOnlyTransport):
    """Explicit single-password interactive method for a reviewed recovery."""
    def auth_password(self,username,password,event=None,fallback=True):
        if event is not None:raise ValueError('Asynchronous interactive authentication unsupported')
        return self.auth_interactive(username,lambda title,instructions,prompts:[password])


def _windows_api():
    """Load only on explicit credential access; current-user generic credential."""
    if os.name != 'nt':
        raise CredentialsUnavailable('Windows Credential Manager unavailable')
    import ctypes as c
    from ctypes import wintypes as w

    class Credential(c.Structure):
        _fields_ = [('Flags', w.DWORD), ('Type', w.DWORD), ('TargetName', w.LPWSTR),
                    ('Comment', w.LPWSTR), ('LastWritten', w.FILETIME),
                    ('CredentialBlobSize', w.DWORD), ('CredentialBlob', c.POINTER(w.BYTE)),
                    ('Persist', w.DWORD), ('AttributeCount', w.DWORD),
                    ('Attributes', c.c_void_p), ('TargetAlias', w.LPWSTR), ('UserName', w.LPWSTR)]
    api = c.WinDLL('advapi32', use_last_error=True)
    api.CredReadW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(c.POINTER(Credential))]
    api.CredReadW.restype = w.BOOL
    api.CredWriteW.argtypes = [c.POINTER(Credential), w.DWORD]
    api.CredWriteW.restype = w.BOOL
    api.CredFree.argtypes = [c.c_void_p]
    api.CredFree.restype = None
    return c, w, Credential, api


def read_radius_credential(target):
    c, _, Credential, api = _windows_api()
    pointer = c.POINTER(Credential)()
    if not api.CredReadW(target, 1, 0, c.byref(pointer)):
        raise CredentialsUnavailable('RADIUS credential unavailable in Windows Credential Manager')
    try:
        item = pointer.contents
        return Credentials(item.UserName, c.string_at(item.CredentialBlob, item.CredentialBlobSize).decode('utf-16-le'))
    finally:
        api.CredFree(pointer)


def store_radius_credential(target, credentials):
    c, w, Credential, api = _windows_api()
    encoded = credentials.password.encode('utf-16-le')
    if len(encoded) > 2560:
        raise ValueError('Credential exceeds Windows storage limit')
    blob = (w.BYTE * len(encoded)).from_buffer_copy(encoded)
    item = Credential(Type=1, TargetName=target, UserName=credentials.username,
                      CredentialBlobSize=len(encoded), CredentialBlob=blob, Persist=2)
    try:
        if not api.CredWriteW(c.byref(item), 0):
            raise CredentialsUnavailable('Windows Credential Manager write failed')
    finally:
        c.memset(blob, 0, len(encoded))


class RadiusProvider:
    """Lazy, thread-safe process cache; no credential lookup on XNet success."""
    def __init__(self, policy, credentials=None):
        self.settings = policy['radius']
        self.cached = credentials
        self.lock = Lock()

    def __call__(self):
        with self.lock:
            if self.cached is None:
                user = os.environ.get(self.settings['username_env'])
                password = os.environ.get(self.settings['password_env'])
                if user is not None or password is not None:
                    if not user or not password:
                        raise CredentialsUnavailable('Both RADIUS environment variables are required')
                    self.cached = Credentials(user, password)
                else:
                    self.cached = read_radius_credential(self.settings['credential_target'])
            return self.cached


def connect_xnet_then_radius(host, local, pins, radius_provider, *, policy=None,
                            attempts=None, local_rejected=False, client_factory=None,
                            radius_keyboard_interactive=False, local_keyboard_interactive=False,
                            port=22):
    """One XNet attempt, then one RADIUS attempt only on explicit auth rejection.

    local_rejected is an in-operation recovery hint, not a permanent cache.
    Timeouts, partial authentication, trust and transport errors never trigger fallback.
    """
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Invalid SSH port')
    pin_endpoint = host if port == 22 else f'[{host}]:{port}'
    if not pins.get(pin_endpoint):
        raise HostKeyError('SSH host key is missing; credentials withheld')
    policy = policy or load_policy()
    attempts = attempts if attempts is not None else []
    factory = client_factory or paramiko.SSHClient
    for source in ('xnet', 'radius'):
        if source == 'xnet' and (local_rejected or local is None):
            attempts.append({'source': source, 'status': 'previously_rejected_in_operation' if local_rejected else 'unavailable'})
            continue
        try:
            creds = local if source == 'xnet' else radius_provider()
        except Exception:
            attempts.append({'source': source, 'status': 'credentials_unavailable'})
            raise
        client = factory()
        client.set_missing_host_key_policy(VerifiedHostKey(pins))
        try:
            port_args = {'port': port} if port != 22 else {}
            client.connect(host, **port_args, username=creds.username, password=creds.password,
                           transport_factory=KeyboardInteractiveTransport if (source=='radius' and radius_keyboard_interactive) or (source=='xnet' and local_keyboard_interactive) else PasswordOnlyTransport,
                           look_for_keys=False, allow_agent=False,
                           timeout=policy['timeouts']['connect'],
                           banner_timeout=policy['timeouts']['banner'],
                           auth_timeout=policy['timeouts']['auth'])
            if not client.get_transport().is_authenticated():raise PartialAuthentication([])
        except paramiko.AuthenticationException as exc:
            transport=client.get_transport()
            disconnected=transport is None or not transport.is_active()
            client.close()
            uncertain = disconnected or isinstance(exc, (PartialAuthentication, BadAuthenticationType)) or any(
                word in str(exc).lower() for word in ('timeout', 'timed out'))
            attempts.append({'source': source, 'status': 'incomplete' if uncertain else 'rejected'})
            if uncertain or source == 'radius':
                raise
        except Exception:
            client.close()
            attempts.append({'source': source, 'status': 'blocked'})
            raise
        else:
            attempts.append({'source': source, 'status': 'authenticated'})
            return client, source
    raise paramiko.AuthenticationException('Authentication rejected')
