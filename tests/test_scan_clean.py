"""Replay the original scan cleanup on synthetic pages and shadows."""

import contextlib
import io
import tempfile
import numpy as np
from PIL import Image
from irspec import scan_clean as sc

import json
from pathlib import Path
import unittest
from record_scan_clean import prepare
from tool_recording import replay

CASES = json.loads(
    (Path(__file__).parent / "data" / "scan_clean_expected.json").read_text(
        encoding="utf-8"
    )
)


class Recorded(unittest.TestCase):
    pass


def recorded_test(name):
    def test(self):
        replay(self, "scan", CASES, prepare, name)

    return test


for name in CASES:
    setattr(Recorded, "test_" + name, recorded_test(name))


def run(path_in, out_jpg, **kw):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        sc.process(str(path_in), None, str(out_jpg), **kw)
    return out.getvalue(), err.getvalue()


def page(w, h):
    a = np.full((h, w, 3), 245, np.uint8)
    a[h // 4 : h // 4 + 6, w // 8 : w - w // 8] = 20  # a rule of "ink"
    return a


class OrientationTests(unittest.TestCase):
    def test_exif_orientation_is_applied_to_the_pixels(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d, "p.jpg"), Path(d, "o.jpg")
            im = Image.fromarray(page(1200, 800))
            exif = Image.Exif()
            exif[0x0112] = 6  # displayed rotated 90 degrees clockwise
            im.save(src, "JPEG", exif=exif)
            run(src, out, min_paper_frac=0)
            with Image.open(out) as o:
                self.assertGreater(o.size[1], o.size[0])  # portrait, as displayed


class BudgetTests(unittest.TestCase):
    def test_unmet_budget_writes_the_smallest_and_warns(self):
        rng = np.random.default_rng(1)
        a = rng.integers(0, 256, (900, 1300, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d, "n.png"), Path(d, "o.jpg")
            Image.fromarray(a).save(src)
            stdout, stderr = run(src, out, target_kb=1, min_paper_frac=0)
            self.assertIn("budget", stderr)
            self.assertIn("1 KB", stderr)
            kb = out.stat().st_size / 1024
            self.assertIn(f"{kb:.0f}", stderr)
            with Image.open(out) as o:
                self.assertEqual(o.size[0], min(sc.JPEG_WIDTHS))

    def test_met_budget_has_no_warning(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d, "p.png"), Path(d, "o.jpg")
            Image.fromarray(page(1500, 1000)).save(src)
            _, stderr = run(src, out, min_paper_frac=0)
            self.assertNotIn("budget", stderr)


if __name__ == "__main__":
    unittest.main()
