"""Automatic UV-Vis limits cover weak traces and labels."""
import unittest

import numpy as np
from irspec import kinds, layout, uvvis


class WeakUVVis(unittest.TestCase):
    def test_limits_round_up_at_the_data_step_at_every_scale(self):
        x = np.array([400., 500., 600.])
        for scale in (1e-6, 1e-3, 1., 1e3):
            y = np.array([1., 2., 1.]) * scale
            label = 2.1 * scale
            got = uvvis.peaks_and_limits({"peaks": [[500., label]]}, x, y)
            self.assertGreater(got["ymax"], max(y.max(), label))
            step = layout.y_step(y.min(), label)
            self.assertAlmostEqual(got["ymax"] / step, round(got["ymax"] / step))
            layout.frame(x, y, kinds.UVVIS, ymax=got["ymax"])
            explicit = uvvis.peaks_and_limits({"peaks": [[500., label]], "ymax": 3 * scale}, x, y)
            self.assertEqual(explicit["ymax"], 3 * scale)
