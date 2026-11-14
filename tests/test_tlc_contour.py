"""Replay the original TLC output on synthetic images and vector PDF pages."""

import contextlib
import io
import os
import tempfile
import numpy as np
from irspec import tlc_contour as tlc

import json
from pathlib import Path
import shutil
import unittest
from record_tlc_contour import prepare
from tool_recording import replay

CASES = json.loads(
    (Path(__file__).parent / "data" / "tlc_contour_expected.json").read_text(
        encoding="utf-8"
    )
)


class Recorded(unittest.TestCase):
    pass


def recorded_test(name):
    def test(self):
        if name in ("pdf_all", "pdf_page") and not shutil.which("pdftoppm"):
            self.skipTest("PDF input needs pdftoppm")
        replay(self, "tlc", CASES, prepare, name)

    return test


for name in CASES:
    setattr(Recorded, "test_" + name, recorded_test(name))


def noise(h, w, seed=0):
    rng = np.random.default_rng(seed)
    return np.where(rng.random((h, w)) < 0.5, 0, 255).astype(np.uint8)


def png_width(path):
    from PIL import Image

    with Image.open(path) as im:
        return im.size[0]


class SaveTests(unittest.TestCase):
    def test_small_image_is_saved_at_its_own_width(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.png")
            width, kb = tlc.save_under_budget(np.full((300, 500), 255, np.uint8), out)
            self.assertEqual(width, 500)
            self.assertEqual(png_width(out), 500)

    def test_unattainable_budget_writes_the_smallest_candidate_and_warns(self):
        arr = noise(900, 700)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.png")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                width, kb = tlc.save_under_budget(arr, out, target_kb=1)
            self.assertEqual(width, min(tlc.WIDTHS))
            self.assertEqual(png_width(out), min(tlc.WIDTHS))
            self.assertAlmostEqual(os.path.getsize(out) / 1024, kb, delta=0.01)
            self.assertIn("budget", err.getvalue())
            self.assertIn(f"{kb:.1f} KB", err.getvalue())

    def test_a_met_budget_gives_no_warning(self):
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                tlc.save_under_budget(
                    np.full((300, 2000), 255, np.uint8), os.path.join(d, "o.png")
                )
            self.assertEqual(err.getvalue(), "")

    def test_pages_share_one_scale(self):
        from PIL import Image

        a = np.full((2708, 2550), 255, np.uint8)
        b = np.full((3300, 1879), 255, np.uint8)
        with tempfile.TemporaryDirectory() as d:
            pa, pb = os.path.join(d, "a.png"), os.path.join(d, "b.png")
            with contextlib.redirect_stdout(io.StringIO()):
                tlc.process_images([(Image.fromarray(a), pa), (Image.fromarray(b), pb)])
            wa, wb = png_width(pa), png_width(pb)
            self.assertEqual(wa, 1700)
            self.assertAlmostEqual(wb / wa, 1879 / 2550, delta=0.001)

    def test_shared_scale_shrinks_until_every_page_fits(self):
        from PIL import Image

        wide = np.full((800, 2000), 255, np.uint8)
        busy = noise(900, 1000)
        with tempfile.TemporaryDirectory() as d:
            pw, pb = os.path.join(d, "w.png"), os.path.join(d, "b.png")
            with contextlib.redirect_stdout(io.StringIO()):
                tlc.process_images(
                    [(Image.fromarray(wide), pw), (Image.fromarray(busy), pb)],
                    target_kb=60,
                    crop_mode="none",
                    bin_thresh=0.9,
                )
            self.assertAlmostEqual(
                png_width(pb) / png_width(pw), 1000 / 2000, delta=0.002
            )


if __name__ == "__main__":
    unittest.main()
