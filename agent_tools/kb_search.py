#!/usr/bin/env python3
"""Read-only search for a locally extracted Mikenopa network-agent knowledge base.

This tool never downloads, uploads, indexes or executes retrieved content.
Search snippets can contain private information; keep results in the local worktree.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

SOURCES = ('wiki', 'attachment', 'chatgpt', 'codex')


def resolve_db(explicit: str | None) -> Path:
    root = Path(__file__).resolve().parent.parent
    candidates = [
        explicit,
        os.environ.get('MIKENOPA_KB_DB'),
        str(root / 'knowledge' / 'network_agent_kb' / 'knowledge.db'),
        str(root / 'network_agent_kb' / 'knowledge.db'),
    ]
    for item in candidates:
        if item and Path(item).expanduser().is_file():
            return Path(item).expanduser().resolve()
    raise FileNotFoundError(
        'Knowledge DB not found. Extract the private ZIP locally and set '
        'MIKENOPA_KB_DB or pass --db <path-to-knowledge.db>.'
    )


def tokens_from(query: str) -> list[str]:
    return re.findall(r'[\w-]+', query, re.UNICODE)[:12]


def search(con: sqlite3.Connection, query: str, top: int, source: str | None) -> dict:
    tokens = tokens_from(query)
    if not tokens:
        raise ValueError('Search query does not contain terms')
    fields = """SELECT d.id, d.title, d.source_type, d.source_url, d.date,
        d.vendors, d.categories, d.path, c.position,
        snippet(chunks_fts, 1, '[[', ']]', ' … ', 24) AS snippet,
        bm25(chunks_fts, 3.0, 1.0) AS score
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        JOIN documents d ON d.id = c.doc_id
        WHERE chunks_fts MATCH ?"""
    if source:
        fields += ' AND d.source_type = ?'
    fields += ' ORDER BY score LIMIT ?'
    for mode, sep in [('all_terms', ' AND '), ('any_term', ' OR ')]:
        match_query = sep.join('"' + t.replace('"', '') + '"' for t in tokens)
        args = [match_query]
        if source:
            args.append(source)
        args.append(min(max(top * 20, 40), 400))
        rows = con.execute(fields, args).fetchall()
        if rows:
            break
    else:
        mode, rows = 'none', []
    # Prefer corporate sources over unverified historic conversations.
    rank = {'wiki': 0, 'attachment': 1, 'codex': 2, 'chatgpt': 3}
    seen: set[str] = set()
    out: list[dict] = []
    for r in sorted(rows, key=lambda r: (rank.get(r['source_type'], 9), r['score'])):
        if r['id'] in seen:
            continue
        seen.add(r['id'])
        out.append({k: r[k] for k in ('id', 'title', 'source_type', 'source_url',
                    'date', 'vendors', 'categories', 'path', 'position', 'snippet')})
        if len(out) >= top:
            break
    return {'query': query, 'match_mode': mode, 'results': out,
            'notice': 'Historic results are not proof of current network state.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query')
    parser.add_argument('--db', help='Path to locally extracted private knowledge.db')
    parser.add_argument('--top', type=int, default=8)
    parser.add_argument('--source', choices=SOURCES)
    args = parser.parse_args(argv)
    if not 1 <= args.top <= 25:
        parser.error('--top must be 1..25')
    try:
        path = resolve_db(args.db)
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5) as con:
            con.row_factory = sqlite3.Row
            result = search(con, args.query, args.top, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (sqlite3.Error, ValueError, OSError) as exc:
        print(f'kb_search: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
