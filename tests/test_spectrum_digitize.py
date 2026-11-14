"""Replay the original spectrum digitizer on deterministic pictures."""

import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw
from irspec import spectrum_digitize as sd
from tool_recording import replay
from record_spectrum_digitize import prepare

ROOT = Path(__file__).resolve().parents[1]

CASES = json.loads(
    (Path(__file__).parent / "data" / "spectrum_digitize_expected.json").read_text(
        encoding="utf-8"
    )
)


class Recorded(unittest.TestCase):
    pass


def recorded_test(name):
    def test(self):
        replay(self, "spectrum", CASES, prepare, name)

    return test


for name in CASES:
    setattr(Recorded, "test_" + name, recorded_test(name))


class CalibrationTests(unittest.TestCase):
    def test_insufficient_ticks_raise_calibration_error(self):
        for ticks in ([], [(100, 5)]):
            with self.subTest(ticks=ticks):
                with self.assertRaisesRegex(sd.CalibrationError, r"need 2"):
                    sd.calibrate(ticks, "0:1", "test ruler", [])

    def test_missing_major_ticks_keep_detected_period(self):
        # Ten minor grid positions per labelled step; two majors are lost.
        ticks = [
            (100 + 8 * k, 15 if k % 10 == 0 else 5)
            for k in range(51)
            if k not in (20, 40)
        ]
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                a, b, majors, residual = sd.calibrate(
                    ticks, "200:-20", "test ruler", [], reverse=reverse
                )
                indices = np.array([0, 10, 30, 50])
                expected = 200 - 2 * (50 - indices if reverse else indices)
                np.testing.assert_allclose([v for _, v in majors], expected)
                np.testing.assert_allclose(
                    a * np.array([100, 500]) + b, [100, 200] if reverse else [200, 100]
                )
                self.assertAlmostEqual(residual, 0)

    def test_one_length_ticks_use_each_grid_position(self):
        ticks = [(100 + 8 * k, 5) for k in range(11) if k != 5]
        _, _, majors, _ = sd.calibrate(ticks, "0:1", "test ruler", [])
        np.testing.assert_allclose(
            [v for _, v in majors], [k for k in range(11) if k != 5]
        )


class NmrOutputTests(unittest.TestCase):
    def test_axis_limits_include_unlabelled_tallest_peak(self):
        for case in ("reference", "solvent", "figure", "separate"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                image = Image.new("L", (700, 400), 255)
                draw = ImageDraw.Draw(image)
                draw.line((75, 330, 625, 330), fill=0, width=2)
                for x in range(100, 601, 25):
                    draw.line(
                        (x, 330, x, 342 if (x - 100) % 50 == 0 else 335),
                        fill=0,
                        width=2,
                    )
                draw.line((80, 300, 620, 300), fill=0, width=2)
                draw.line((480, 300, 480, 260), fill=0, width=2)
                draw.line((600, 300, 600, 50), fill=0, width=2)
                options = []
                if case == "solvent":
                    options = ["--solvent", "0", "--solvent-style", "none"]
                if case in ("figure", "separate"):
                    draw.line((130, 160, 430, 160), fill=0, width=2)
                    for x in range(150, 401, 25):
                        draw.line(
                            (x, 160, x, 172 if (x - 150) % 50 == 0 else 165),
                            fill=0,
                            width=2,
                        )
                    draw.line((140, 130, 420, 130), fill=0, width=2)
                    draw.line((250, 130, 250, 20), fill=0, width=2)
                    draw.line((350, 130, 350, 100), fill=0, width=2)
                    options = [
                        "--inset",
                        "80:-2",
                        "--solvent",
                        "76",
                        "--solvent-style",
                        "none",
                        "--inset-layout",
                        case,
                    ]
                image.save(work / "input.png")
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "irspec",
                        "spectrum",
                        "nmr",
                        "input.png",
                        "--x-ticks",
                        "10:-1",
                        "--no-integrals",
                        "--out",
                        "trace.csv",
                        "--tex-out",
                        "plot.tex",
                        "--list-out",
                        "peaks.list",
                        *options,
                    ],
                    cwd=work,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                names = [""] + (["_inset1"] if options and case != "solvent" else [])
                for suffix in names:
                    with (work / f"trace{suffix}.csv").open(encoding="utf-8") as f:
                        tallest = max(
                            float(row["intensity"]) for row in csv.DictReader(f)
                        )
                    lines = (
                        (work / f"peaks{suffix}.list")
                        .read_text(encoding="utf-8")
                        .splitlines()
                    )
                    self.assertTrue(lines[1], "the smaller peak must have a label")
                    self.assertGreaterEqual(float(lines[0].split("=")[1]), tallest)
                limits = re.findall(
                    r"ymax=([\d.]+)", (work / "plot.tex").read_text(encoding="utf-8")
                )
                self.assertEqual(len(limits), len(names))
                self.assertTrue(all(float(v) >= 100 for v in limits), limits)


class MsOutputTests(unittest.TestCase):
    def test_no_x_ticks_reports_calibration_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            image = Image.new("L", (400, 300), 255)
            draw = ImageDraw.Draw(image)
            draw.line((30, 250, 380, 250), fill=0, width=2)
            draw.line((30, 20, 30, 250), fill=0, width=2)
            image.save(work / "axes.png")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "irspec",
                    "spectrum",
                    "ms",
                    "axes.png",
                    "--x-ticks",
                    "0:1",
                    "--y-ticks",
                    "0:20",
                    "--out",
                    "trace.csv",
                ],
                cwd=work,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("x (m/z)", result.stderr)
            self.assertIn("need 2", result.stderr)
            self.assertFalse((work / "trace.csv").exists())


if __name__ == "__main__":
    unittest.main()
