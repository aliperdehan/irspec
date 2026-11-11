"""Preview and session share QUANT-IR scale precedence."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from irspec import preview, session

DATA = Path(__file__).parent / "data"


class QuantirScale(unittest.TestCase):
    def test_both_options_use_peak_a_in_preview_and_session(self):
        source = (DATA / "phenacetin_quantir.jdx").resolve()
        with tempfile.TemporaryDirectory() as d:
            for scale in ({"peak_a": 1, "cl": 1}, {"cl": 1}, {"peak_a": 1}):
                entry = {"file": str(source), "name": "gas", **scale}
                r = session.process_jdx_reference(d, entry, d, d)
                x, y = session.read_plain(r["plain_path"])
                loaded = preview.load_ir(str(source), entry)
                np.testing.assert_allclose(loaded[0], x)
                np.testing.assert_allclose(loaded[1], y, rtol=0, atol=0.0001)
                if "peak_a" in scale:
                    self.assertAlmostEqual(min(loaded[1]), 10.)
