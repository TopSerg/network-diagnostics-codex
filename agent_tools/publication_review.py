"""Review ONLY an explicit publication manifest. Never stages, uploads or pushes."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re

PRIVATE_ROOTS = frozenset(x.casefold() for x in (
    'knowledge', 'network_agent_kb', 'Hotels', 'Knowledge Base', 'Ru Dc', 'WLC', 'data',
    'logs', '.cache', 'browser_profiles', '.chrome-meraki', '.tmp_snmp', 'divers', 'agent_reports', '.git'
))
PRIVATE_SUFFIXES = {'.zip','.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx','.mobaconf',
                    '.pcap','.pcapng','.xlsx','.xls','.csv','.rsc','.crt','.der'}
PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'token_shape': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b'),
    'credential_literal': re.compile(r'''(?i)(?:password|passwd|secret|token|community|api_key)\s*[:=]\s*['"]([^'"\n]{4,})['"]'''),
    'corporate_url': re.compile(r'(?i)https?://(?:xnet|wiki|daktela|mars)[.\w/-]*'),
    'user_profile_path': re.compile(r'(?i)[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]'),
    'ipv4': re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])'),
}
DOCUMENTATION_NETS = tuple(ipaddress.ip_network(s) for s in (
    '192.0.2.0/24','198.51.100.0/24','203.0.113.0/24','127.0.0.0/8','0.0.0.0/32'
))
PUBLIC_PROJECT_IDENTIFIERS = frozenset({'mikenopa'})


def checked_path(root: Path, relative: str) -> Path:
    p = PurePosixPath(relative)
    if not relative or p.is_absolute() or '..' in p.parts or '\\' in relative or ':' in relative:
        raise ValueError('Invalid publication path')
    if p.parts[0].casefold() in PRIVATE_ROOTS or Path(relative).suffix.lower() in PRIVATE_SUFFIXES:
        raise ValueError('Private data class prohibited')
    if relative == 'README.md' or Path(relative).name.startswith('LOCAL_'):
        raise ValueError('Private local report prohibited')
    path = root / Path(*p.parts)
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Publication source missing or outside workspace')
    if any(part.is_symlink() for part in [path, *path.parents] if part != root.parent):
        raise ValueError('Symlink sources prohibited')
    return path


def scan_text(text: str, *, known_secrets: tuple[str, ...] = (), customer_names: tuple[str, ...] = ()) -> list[dict]:
    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        kinds = set()
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                if kind == 'ipv4':
                    try:
                        address = ipaddress.ip_address(match.group())
                    except ValueError:
                        continue
                    if any(address in network for network in DOCUMENTATION_NETS):
                        continue
                kinds.add(kind)
        for value in known_secrets:
            if len(value) >= 6 and value in line:
                kinds.add('public_identifier_collision' if value.casefold() in PUBLIC_PROJECT_IDENTIFIERS
                          else 'known_inventory_secret')
        if any(value.casefold() in line.casefold() for value in customer_names if len(value) >= 7):
            kinds.add('customer_identifier')
        findings.extend({'line': n, 'kind': kind} for kind in sorted(kinds))
    return findings


def private_comparison_values(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Explicit local comparison only. Values never appear in review output."""
    from openpyxl import load_workbook
    secrets = set()
    for directory in ('Hotels', 'WLC', 'data'):
        for path in (root / directory).rglob('*.xlsx'):
            # Excel owner/lock files are not XLSX workbooks and may be locked.
            # Real workbook errors must still stop the privacy comparison.
            if path.name.startswith('~$'):
                continue
            workbook = load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet in workbook:
                    rows = sheet.iter_rows(values_only=True)
                    headers = next(rows, ())
                    columns = [i for i, key in enumerate(headers) if re.search(
                        r'password|passwd|passphrase|secret|token|community|api.?key', str(key), re.I)]
                    for values in rows:
                        for i in columns:
                            if i < len(values) and values[i] is not None:
                                value = str(values[i])
                                if len(value) >= 6:
                                    secrets.add(value)
            finally:
                workbook.close()
    names = tuple(path.name for path in (root / 'Hotels').iterdir() if path.is_dir()) if (root / 'Hotels').is_dir() else ()
    return tuple(secrets), names


def review(root: Path, manifest: dict, *, known_secrets: tuple[str, ...] = (),
           customer_names: tuple[str, ...] = ()) -> dict:
    files = manifest['files']
    paths = [item['path'] for item in files]
    if len(set(p.casefold() for p in paths)) != len(paths):
        raise ValueError('Duplicate publication paths')
    rows = []
    for item in files:
        path = checked_path(root, item['path'])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        # An exemption is scoped to a reviewed file hash and specific line/kind.
        valid_hash = digest == item['sha256']
        exceptions = {(e['line'], e['kind']) for e in item.get('reviewed_examples', [])
                      if e.get('reason') and valid_hash}
        found = scan_text(path.read_text(encoding='utf-8-sig'), known_secrets=known_secrets,
                          customer_names=customer_names)
        unresolved = [f for f in found if (f['line'], f['kind']) not in exceptions]
        # Real secrets and customer identifiers cannot be exempted as examples.
        unresolved += [f for f in found if f['kind'] in {'known_inventory_secret','customer_identifier'}
                       and f not in unresolved]
        rows.append({'path': item['path'], 'hash_matches': valid_hash, 'findings': found,
                     'unresolved': unresolved})
    ready = all(row['hash_matches'] and not row['unresolved'] for row in rows)
    return {'files_checked': len(rows), 'ready_for_user_review': ready, 'published': False,
            'notice': 'Local content review only; no Git history scan, license clearance or upload. Confirm before publication.',
            'files': rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('docs/PUBLICATION_MANIFEST.json'))
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--compare-private-inventory', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        secrets, names = private_comparison_values(args.root) if args.compare_private_inventory else ((), ())
        result = review(args.root, json.loads(args.manifest.read_text(encoding='utf8')),
                        known_secrets=secrets, customer_names=names)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
        print(json.dumps({k:v for k,v in result.items() if k != 'files'}, ensure_ascii=False, indent=2))
        return 0 if result['ready_for_user_review'] else 2
    except Exception as exc:
        print(json.dumps({'status':'refused','error_type':type(exc).__name__,'published':False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
