"""JCAMP display names are never interpreted as output paths."""
import json
import tempfile
import unittest
from pathlib import Path

from irspec import session

DATA = Path(__file__).parent / 'data'


def write_spectrum(path, title):
    text = (DATA / 'phenacetin_T.jdx').read_text()
    old = next(line for line in text.splitlines() if line.startswith('##TITLE='))
    path.write_text(text.replace(old, '##TITLE=' + title))


class JdxFilenames(unittest.TestCase):
    def test_batch_title_and_name_map_cannot_escape_either_directory(self):
        for source in ('title', 'name_map'):
            for name in ('../victim', '../../victim', r'..\victim', r'C:\victim', '.', '..'):
                with self.subTest(source=source, name=name), tempfile.TemporaryDirectory() as d:
                    root = Path(d)
                    inputs, archival, plain = root / 'jdx', root / 'exports', root / 'plain'
                    inputs.mkdir()
                    victim = root / 'victim.csv'
                    victim.write_bytes(b'existing CSV\n')
                    write_spectrum(inputs / 'sample.jdx', name if source == 'title' else 'Display')
                    argv = ['batch', inputs, '--out-dir', archival, '--plain-dir', plain]
                    if source == 'name_map':
                        names = root / 'names.json'
                        names.write_text(json.dumps({'62-44-2': name}))
                        argv += ['--name-map', names]
                    code, out, err = session.call('jdx_tool', argv)
                    self.assertEqual(code, 0, err)
                    self.assertEqual(victim.read_bytes(), b'existing CSV\n')
                    csvs, plains = list(archival.glob('*.csv')), list(plain.glob('*.csv'))
                    self.assertEqual(len(csvs), 1)
                    self.assertEqual(len(plains), 1)
                    self.assertEqual(csvs[0].name, plains[0].name)
                    self.assertEqual(csvs[0].read_text().splitlines()[0], f';{name};')
                    self.assertTrue(plains[0].read_text().startswith('wavenumber,intensity\n'))

    def test_default_convert_handles_relative_absolute_and_override_names(self):
        for source in ('title', 'override'):
            for absolute in (False, True):
                with self.subTest(source=source, absolute=absolute), tempfile.TemporaryDirectory() as d:
                    root = Path(d)
                    inputs = root / 'jdx'
                    inputs.mkdir()
                    victim = root / 'victim.csv'
                    victim.write_bytes(b'existing CSV\n')
                    name = str(root / 'victim') if absolute else '../victim'
                    spectrum = inputs / 'sample.jdx'
                    write_spectrum(spectrum, name if source == 'title' else 'Display')
                    argv = ['convert', spectrum]
                    if source == 'override':
                        argv += ['--name', name]
                    code, out, err = session.call('jdx_tool', argv)
                    self.assertEqual(code, 0, err)
                    self.assertEqual(victim.read_bytes(), b'existing CSV\n')
                    csvs = list(inputs.glob('*.csv'))
                    self.assertEqual(len(csvs), 1)
                    self.assertEqual(csvs[0].read_text().splitlines()[0], f';{name};')

    def test_batch_preflights_both_destinations_including_symlinks(self):
        for destination in ('exports', 'plain'):
            with self.subTest(destination=destination), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                for sub in ('jdx', 'exports', 'plain'):
                    (root / sub).mkdir()
                write_spectrum(root / 'jdx/sample.jdx', 'SAFE')
                victim = root / 'victim.csv'
                victim.write_bytes(b'existing CSV\n')
                (root / destination / 'SAFE.csv').symlink_to(victim)
                code, out, err = session.call('jdx_tool', ['batch', root / 'jdx',
                    '--out-dir', root / 'exports', '--plain-dir', root / 'plain'])
                self.assertNotEqual(code, 0)
                self.assertIn('outside', err)
                self.assertNotIn('Traceback', err)
                self.assertEqual(victim.read_bytes(), b'existing CSV\n')
                other = root / ('plain' if destination == 'exports' else 'exports')
                self.assertEqual(list(other.iterdir()), [])

    def test_default_convert_rejects_an_existing_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inputs = root / 'jdx'
            inputs.mkdir()
            spectrum = inputs / 'sample.jdx'
            write_spectrum(spectrum, 'SAFE')
            victim = root / 'victim.csv'
            victim.write_bytes(b'existing CSV\n')
            (inputs / 'SAFE.csv').symlink_to(victim)
            code, out, err = session.call('jdx_tool', ['convert', spectrum])
            self.assertNotEqual(code, 0)
            self.assertIn('outside', err)
            self.assertEqual(victim.read_bytes(), b'existing CSV\n')
