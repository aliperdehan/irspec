"""QUANT-IR units come from the decoder, irrespective of header layout."""
import tempfile
import unittest
from pathlib import Path

from irspec import session

DATA = Path(__file__).parent / 'data'


class ParsedUnits(unittest.TestCase):
    def test_quantir_header_variants_require_scale_and_convert_identically(self):
        original = (DATA / 'phenacetin_quantir.jdx').read_text()
        unit_line = next(line for line in original.splitlines() if line.startswith('##YUNITS='))
        variants = {
            'standard': original,
            'spaced': original.replace('##YUNITS=', '##YUNITS ='),
            # Beyond the former 20,000-character scan, still inside the JCAMP header.
            'late': original.replace(unit_line + '\n', '').replace(
                '##XYDATA=', '##COMMENT=' + 'x' * 20001 + '\n' + unit_line + '\n##XYDATA='),
        }
        outputs = []
        with tempfile.TemporaryDirectory() as d:
            for label, text in variants.items():
                with self.subTest(header=label):
                    folder = Path(d) / label
                    (folder / 'jdx').mkdir(parents=True)
                    path = folder / 'jdx' / 'sample.jdx'
                    path.write_text(text)
                    csv, plain = folder / 'csv', folder / 'plain'
                    csv.mkdir(); plain.mkdir()
                    entry = {'file': 'jdx/sample.jdx', 'name': 'SAMPLE'}
                    with self.assertRaisesRegex(session.SessionError, 'peak_a.*cl'):
                        session.process_jdx_reference(str(folder), entry, str(csv), str(plain))
                    self.assertEqual(list(csv.iterdir()), [])
                    self.assertEqual(list(plain.iterdir()), [])
                    for scale in ({'peak_a': 1}, {'cl': 10}):
                        session.process_jdx_reference(str(folder), {**entry, **scale},
                                                      str(csv), str(plain))
                        outputs.append((scale, (csv / 'SAMPLE.csv').read_bytes(),
                                        (plain / 'SAMPLE.csv').read_bytes()))
            self.assertTrue(outputs[:2] == outputs[2:4], "spaced header changed CSV bytes")
            self.assertTrue(outputs[:2] == outputs[4:], "late units changed CSV bytes")

    def test_true_absorbance_and_transmittance_keep_their_kind(self):
        for fixture, kind in [('phenacetin_A.jdx', 'absorbance'),
                              ('phenacetin_T.jdx', 'transmittance')]:
            with self.subTest(kind=kind):
                self.assertEqual(session._jdx_kind(DATA / fixture), kind)

    def test_absorptivity_converter_uses_units_not_a_comment(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'sample.jdx'
            path.write_text((DATA / 'phenacetin_A.jdx').read_text().replace(
                '##XYDATA=', '##COMMENT=(MICROMOL/MOL)-1M-1\n##XYDATA='))
            code, out, err = session.call('absorptivity_to_absorbance', [
                path, '--name', 'SAMPLE', '--out', Path(d) / 'a.csv',
                '--plain-out', Path(d) / 'p.csv', '--peak-a', '1'])
            self.assertNotEqual(code, 0)
            self.assertIn('y-units are not', err)
            self.assertFalse((Path(d) / 'a.csv').exists())
