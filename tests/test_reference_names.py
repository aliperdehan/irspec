"""Reference output names cannot act as paths."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from irspec import session

DATA = Path(__file__).parent / 'data'


class ReferenceNames(unittest.TestCase):
    def test_manifest_and_cas_map_paths_are_rejected_before_any_conversion(self):
        for source in ('manifest', 'cas_names'):
            for kind in ('jdx', 'img'):
                for name in ('../../outside', '/absolute', r'..\..\outside',
                             r'C:\outside', 'C:outside', '.', '..', '', 123, 'bad\0name'):
                    with self.subTest(source=source, kind=kind, name=name):
                        with tempfile.TemporaryDirectory() as d:
                            folder = Path(d) / 'session'
                            (folder / kind).mkdir(parents=True)
                            rel = f'{kind}/62-44-2-IR.' + ('jdx' if kind == 'jdx' else 'png')
                            if kind == 'jdx':
                                shutil.copy(DATA / 'phenacetin_T.jdx', folder / rel)
                            else:
                                (folder / rel).write_bytes(b'digitiser must not open this')
                            outside = Path(d) / 'outside.csv'
                            outside.write_bytes(b'existing CSV\n')
                            entry = {'file': rel, 'title': 'Reference'}
                            if source == 'manifest':
                                entry['name'] = name
                            else:
                                (folder / 'cas_names.json').write_text(json.dumps({'62-44-2': name}))
                            (folder / 'manifest.json').write_text(json.dumps([entry]))
                            with patch.object(session, 'call', side_effect=AssertionError(
                                    'conversion started before validating the output path')) as convert:
                                with self.assertRaisesRegex(session.SessionError, 'filename component'):
                                    session.run(str(folder), build='none')
                                convert.assert_not_called()
                            self.assertEqual(outside.read_bytes(), b'existing CSV\n')
                            self.assertFalse((folder / 'figures.json').exists())

    def test_symlink_outputs_are_rejected_before_conversion(self):
        for kind, target in (('jdx', 'csv/SAFE.csv'), ('jdx', 'plain/SAFE.csv'),
                             ('img', 'csv/SAFE.csv'), ('img', 'plain/SAFE.csv'),
                             ('img', 'check/SAFE_overlay.png'), ('img', 'check/SAFE.log')):
            with self.subTest(kind=kind, target=target), tempfile.TemporaryDirectory() as d:
                folder = Path(d) / 'session'
                for sub in (kind, 'csv', 'plain', 'check'):
                    (folder / sub).mkdir(parents=True, exist_ok=True)
                outside = Path(d) / 'outside.csv'
                outside.write_bytes(b'existing CSV\n')
                (folder / target).symlink_to(outside)
                rel = f'{kind}/sample.' + ('jdx' if kind == 'jdx' else 'png')
                if kind == 'jdx':
                    shutil.copy(DATA / 'phenacetin_T.jdx', folder / rel)
                else:
                    (folder / rel).write_bytes(b'digitiser must not open this')
                with patch.object(session, 'call', side_effect=AssertionError(
                                    'conversion started before validating the output path')) as convert:
                    with self.assertRaisesRegex(session.SessionError, 'outside'):
                        session.process(str(folder), {'file': rel, 'name': 'SAFE'},
                                        str(folder / 'csv'), str(folder / 'plain'))
                    convert.assert_not_called()
                self.assertEqual(outside.read_bytes(), b'existing CSV\n')

    def test_existing_reference_name_convention_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / 'cas_names.json').write_text(json.dumps({'62-44-2': 'PHENACETIN_GAS'}))
            entry = {'file': 'jdx/62-44-2-IR.jdx'}
            self.assertEqual(session.reference_name(d, entry), 'PHENACETIN_GAS')
            self.assertEqual(session.reference_name(d, {**entry, 'name': 'CUSTOM'}), 'CUSTOM')
            self.assertEqual(session.reference_name(d, {'file': 'img/book_fig.png'}), 'book_fig')
