"""ASA / RouterOS RU DC operations; separate from the offline agent.

Publication variant of the existing operational runner with explicit private inputs."""
from pathlib import Path
import argparse
import json
import re
import socket
import sys
import time
import paramiko
from openpyxl import load_workbook
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from mikenopa_utils.network_ssh import Credentials, CredentialsUnavailable, RadiusProvider, connect_xnet_then_radius, load_policy
from mikenopa_utils.credential_input import decode_prompt_password, prompt_secret
FOLDER = None
CA_PATH = None
WORKBOOK = None
TRUST = {}
AUTH_EVENTS = []
EXTRA_SECRETS = []
RADIUS_PROVIDER = None

def devices():
    w = load_workbook(WORKBOOK, read_only=True, data_only=True)
    rows = w.active.iter_rows(values_only=True)
    headers = next(rows)
    result = [dict(zip(headers, row)) for row in rows]
    w.close()
    return result

def clean(text):
    text = re.sub(r'(?i)(password|secret|passphrase|export-passphrase|private-key|auth-key|preshared-key|challenge-password|challenge)=("[^"]*"|\S+)', r'\1=[redacted]', text)
    for d in devices():
        for key in ('password', 'enablePassword', 'ipmiPassword', 'snmpCommunityRead', 'snmpCommunityWrite'):
            value = str(d.get(key) or '')
            if len(value) > 3:
                text = text.replace(value, '[redacted]')
    for value in EXTRA_SECRETS:
        text = text.replace(value, '[redacted]')
    if RADIUS_PROVIDER is not None and RADIUS_PROVIDER.cached is not None:
        text = text.replace(RADIUS_PROVIDER.cached.password, '[redacted]')
    text = re.sub(r'(?i)([?&](?:pass|password|token|secret|key)=)[^&\s"<>]+', r'\1[redacted]', text)
    text = re.sub(r'(?im)^.*(?:\b(?:username|enable|passwd)\b.*\b(?:password|secret)\b|^\s*passwd\s|\bsnmp-server\s+(?:user|host)\b|\bldap-login-password\b).*$','[credential line redacted]',text)
    text = re.sub(r'(?im)^.*(?:snmp-server community|radius-server.*key|tacacs-server.*key|pre-shared-key|encrypted-password|auth-key=|enc-key=).*$','[credential line redacted]',text)
    text = re.sub(r'(?im)^\s*(?:key|password|passwd|secret|ntp authentication-key)\s+.*$','[credential line redacted]',text)
    text = re.sub(r'(?im)^.*(?:keymat|key data|encryption key|authentication key|SK_d|SK_ai|SK_ar|SK_ei|SK_er).*$','[key material redacted]',text)
    text = re.sub(r'(?im)^\s*(?:[0-9a-f]{16,}|(?:[0-9a-f]{2}[ :]+){8,}[0-9a-f]{0,2})\s*$','[opaque hex data redacted]',text)
    text = re.sub(r'(?im)^.*?:\s+(?:[0-9a-f]{8}\s+){2,}[0-9a-f\s]*$','[packet/key hex data redacted]',text)
    return text

def connect(d):
    global RADIUS_PROVIDER
    host = str(d.get('_connect_host') or d['ip'])
    port = int(d.get('_connect_port', 22))
    trust_host = host if port == 22 else f'[{host}]:{port}'
    if not TRUST.get(trust_host):
        raise RuntimeError('Verified SSH host key required; credentials withheld')
    first = Credentials(str(d['login']), str(d['password'])) if d.get('login') and d.get('password') else None
    if d.get('_user_first'):
        if port != 22:
            raise RuntimeError('User-first fallback currently supports port 22 only')
        attempts = []
        def inventory_fallback():
            if d.get('_no_inventory_fallback'):
                raise CredentialsUnavailable('Inventory fallback withheld for this reviewed recovery')
            return Credentials(*d['_inventory_credentials'])
        try:
            c, source = connect_xnet_then_radius(host, first, TRUST,
                inventory_fallback, attempts=attempts,
                local_keyboard_interactive=d.get('_user_keyboard_interactive', False))
        finally:
            AUTH_EVENTS.extend({'host':host, 'source':{'xnet':'user_supplied','radius':'inventory'}[x['source']],
                'status':'withheld_by_recovery_scope' if d.get('_no_inventory_fallback') and x['source']=='radius' and x['status']=='credentials_unavailable' else x['status']} for x in attempts)
            (FOLDER / 'AUTH_STATUS.json').write_text(json.dumps(AUTH_EVENTS, indent=2), encoding='utf-8')
        return c
    if RADIUS_PROVIDER is None:
        RADIUS_PROVIDER = RadiusProvider(load_policy())
    attempts = []
    try:
        c, source = connect_xnet_then_radius(host, first, TRUST, RADIUS_PROVIDER,
                                           attempts=attempts, port=port)
        return c
    finally:
        AUTH_EVENTS.extend({'host': host, 'port': port, **event} for event in attempts)
        (FOLDER / 'AUTH_STATUS.json').write_text(json.dumps(AUTH_EVENTS, indent=2), encoding='utf-8')

def idle(ch, limit=35, gap=1.0):
    deadline = time.monotonic() + limit
    last = time.monotonic()
    out = []
    while time.monotonic() < deadline:
        if ch.recv_ready():
            out.append(ch.recv(65535).decode('utf-8', 'replace'))
            last = time.monotonic()
        elif time.monotonic() - last > gap:
            break
        else:
            time.sleep(.1)
    return ''.join(out)

class CLIReadTimeout(TimeoutError):
    def __init__(self, partial):
        self.partial = partial
        super().__init__('CLI did not reach a prompt within the bounded timeout; do not repeat a submitted change')

def cli_text(text):
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text).replace('\r', '').replace('\x08', '')

def routeros_command_error(response):
    return bool(re.search(r'(?im)^(failure:|input does not match|expected |syntax error|no such item|bad command|bad parameter|script error:)', response)
                or re.search(r'\(:error;\s*line\s+\d+\)', response))

def read_cli(ch, *, allow_password=False, expected_base=None, limit=35):
    """Wait for a real prompt, not a one-second gap in a slow ASA response."""
    deadline = time.monotonic() + limit
    out = ''
    while time.monotonic() < deadline:
        if ch.recv_ready():
            chunk = ch.recv(65535)
            if not chunk:
                raise EOFError('CLI channel closed')
            out += chunk.decode('utf-8', 'replace')
            if len(out) > 2_000_000:
                raise RuntimeError('CLI response exceeded the size bound')
            plain = cli_text(out).rstrip()
            tail = plain.split('\n')[-1] if plain else ''
            prompt_pattern = (re.escape(expected_base) + r'(?:\([A-Za-z0-9_.:-]+\))?[#>]'
                              if expected_base else r'[A-Za-z0-9][A-Za-z0-9_.:/()-]{0,178}[#>]')
            if re.fullmatch(prompt_pattern, tail):
                return out
            if allow_password and re.fullmatch(r'\s*Password\s*:', tail, re.I):
                return out
        elif ch.closed:
            raise EOFError('CLI channel closed')
        else:
            time.sleep(.1)
    raise CLIReadTimeout(out)


def public_certificates_from_log(raw, prefix):
    """Extract only DER X.509 payloads, never key/auth/packet dumps."""
    from cryptography import x509
    blocks, current = [], None
    for line in raw.splitlines():
        if prefix + ':' not in line:
            continue
        message = line.split(prefix + ':', 1)[1].strip()
        heading = re.fullmatch(r'=> certificate \(size 0x([0-9a-fA-F]+)\)', message)
        if heading:
            if current is not None:
                blocks.append(current)
            current = [int(heading.group(1), 16), bytearray()]
        elif message.startswith('=>'):
            if current is not None:
                blocks.append(current)
            current = None
        elif current is not None and re.fullmatch(r'(?:[0-9a-fA-F]{2,8}\s*)+', message) and message:
            current[1].extend(bytes.fromhex(message))
    if current is not None:
        blocks.append(current)
    result = []
    for size, body in blocks:
        if len(body) != size or size > 16384:
            continue
        try:
            result.append(x509.load_der_x509_certificate(bytes(body)))
        except ValueError:
            continue
    return result


def recover_peer_certificate(d, prefix, expected_cn):
    """Read already captured public peer certificates and verify the approved CA chain."""
    from datetime import datetime, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    if not re.fullmatch(r'[A-Z0-9_]{1,64}', prefix or '') or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', expected_cn or ''):
        raise ValueError('Exact safe log prefix and expected peer CN required')
    c = connect(d)
    try:
        def query(command):
            _, stdout, stderr = c.exec_command(command, timeout=45)
            stdout.channel.settimeout(45)
            raw = stdout.read(2_000_001)
            error = stderr.read(65536)
            if len(raw) > 2_000_000 or error.strip():
                raise RuntimeError('Bounded certificate read failed')
            return raw.decode('utf-8', 'replace')
        identity = query('/system identity print')
        board = query('/system routerboard print')
        if not re.search(r'(?m)^\s*name:\s*' + re.escape(str(d['controlName'])) + r'\s*$', identity):
            raise RuntimeError('Router identity mismatch')
        if not re.search(r'(?m)^\s*serial-number:\s*' + re.escape(str(d['serialNumber'])) + r'\s*$', board):
            raise RuntimeError('Router serial mismatch')
        raw = query('/log print without-paging where message~"' + prefix + '"')
        certs = public_certificates_from_log(raw, prefix)
        del raw
    finally:
        c.close()
    root = x509.load_pem_x509_certificate(CA_PATH.read_bytes())
    matches = [cert for cert in certs if cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
               and cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value == expected_cn]
    if not matches:
        raise RuntimeError('Expected peer certificate not found; no trust/configuration changed')
    leaf = matches[-1]
    issuer = next((cert for cert in certs + [root] if cert.subject == leaf.issuer), None)
    if issuer is None:
        raise RuntimeError('Peer issuer certificate missing')
    leaf.verify_directly_issued_by(issuer)
    issuer.verify_directly_issued_by(root)
    now = datetime.now(timezone.utc)
    if not all(cert.not_valid_before_utc <= now < cert.not_valid_after_utc for cert in (leaf, issuer, root)):
        raise RuntimeError('Peer CA chain is outside its validity period')
    if leaf.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise RuntimeError('Expected peer is a CA, not a leaf')
    (FOLDER / 'RU_DC_peer.crt').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    (FOLDER / 'RU_DC_peer_issuer.crt').write_bytes(issuer.public_bytes(serialization.Encoding.PEM))
    result = {'expected_cn': expected_cn, 'subject': leaf.subject.rfc4514_string(),
              'issuer': leaf.issuer.rfc4514_string(), 'sha256': leaf.fingerprint(hashes.SHA256()).hex(),
              'chain_verified_to_approved_root': True, 'valid_at_utc': now.isoformat(),
              'not_after_utc': leaf.not_valid_after_utc.isoformat(), 'private_material_extracted': False}
    (FOLDER / 'RU_DC_PEER_CERTIFICATE_VERIFICATION.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))

def run(d, commands, label, stop_on_error=False):
    c = connect(d)
    output = []
    try:
        if any(t in str(d.get('model', '')).lower() for t in ('asa', 'cisco', 'ws-c')):
            ch = c.invoke_shell(width=240, height=1000)
            banner = read_cli(ch)
            prompt_base = cli_text(banner).rstrip().split('\n')[-1][:-1]
            enable_trace = ['$ initial CLI\n' + clean(banner)]
            if not cli_text(banner).rstrip().endswith('#'):
                ch.sendall('enable\r')
                response = read_cli(ch, allow_password=True, expected_base=prompt_base)
                enable_trace.append('$ enable prompt\n' + clean(response))
                if re.search(r'(?im)^\s*Password\s*:\s*$', cli_text(response)):
                    ch.sendall(str(d.get('enablePassword') or d['password']) + '\r')
                    enabled = read_cli(ch, allow_password=True, expected_base=prompt_base)
                    enable_trace.append('$ enable result\n' + clean(enabled))
                    response += enabled
                if not cli_text(response).rstrip().endswith('#'):
                    (FOLDER / (label + '_enable.log')).write_text('\n'.join(enable_trace), encoding='utf-8')
                    raise RuntimeError('Cisco enable failed')
            (FOLDER / (label + '_enable.log')).write_text('\n'.join(enable_trace), encoding='utf-8')
            ch.sendall(('terminal pager 0' if 'asa' in str(d.get('model', '')).lower() else 'terminal length 0') + '\r')
            read_cli(ch, expected_base=prompt_base)
            for cmd in commands:
                ch.sendall(cmd + '\r')
                try:
                    response = read_cli(ch, expected_base=prompt_base)
                except CLIReadTimeout as error:
                    output.append('$ ' + clean(cmd) + '\n' + clean(error.partial) + '\n[response incomplete; submitted result unknown]')
                    (FOLDER / (label + '.log')).write_text('\n'.join(output), encoding='utf-8')
                    raise
                output.append('$ ' + clean(cmd) + '\n' + clean(response))
                (FOLDER / (label + '.log')).write_text('\n'.join(output), encoding='utf-8')
                if stop_on_error and re.search(r'(?im)^\s*(?:%\s*)?(?:ERROR:|Invalid input|Invalid command|Unrecognized command|Command authorization failed|Authorization failed)', response):
                    raise RuntimeError('Stopped after Cisco command error; inspect the saved partial journal')
        else:
            for cmd in commands:
                _, out, err = c.exec_command(cmd, timeout=45)
                out.channel.settimeout(45)
                response = clean(out.read().decode('utf-8', 'replace') + err.read().decode('utf-8', 'replace'))
                output.append('$ ' + clean(cmd) + '\n' + response)
                if stop_on_error and routeros_command_error(response):
                    text = '\n'.join(line for line in '\n'.join(output).splitlines() if line.strip())
                    (FOLDER / (label + '.log')).write_text(text, encoding='utf-8')
                    print(text, flush=True)
                    raise RuntimeError('Stopped after RouterOS command error')
        text = '\n'.join(line for line in '\n'.join(output).splitlines() if line.strip())
        (FOLDER / (label + '.log')).write_text(text, encoding='utf-8')
        print(text, flush=True)
        return text
    finally:
        c.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['inventory', 'read', 'file', 'upload-ca', 'upload', 'backup', 'download', 'peer-certificate'])
    p.add_argument('--host')
    p.add_argument('--connect-host')
    p.add_argument('--connect-port', type=int, default=22)
    p.add_argument('--command', action='append')
    p.add_argument('--path')
    p.add_argument('--label', required=True, help='Unique operation phase; do not reuse a submitted change label')
    p.add_argument('--username')
    p.add_argument('--prompt-password', action='store_true')
    p.add_argument('--password-input-encoding', '--prompt-input-encoding', dest='password_input_encoding',
                   choices=('plain', 'hex'), default='plain',
                   help='Masked stdin transport only; hex avoids Windows PTY punctuation loss. Never pass the value as an argument.')
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--trust', type=Path, required=True)
    p.add_argument('--user-first', action='store_true', help='Explicit user-authorized account first, inventory on auth rejection only')
    p.add_argument('--prompt-scep-challenge', action='store_true', help='Replace {{SCEP_CHALLENGE}} in a reviewed command file in memory')
    p.add_argument('--user-keyboard-interactive', action='store_true', help='Explicit single-password interactive authentication for a reviewed recovery')
    p.add_argument('--no-inventory-fallback', action='store_true')
    p.add_argument('--log-prefix')
    p.add_argument('--expected-peer-cn')
    p.add_argument('--ca', type=Path, help='Independently approved local root CA; never taken from the peer')
    a = p.parse_args()
    if a.password_input_encoding != 'plain' and not (a.prompt_password or a.prompt_scep_challenge):
        p.error('--password-input-encoding requires a password or SCEP challenge prompt')
    WORKBOOK = a.inventory
    CA_PATH = a.ca
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', a.label):
        p.error('Safe unique label required')
    if a.mode in ('upload-ca', 'peer-certificate') and (CA_PATH is None or not CA_PATH.is_file()):
        p.error('This mode requires --ca with an approved local certificate')
    if a.output_dir:
        FOLDER = a.output_dir
        FOLDER.mkdir(parents=True, exist_ok=True)
        auth_path = FOLDER / 'AUTH_STATUS.json'
        if auth_path.exists():
            AUTH_EVENTS = json.loads(auth_path.read_text(encoding='utf-8'))
            if not isinstance(AUTH_EVENTS, list) or not all(isinstance(event, dict) for event in AUTH_EVENTS):
                p.error('Invalid operation authentication journal')
    if a.trust:
        TRUST = json.loads(a.trust.read_text(encoding='utf-8-sig'))
        if not isinstance(TRUST, dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in TRUST.items()):
            p.error('Trust must map exact SSH hosts to independently verified SHA256 fingerprints')
    if a.user_first and not (a.username and a.prompt_password):
        p.error('--user-first requires --username and --prompt-password')
    if (a.user_keyboard_interactive or a.no_inventory_fallback) and not a.user_first:
        p.error('User authentication recovery options require --user-first')
    if a.mode == 'inventory':
        for d in devices():
            if any(t in str(d.get('model', '')).lower() for t in ('mikrotik', 'asa', 'cisco')):
                print(json.dumps({k:v for k,v in d.items() if not any(t in str(k).lower() for t in ('pass', 'secret', 'community', 'login'))}, ensure_ascii=False, default=str))
    else:
        selected = [d for d in devices() if str(d.get('ip')) == a.host]
        if not a.host or len(selected) != 1:
            p.error('Exactly one inventory device must match --host')
        d = selected[0]
        if a.mode in ('read', 'file') and not (a.command if a.mode == 'read' else a.path):
            p.error('Read requires --command; file requires --path')
        if a.mode in ('upload', 'download') and not a.path:
            p.error('Transfer requires --path')
        if a.user_first:
            d['_inventory_credentials'] = (str(d['login']), str(d['password']))
            d['_user_first'] = True
            d['_user_keyboard_interactive'] = a.user_keyboard_interactive
            d['_no_inventory_fallback'] = a.no_inventory_fallback
        d['_connect_host'] = a.connect_host or a.host
        d['_connect_port'] = a.connect_port
        if a.username:
            d['login'] = a.username
        if a.prompt_password:
            d['password'] = prompt_secret('Device password', a.password_input_encoding,
                                          redactions=EXTRA_SECRETS)
        if a.mode == 'peer-certificate':
            recover_peer_certificate(d, a.log_prefix, a.expected_peer_cn)
            sys.exit(0)
        if a.mode in ('upload-ca', 'upload', 'backup', 'download'):
            c = connect(d)
            try:
                if a.mode == 'backup':
                    stamp = a.label
                    _, stdout, stderr = c.exec_command('/export file=' + stamp, timeout=45)
                    response = stdout.read().decode() + stderr.read().decode()
                    if response.strip():
                        print(clean(response))
                    remote = stamp + '.rsc'
                    with c.open_sftp() as s:
                        local_name = str(d['controlName']) + '_' + stamp + '.rsc'
                        s.get(remote, str(FOLDER / local_name))
                    print('Backup downloaded')
                elif a.mode == 'download':
                    with c.open_sftp() as s:
                        s.get(a.path, str(FOLDER / Path(a.path).name))
                    print('Downloaded', Path(a.path).name)
                elif a.mode == 'upload':
                    with c.open_sftp() as s:
                        s.put(a.path, Path(a.path).name)
                    print('Uploaded', Path(a.path).name)
                else:
                    with c.open_sftp() as s:
                        s.put(str(CA_PATH), CA_PATH.name)
                    print('CA uploaded')
            finally:
                c.close()
            sys.exit(0)
        commands = a.command if a.mode == 'read' else [s.strip() for s in Path(a.path).read_text(encoding='utf-8-sig').splitlines() if s.strip() and not s.strip().startswith('#')]
        if a.prompt_scep_challenge:
            if a.mode != 'file' or sum('{{SCEP_CHALLENGE}}' in cmd for cmd in commands) != 1:
                p.error('SCEP challenge requires one placeholder in a reviewed command file')
            challenge = prompt_secret('SCEP challenge', a.password_input_encoding,
                                      redactions=EXTRA_SECRETS)
            if not challenge or any(c in challenge for c in '\r\n"\\$'):
                p.error('Unsupported characters in SCEP challenge')
            EXTRA_SECRETS.append(challenge)
            commands = [cmd.replace('{{SCEP_CHALLENGE}}', challenge) for cmd in commands]
        elif any('{{SCEP_CHALLENGE}}' in cmd for cmd in commands or []):
            p.error('Use --prompt-scep-challenge; challenge must not be stored in command files')
        run(d, commands, a.label, stop_on_error=a.mode == 'file')
