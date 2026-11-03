"""Only synthetic publication fixtures; no staging/push or private-data output."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from zipfile import BadZipFile

from agent_tools.publication_review import checked_path, private_comparison_values, review, scan_text


class PublicationTests(unittest.TestCase):
    def test_excel_owner_file_skipped_but_real_workbook_is_compared(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / 'Hotels' / 'synthetic-site'
            directory.mkdir(parents=True)
            (directory / '~$inventory.xlsx').write_text('owner-file', encoding='utf8')
            workbook = Workbook()
            workbook.active.append(['password'])
            workbook.active.append(['fixture-inventory-secret'])
            workbook.save(directory / 'inventory.xlsx')
            workbook.close()
            secrets, names = private_comparison_values(root)
            self.assertIn('fixture-inventory-secret', secrets)
            self.assertIn('synthetic-site', names)
            (directory / 'broken.xlsx').write_text('invalid-workbook', encoding='utf8')
            with self.assertRaises(BadZipFile):
                private_comparison_values(root)

    def test_private_paths_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path in ['../outside.py','C:/outside.py','Hotels/demo.py','knowledge/knowledge.db',
                         'README.md','docs/LOCAL_RESULT.md','capture.pcap','credential.pem']:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    checked_path(root, path)

    def test_private_content_inside_python_detected(self):
        found = scan_text('host = "10.23.45.67"\npassword = "fixture-only-password"\n',
                          known_secrets=('fixture-only-password',))
        self.assertIn('ipv4', {x['kind'] for x in found})
        self.assertIn('known_inventory_secret', {x['kind'] for x in found})
        self.assertNotIn('fixture-only-password', repr(found))

    def test_documentation_addresses_are_allowed(self):
        self.assertEqual(scan_text('192.0.2.1 198.51.100.1 203.0.113.1'), [])

    def test_hash_drift_invalidates_reviewed_examples(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);path = root/'sample.py'
            path.write_text('host="10.23.45.67"\n', encoding='utf8')
            manifest = {'files':[{'path':'sample.py','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'reviewed_examples':[{'line':1,'kind':'ipv4','reason':'Synthetic illustration'}]}]}
            self.assertTrue(review(root, manifest)['ready_for_user_review'])
            path.write_text('host="10.23.45.68"\n', encoding='utf8')
            self.assertFalse(review(root, manifest)['ready_for_user_review'])

    def test_known_secret_cannot_be_exempted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'sample.py';path.write_text('fixture-only-password',encoding='utf8')
            manifest={'files':[{'path':'sample.py','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'reviewed_examples':[{'line':1,'kind':'known_inventory_secret','reason':'Invalid exemption'}]}]}
            self.assertFalse(review(root,manifest,known_secrets=('fixture-only-password',))['ready_for_user_review'])

    def test_duplicate_casefolded_paths_rejected(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            review(Path(folder), {'files':[{'path':'A.py'}, {'path':'a.py'}]})
