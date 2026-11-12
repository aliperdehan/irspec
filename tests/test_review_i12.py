"""Correlation uses the requested grid only where both spectra were measured."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from irspec.ir_corr import corr


ROOT = Path(__file__).resolve().parent.parent


class CorrelationCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def write(self, name, x, y):
        np.savetxt(self.folder / name, np.column_stack((x, y)), delimiter=",",
                   header="wavenumber,intensity", comments="")

    def run_corr(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "irspec", "corr", *args], cwd=self.folder,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True,
        )

    def assert_rejected(self, result, *ranges):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"at least two grid points", result.stderr)
        self.assertIn(b"a.csv ~ b.csv", result.stderr)
        for measured in ranges:
            self.assertIn(measured.encode(), result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(b"NOTE:", result.stderr)

    def test_disjoint_ramps_rejected_by_cli_and_function(self):
        a = ([700., 1600.], [100., 0.])
        b = ([2400., 3900.], [100., 0.])
        self.write("a.csv", *a)
        self.write("b.csv", *b)
        self.assert_rejected(self.run_corr("a.csv", "b.csv"),
                             "[700, 1600]", "[2400, 3900]")
        with self.assertRaisesRegex(ValueError, "both measured ranges"):
            corr(a, b)

    def test_partial_overlap_uses_only_shared_grid_and_reports_range(self):
        a = ([700., 1000., 1400., 1800., 2200.], [10., 80., 20., 90., 30.])
        b = ([1200., 1400., 1600., 1800., 2400.], [90., 10., 60., 30., 80.])
        self.write("a.csv", *a)
        # CSVs may arrive in descending wavenumber order.
        self.write("b.csv", b[0][::-1], b[1][::-1])
        grid = np.arange(1200., 2201.)
        expected = np.corrcoef(np.interp(grid, *a), np.interp(grid, *b))[0, 1]
        result = self.run_corr("a.csv", "b.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"{expected:.4f}  a.csv  ~  b.csv\n".encode())
        self.assertEqual(result.stderr, b"NOTE: comparing only 1200 to 2200 cm-1 "
                         b"within both measured ranges\n")

    def test_restriction_preserves_requested_grid_alignment(self):
        a = ([750., 1000., 1255.], [10., 80., 20.])
        b = ([800., 1100., 1450.], [90., 10., 60.])
        self.write("a.csv", *a)
        self.write("b.csv", *b)
        grid = np.array([805., 905., 1005., 1105., 1205.])
        expected = np.corrcoef(np.interp(grid, *a), np.interp(grid, *b))[0, 1]
        result = self.run_corr("a.csv", "b.csv", "--lo", "705", "--hi", "2005",
                               "--step", "100")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"{expected:.4f}  a.csv  ~  b.csv\n".encode())
        self.assertEqual(result.stderr, b"NOTE: comparing only 805 to 1205 cm-1 "
                         b"within both measured ranges\n")

    def test_overlap_with_zero_or_one_grid_points_is_rejected(self):
        for a_lo, b_lo in ((700., 700.1), (700., 700.)):
            with self.subTest(a_lo=a_lo, b_lo=b_lo):
                self.write("a.csv", [a_lo, 700.8], [100., 0.])
                self.write("b.csv", [b_lo, 700.9], [100., 0.])
                self.assert_rejected(self.run_corr("a.csv", "b.csv"),
                                     "[700, 700.8]", f"[{b_lo:g}, 700.9]")

    def test_requested_grid_outside_shared_coverage_is_rejected(self):
        self.write("a.csv", [700., 1600.], [100., 0.])
        self.write("b.csv", [800., 1700.], [100., 0.])
        self.assert_rejected(self.run_corr("a.csv", "b.csv", "--lo", "3000",
                                          "--hi", "3100"),
                             "[700, 1600]", "[800, 1700]")

    def test_two_shared_grid_points_suffice(self):
        self.write("a.csv", [700., 701.], [100., 0.])
        self.write("b.csv", [700., 701.], [50., 0.])
        result = self.run_corr("a.csv", "b.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"1.0000  a.csv  ~  b.csv\n")
        self.assertEqual(result.stderr.count(b"NOTE:"), 1)
        self.assertIn(b"700 to 701 cm-1", result.stderr)

    def test_full_coverage_keeps_legacy_stdout_byte_for_byte(self):
        a = ([600., 1500., 2500., 4000.], [20., 80., 30., 90.])
        b = ([600., 1800., 2700., 4000.], [90., 20., 70., 40.])
        self.write("a.csv", *a)
        self.write("b.csv", *b)
        for lo, hi, step in ((700., 3900., 1.), (705., 2005., 100.),
                             (700., 3900., 7.)):
            with self.subTest(lo=lo, hi=hi, step=step):
                # The original algorithm, including its arange endpoint rule.
                grid = np.arange(lo, hi + step / 2, step)
                legacy = np.corrcoef(np.interp(grid, *a), np.interp(grid, *b))[0, 1]
                result = self.run_corr("a.csv", "b.csv", "--lo", str(lo),
                                       "--hi", str(hi), "--step", str(step))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"{legacy:.4f}  a.csv  ~  b.csv\n".encode())
                self.assertEqual(result.stderr, b"")

    def test_later_disjoint_spectrum_prints_no_correlations(self):
        self.write("a.csv", [700., 1600.], [100., 0.])
        self.write("b.csv", [2400., 3900.], [100., 0.])
        result = self.run_corr("a.csv", "a.csv", "b.csv")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"[700, 1600] and [2400, 3900]", result.stderr)
