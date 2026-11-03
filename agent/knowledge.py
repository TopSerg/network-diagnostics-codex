"""Read-only access to the private local corpus; no network or embedded commands."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from agent_tools.kb_search import resolve_db, search
from agent_tools.redaction import redact


class LocalKnowledge:
    def __init__(self, database: str | None = None):
        self.database = database

    def lookup(self, query: str, top: int = 6, source: str | None = None) -> dict:
        path = resolve_db(self.database)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            # Corporate lookup first, even when history matches more query terms.
            # any_term remains explicitly marked: relevance must still be reviewed.
            result = search(connection, query, top, source or 'wiki')
            if source is None and not result['results']:
                result = search(connection, query, top, None)
        return redact(result)
