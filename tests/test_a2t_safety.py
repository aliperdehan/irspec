"""An in-place conversion must preserve its input when writing fails."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from irspec import absorbance_to_transmittance as a2t


class OutputSafety(unittest.TestCase):
    def test_negative_precision_leaves_in_place_input_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'spectrum.csv'
            original = b'wavenumber,intensity\n1000,1\n'
            path.write_bytes(original)
            result = subprocess.run(
                [sys.executable, '-m', 'irspec', 'a2t', str(path), '--out', str(path),
                 '--digits', '-1'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertIn('--digits must be non-negative', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            with self.assertRaisesRegex(ValueError, 'digits must be non-negative'):
                a2t.write_plain_csv(path, ['wavenumber', 'intensity'], ['1000'], [10], -1)
            self.assertEqual(path.read_bytes(), original)

    def test_formatting_failure_preserves_output_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'spectrum.csv'
            path.write_bytes(b'existing CSV\n')
            with self.assertRaises((ValueError, TypeError)):
                a2t.write_plain_csv(path, ['wavenumber', 'intensity'], ['1000'], [object()])
            self.assertEqual(path.read_bytes(), b'existing CSV\n')
            self.assertEqual(list(Path(d).iterdir()), [path])

    def test_zero_precision_in_place_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'spectrum.csv'
            path.write_text('wavenumber,intensity\n1000,1\n')
            header, rows = a2t.read_plain_csv(path)
            a2t.write_plain_csv(path, header, [wn for wn, _ in rows],
                                a2t.convert_series([y for _, y in rows]), digits=0)
            self.assertEqual(path.read_bytes(), b'wavenumber,intensity\r\n1000,10\r\n')
