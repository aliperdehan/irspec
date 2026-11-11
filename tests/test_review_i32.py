"""SPA absorbance bands point upwards."""
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from irspec import session, spa_tool


class AbsorbancePicking(unittest.TestCase):
    def test_convert_and_batch_pick_bands_and_put_labels_above(self):
        x = np.arange(650., 751.)
        y = np.exp(-((x - 680) / 5)**2) + np.exp(-((x - 720) / 5)**2)
        with tempfile.TemporaryDirectory() as d, patch(
                "irspec.spa_tool.read_spa", return_value=(x, y)):
            for axis in (None, "Absorbance"):
                entry = {"spa": "sample.SPA", "prominence": 0.1}
                if axis:
                    entry["axis"] = axis
                r = spa_tool.process_entry(entry, d, d)
                self.assertEqual(r["n_peaks"], 2)
                pairs = [list(map(float, p.split("/"))) for p in r["peaklist"].split(",")]
                self.assertEqual([p[0] for p in pairs], [680., 720.])
                self.assertTrue(all(p[1] > 1 for p in pairs))
            code, out, err = session.call("spa_tool", ["convert", "sample.SPA", "--out", d + "/s",
                                                     "--prominence", "0.1"])
            self.assertEqual(code, 0, err)
            self.assertIn("680.0000/6.0,720.0000/11.0", out)
