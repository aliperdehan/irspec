"""Manual requests select the nearest local band, not a neighbour's slope."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from irspec import session


class ManualPicking(unittest.TestCase):
    def test_cli_uses_nearest_band_for_both_axes_and_directions(self):
        x = np.arange(960., 1061.)
        dips = 5 * np.exp(-((x - 1000) / 3)**2) + 50 * np.exp(-((x - 1019) / 8)**2)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.csv"
            for absorbance in (False, True):
                y = dips if absorbance else 100 - dips
                for reverse in (False, True):
                    data = np.column_stack((x, y))
                    np.savetxt(p, data[::-1] if reverse else data, delimiter=",",
                               header="wavenumber,intensity", comments="")
                    args = [str(p), "--mode", "manual", "--peaks", "1002", "--json"]
                    if absorbance:
                        args += ["--axis", "Absorbance"]
                    code, out, err = session.call("spa_peaks", args)
                    self.assertEqual(code, 0, err)
                    obj = json.loads(out)
                    self.assertEqual(obj["peaks"][0][0], 1000.)
