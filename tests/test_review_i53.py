"""Flat automatic frames use the layout tick step."""
import unittest

import numpy as np
from irspec import kinds, layout, uvvis


class FlatUVVis(unittest.TestCase):
    def test_blank_and_constant_scans_have_finite_frames(self):
        x = np.array([400., 450., 500., 550.])
        for value in (0., 0.25, -0.25):
            y = np.full(4, value)
            got = uvvis.peaks_and_limits({"peaks": []}, x, y)
            _, limits, _, _ = layout.frame(x, y, kinds.UVVIS,
                                          ymin=got["ymin"], ymax=got["ymax"])
            step = layout.y_step(value, value)
            lower, upper = kinds.UVVIS.pad
            self.assertEqual(limits, (value - step - lower * 2 * step,
                                      value + step + upper * 2 * step))
            self.assertTrue(all(np.isfinite(limits)))
            self.assertLess(limits[0], value)
            self.assertGreater(limits[1], value)

    def test_explicit_conflicts_still_fail_and_one_auto_bound_can_expand(self):
        y = np.zeros(4)
        for low, high in ((0, 0), (1, 0)):
            with self.assertRaises(ValueError):
                layout.ylimits(y, low, high, kinds.UVVIS)
        self.assertGreater(layout.ylimits(y, ymin=0, kind=kinds.UVVIS)[1], 0)
        self.assertLess(layout.ylimits(y, ymax=0, kind=kinds.UVVIS)[0], 0)
