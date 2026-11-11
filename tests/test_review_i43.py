"""Clipping keeps previews bounded even for extremely tight crops."""
import os
import subprocess
import sys
import unittest

import numpy as np
from irspec import preview


class Clipping(unittest.TestCase):
    def test_crossing_and_outside_segments(self):
        dots = np.zeros((5, 7), dtype=bool)
        preview._line(dots, -1000000000, 2, 1000000000, 2)
        self.assertTrue(dots[2].all())
        self.assertEqual(dots.sum(), 7)
        preview._line(dots, -1000000000, -1, 1000000000, -1)
        self.assertEqual(dots.sum(), 7)
        dots[:] = False
        preview._line(dots, -2, -2, 6, 6)
        self.assertTrue(all(dots[i, i] for i in range(5)))

    def test_fixture_tight_crop_finishes(self):
        script = """from irspec import preview, spa_tool
x, y = spa_tool.read_spa('tests/data/PHENACETIN_CRUDE_LR1-2.SPA')
dots = preview.trace_dots(x, y, 80, 8, 0, 100, (1720.00001, 1720))
assert dots.any()
"""
        result = subprocess.run([sys.executable, "-c", script], env=dict(os.environ, PYTHONPATH="src"),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
