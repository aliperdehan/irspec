"""Absorbance SPA session regression."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from irspec import edit, preview, session


class AbsorbanceSPA(unittest.TestCase):
    def test_session_converts_plain_and_peaks_but_keeps_archive(self):
        x = np.arange(700., 741., 10.)
        y = np.array([0., 1., 0., 0.5, 0.])
        with tempfile.TemporaryDirectory() as d, patch(
                "irspec.spa_tool.read_spa", return_value=(x, y)):
            entry = {"file": "SPA/sample.SPA"}
            result = session.process_ir(d, entry, str(Path(d) / "csv"), str(Path(d) / "plain"))
            xp, yp = session.read_plain(result["plain_path"])
            self.assertAlmostEqual(yp[xp == 710][0], 10.)
            self.assertEqual(result["axis_label"], "Transmittance %")
            self.assertEqual([p[0] for p in entry["peaks"]], [710., 730.])
            self.assertEqual(entry["peaks"][0][1], 5.)
            archive = Path(result["archival_path"]).read_text()
            self.assertIn("Absorbance", archive)
            self.assertIn("710,000;1,0000;", archive)
            loaded = preview.load_ir("sample.SPA", {})
            np.testing.assert_allclose(loaded[1], yp)
            self.assertEqual(loaded[2], result["axis_label"])
            saved = edit.load_saved_ir(d, entry)
            np.testing.assert_allclose(saved[1], yp)
            raw = Path(d) / entry["file"]
            raw.parent.mkdir()
            raw.touch()
            np.testing.assert_allclose(edit.load_saved_ir(d, entry)[1], 100 * 10. ** -y)
            raw.unlink()
            Path(result["plain_path"]).unlink()
            np.testing.assert_allclose(edit.load_saved_ir(d, entry)[1], 100 * 10. ** -y)
            self.assertEqual(saved[2:], ("Transmittance %", False))
