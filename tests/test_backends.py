"""figures.json, the shared geometry, and the matplotlib and R backends.

The y limits in MEASURED were read off the TeX figure (pdfplumber: frame and
tick-label positions) for the author's phenacetin spectrum and four more y
ranges made from it, so layout.py is held to what pgfplots actually draws.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import layout, mpl, plot, session  # noqa: E402
from irspec.figure import SPEC_VERSION, Figure, read_figures, write_figures  # noqa: E402

DATA = ROOT / "tests" / "data"
R_SCRIPT = ROOT / "src" / "irspec" / "data" / "irspec.R"

# (data min, data max, ymin, TeX frame bottom, TeX frame top), measured
MEASURED = [
    (44.45, 98.89, None, 39.09, 98.98),
    (44.45, 98.89, -5, -15.23, 99.06),
    (44.45, 98.89, -40, -53.67, 99.12),
    (44.45, 98.89, 0, -9.73, 99.05),
    (32.22, 59.44, None, 29.54, 59.49),
    (32.22, 59.44, -20, -27.82, 59.55),
]


def r_ready():
    if not shutil.which("Rscript"):
        return False
    r = subprocess.run(["Rscript", "-e", 'quit(status = !all(sapply(c("ggplot2","jsonlite"), '
                       "requireNamespace, quietly = TRUE)))"], capture_output=True)
    return r.returncode == 0


def make_session(d):
    f = Path(d) / "session_29-09"
    (f / "SPA").mkdir(parents=True)
    shutil.copy(DATA / "PHENACETIN_CRUDE_LR1-2.SPA", f / "SPA")
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        session.run(str(f), build="none", titles={"PHENACETIN_CRUDE_LR1-2": "Phenacetin 100% (crude)"})
    return f


class FigureFile(unittest.TestCase):
    def test_round_trip(self):
        f = Figure(csv="plain/a.csv", title="T", peaks=[(1700.0, 50.0), (3000.5, 80.0)], ymin=-5,
                   axis="Transmittance %", height="5in")
        self.assertEqual(Figure.from_entry(f.to_entry()), f)

    def test_written_by_session_with_plain_text(self):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d)
            raw = json.loads((f / "figures.json").read_text(encoding="utf-8"))
            self.assertEqual(raw[0]["spec"], SPEC_VERSION)
            # raw text, not LaTeX: the TeX writer escapes, the others must not see backslashes
            self.assertEqual(raw[0]["title"], "Phenacetin 100% (crude)")
            self.assertEqual(raw[0]["axis"], "Transmittance %")
            self.assertNotIn("\\", json.dumps(raw))
            figs, folder = read_figures(f / "figures.json")
            self.assertTrue((Path(folder) / figs[0].csv).exists())
            self.assertEqual(len(figs[0].peaks), 31)

    def test_other_spec_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "figures.json"
            p.write_text(json.dumps([{"spec": 99, "csv": "x.csv", "title": ""}]))
            with self.assertRaises(ValueError):
                read_figures(p)


class Layout(unittest.TestCase):
    def test_frame_matches_tex(self):
        for dmin, dmax, ymin, bot, top in MEASURED:
            lo, hi = layout.ylimits(np.array([dmin, dmax]), ymin)
            self.assertAlmostEqual(lo, bot, delta=0.05, msg=f"bottom for ymin={ymin}")
            self.assertAlmostEqual(hi, top, delta=0.05, msg=f"top for ymin={ymin}")

    def test_ticks_inside_and_few(self):
        for lo, hi in [(-15.2, 99.1), (39.1, 99.0), (-53.7, 99.1), (0.0, 1.2), (-0.02, 0.1)]:
            t = layout.y_ticks(lo, hi)
            self.assertTrue(all(lo - 1e-9 <= v <= hi + 1e-9 for v in t))
            self.assertLessEqual(len(t), layout.MAX_Y_INTERVALS + 1)
            self.assertGreaterEqual(len(t), 4)

    def test_number_format(self):
        self.assertEqual(layout.fmt_number(4000), "4,000")
        self.assertEqual(layout.fmt_number(-10), "−10")
        self.assertEqual(layout.fmt_number(0.5), "0.5")


class Matplotlib(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib not installed")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = make_session(cls.tmp.name)
        cls.figs, _ = read_figures(cls.folder / "figures.json")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_what_is_drawn(self):
        fig = self.figs[0]
        out = mpl.draw(fig, str(self.folder))
        ax = out.axes[0]
        x, y = layout.window(*mpl.read_plain(str(self.folder / fig.csv)))
        line = ax.lines[0]
        np.testing.assert_array_equal(line.get_xdata(), x)
        np.testing.assert_array_equal(line.get_ydata(), y)
        self.assertEqual(ax.get_xlim(), layout.XLIM)
        lo, hi = layout.ylimits(y, fig.ymin)
        self.assertAlmostEqual(ax.get_ylim()[0], lo)
        self.assertLessEqual(ax.get_ylim()[0], fig.ymin)
        labels = [t.get_text() for t in ax.texts]
        self.assertEqual(labels, [f"{px:.1f}" for px, _ in fig.peaks])
        self.assertEqual(len(ax.lines), 1 + len(fig.peaks))      # trace + one leader per peak
        for t, (px, ly) in zip(ax.texts, fig.peaks):
            self.assertEqual(t.get_position(), (px, ly))
            self.assertEqual(t.get_rotation(), 90)
        self.assertEqual(ax.get_xlabel(), "Wavenumber / cm⁻¹")
        self.assertEqual(ax.get_ylabel(), "Transmittance %")
        self.assertEqual([t.get_text() for t in out.texts], ["Phenacetin 100% (crude)"])

    def test_files(self):
        with tempfile.TemporaryDirectory() as d:
            paths = mpl.render(str(self.folder), ["png", "tiff", "pdf", "svg", "svg-text"], d,
                               size=(6, 4), dpi=100)
            names = sorted(os.path.basename(p) for p in paths)
            self.assertEqual(names, ["PHENACETIN_CRUDE_LR1-2.pdf", "PHENACETIN_CRUDE_LR1-2.png",
                                     "PHENACETIN_CRUDE_LR1-2.svg", "PHENACETIN_CRUDE_LR1-2.tiff",
                                     "PHENACETIN_CRUDE_LR1-2_text.svg"])
            from PIL import Image
            with Image.open(os.path.join(d, "PHENACETIN_CRUDE_LR1-2.png")) as im:
                png = im.convert("RGB")
            with Image.open(os.path.join(d, "PHENACETIN_CRUDE_LR1-2.tiff")) as im:
                tif, compression = im.convert("RGB"), im.info.get("compression")
            self.assertEqual(png.size, (600, 400))
            self.assertEqual(tif.size, (600, 400))
            self.assertEqual(compression, "tiff_lzw")
            self.assertTrue((np.asarray(png) == np.asarray(tif)).all())
            plain = Path(d, "PHENACETIN_CRUDE_LR1-2.svg").read_text(encoding="utf-8")
            text = Path(d, "PHENACETIN_CRUDE_LR1-2_text.svg").read_text(encoding="utf-8")
            self.assertNotIn("<text", plain)
            self.assertIn("<text", text)
            self.assertIn("Wavenumber", text.replace("</tspan>", "").replace("<tspan", " "))
            self.assertIn("3253.3", text)
            self.assertTrue(Path(d, "PHENACETIN_CRUDE_LR1-2.pdf").read_bytes().startswith(b"%PDF"))

    def test_no_caption_and_default_folder(self):
        out = mpl.draw(self.figs[0], str(self.folder), caption=False)
        self.assertEqual(out.texts, [])
        paths = mpl.render(str(self.folder / "figures.json"), ["png"], dpi=40)
        self.assertEqual(Path(paths[0]).parent, self.folder / "figures" / "matplotlib")

    def test_errors_are_messages(self):
        with self.assertRaises(SystemExit) as c:
            mpl.render(str(self.folder.parent / "nowhere"), ["png"])
        self.assertIn("irspec session", str(c.exception))
        with self.assertRaises(SystemExit):
            mpl.parse_size("big")


@unittest.skipUnless(r_ready(), "Rscript with ggplot2 and jsonlite not available")
class R(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = make_session(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_geometry_agrees_with_layout_py(self):
        r = subprocess.run(["Rscript", str(R_SCRIPT), str(self.folder), "--layout"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        lo, hi, ticks = r.stdout.split()
        figs, folder = read_figures(self.folder / "figures.json")
        x, y = layout.window(*mpl.read_plain(os.path.join(folder, figs[0].csv)))
        plo, phi = layout.ylimits(y, figs[0].ymin)
        self.assertAlmostEqual(float(lo), plo, places=8)
        self.assertAlmostEqual(float(hi), phi, places=8)
        self.assertEqual([float(v) for v in ticks.split(",")], layout.y_ticks(plo, phi))

    def test_files_through_the_plot_command(self):
        with tempfile.TemporaryDirectory() as d:
            plot.main([str(self.folder), "--backend", "r", "--formats", "png,svg,tiff",
                       "--dpi", "50", "--size", "6x4", "--out", d])
            from PIL import Image
            for name in ("PHENACETIN_CRUDE_LR1-2.png", "PHENACETIN_CRUDE_LR1-2.tiff"):
                with Image.open(os.path.join(d, name)) as im:
                    self.assertEqual(im.size, (300, 200), name)
            svg = Path(d, "PHENACETIN_CRUDE_LR1-2.svg").read_text(encoding="utf-8")
            self.assertIn("<text", svg)
            self.assertIn("3253.3", svg)
            self.assertIn("Phenacetin 100% (crude)", svg)

    def test_bad_format_is_a_message(self):
        r = subprocess.run(["Rscript", str(R_SCRIPT), str(self.folder), "--formats", "gif"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown format 'gif'", r.stderr)


class Dispatcher(unittest.TestCase):
    def test_r_script_is_packaged(self):
        self.assertEqual(Path(plot.r_script_path()), R_SCRIPT)
        self.assertTrue(R_SCRIPT.exists())


if __name__ == "__main__":
    unittest.main()
