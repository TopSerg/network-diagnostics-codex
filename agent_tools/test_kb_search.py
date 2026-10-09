"""Offline unit tests for the read-only KB search adapter."""
import sqlite3
import unittest

from kb_search import search


class KnowledgeSearchTests(unittest.TestCase):
    def test_prefer_corporate_wiki(self):
        with sqlite3.connect(':memory:') as con:
            con.row_factory = sqlite3.Row
            con.executescript("""
                CREATE TABLE documents(id TEXT, title TEXT, source_type TEXT,
                    source_url TEXT, date TEXT, vendors TEXT, categories TEXT, path TEXT);
                CREATE TABLE chunks(id INTEGER PRIMARY KEY,doc_id TEXT, position INT,
                    title TEXT, content TEXT);
                CREATE VIRTUAL TABLE chunks_fts USING fts5(title,content,
                    content='chunks',content_rowid='id');
                INSERT INTO documents VALUES
                    ('wiki:1','ICX standard','wiki','url','2026','[]','[]','wiki/a.md'),
                    ('codex:1','ICX case','codex',NULL,'2026','[]','[]','codex/a.md');
                INSERT INTO chunks VALUES
                    (1,'wiki:1',0,'Ruckus ICX','Ruckus VLAN STP'),
                    (2,'codex:1',0,'Ruckus ICX','Ruckus VLAN STP');
                INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');
            """)
            result = search(con, 'Ruckus VLAN', 5, None)
            self.assertEqual(result['match_mode'], 'all_terms')
            self.assertEqual(result['results'][0]['id'], 'wiki:1')
            result = search(con, 'Ruckus unrelated', 5, 'wiki')
            self.assertEqual(result['match_mode'], 'any_term')
            self.assertEqual([r['source_type'] for r in result['results']], ['wiki'])


if __name__ == '__main__':
    unittest.main()
