"""Per-figure xmin, xmax and ymax: the manifest keys that crop the x axis and set the top of the y axis.

What the TeX figure does with them was MEASURED (pdfplumber on lualatex output, 2026-11-10); the
numbers below are those readings, so layout.py is held to pgfplots, not to itself. The TeX test
repeats the measurement and skips itself without lualatex or pdfplumber.
"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, edit, layout, mpl, preview, session, texout  # noqa: E402
from irspec.figure import Figure, read_figures  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
STEM = "PHENACETIN_CRUDE_LR1-2"
R_SCRIPT = ROOT / "src" / "irspec" / "data" / "irspec.R"

# (data min, data max, ymin, ymax, TeX frame bottom, TeX frame top), measured
MEASURED = [
    (44.45, 98.89, -5, 100, -15.33, 100.17),
    (44.45, 98.89, -5, 110, -16.32, 110.19),
    (44.45, 98.89, None, 110, 37.99, 110.10),
    (44.45, 98.89, 20, 105, 11.64, 105.14),
]


def make_session(d, **limits):
    f = Path(d) / "lab_29-09"
    (f / "SPA").mkdir(parents=True)
    shutil.copy(DATA / SAMPLE, f / "SPA")
    with contextlib.redirect_stdout(io.StringIO()):
        session.run(str(f), build="none")
    if limits:
        mp = f / "manifest.json"
        entries = json.loads(mp.read_text(encoding="utf-8"))
        entries[0].update(limits)
        mp.write_text(json.dumps(entries), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            session.run(str(f), build="none")
    return f


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main([str(a) for a in argv])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
            if isinstance(e.code, str):
                err.write(e.code + "\n")
    return code, out.getvalue(), err.getvalue()


class LayoutLimits(unittest.TestCase):
    def test_x_defaults_and_a_crop(self):
        self.assertEqual(layout.xlimits(), layout.XLIM)
        self.assertEqual(layout.xlimits(xmin=1000, xmax=3000), (3000.0, 1000.0))
        self.assertEqual(layout.xlimits(xmax=3000), (3000.0, 650.0))
        self.assertEqual(layout.xlimits(xmin=1000), (4000.0, 1000.0))

    def test_a_backwards_limit_is_refused(self):
        with self.assertRaises(ValueError):
            layout.xlimits(xmin=3000, xmax=1000)
        with self.assertRaises(ValueError):
            layout.ylimits(np.array([10.0, 50.0]), ymin=60)
        with self.assertRaises(ValueError):
            layout.ylimits(np.array([10.0, 50.0]), ymax=5)

    def test_frame_matches_tex_with_ymax(self):
        for dmin, dmax, ymin, ymax, bot, top in MEASURED:
            lo, hi = layout.ylimits(np.array([dmin, dmax]), ymin, ymax)
            self.assertAlmostEqual(lo, bot, delta=0.05, msg=f"bottom for ymin={ymin} ymax={ymax}")
            self.assertAlmostEqual(hi, top, delta=0.05, msg=f"top for ymin={ymin} ymax={ymax}")

    def test_without_ymax_nothing_changed(self):
        y = np.array([44.45, 98.89])
        self.assertEqual(layout.ylimits(y, -5), layout.ylimits(y, -5, None))


class FigureAndTex(unittest.TestCase):
    def test_round_trip_and_the_defaults_are_not_written(self):
        f = Figure(csv="a.csv", title="t", ymin=-5, ymax=100, xmin=1000, xmax=3000)
        self.assertEqual(Figure.from_entry(f.to_entry()), f)
        plain = Figure(csv="a.csv", title="t").to_entry()
        self.assertFalse({"ymax", "xmin", "xmax"} & set(plain))

    def test_the_tex_call_carries_them_as_pgfplots_keys(self):
        f = Figure(csv="a.csv", title="t", ymin=-5, ymax=100, xmin=1000, xmax=3000)
        self.assertIn("[width=\\linewidth,height=6.8in,ymin=-5,ymax=100,xmin=1000,xmax=3000]",
                      texout._block(f))
        self.assertIn("[width=\\linewidth,height=6.8in]", texout._block(Figure(csv="a", title="t")))

    def test_manifest_to_figures_json_to_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d, xmin=1000, xmax=3000, ymax=105)
            raw = json.loads((f / "figures.json").read_text(encoding="utf-8"))[0]
            self.assertEqual((raw["xmin"], raw["xmax"], raw["ymax"]), (1000, 3000, 105))
            md = (f / "ir_29-09.md").read_text(encoding="utf-8")
            self.assertIn("ymin=-5,ymax=105,xmin=1000,xmax=3000]", md)


class Matplotlib(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib not installed")

    def draw(self, **limits):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d, **limits)
            figs, folder = read_figures(f / "figures.json")
            out = mpl.draw(figs[0], folder)
            ax = out.axes[0]
            res = (ax.get_xlim(), ax.get_ylim(), len(ax.texts), len(ax.lines))
            ticks = [t for t in ax.get_xticks() if min(ax.get_xlim()) <= t <= max(ax.get_xlim())]
            import matplotlib.pyplot as plt
            plt.close(out)
            return res + (ticks,)

    def test_default_is_unchanged(self):
        xl, yl, labels, _, _ = self.draw()
        self.assertEqual(xl, layout.XLIM)
        self.assertEqual(labels, 31)

    def test_a_crop_and_ymax(self):
        xl, yl, labels, _, ticks = self.draw(xmin=1000, xmax=3000, ymax=105)
        self.assertEqual(xl, (3000.0, 1000.0))
        self.assertAlmostEqual(yl[1], 105 + layout.UPPER_PAD * (105 + 5), places=6)
        self.assertEqual(sorted(ticks), [1000, 1500, 2000, 2500, 3000])
        self.assertEqual(labels, 23)   # of the sample's 31 peaks, those inside 1000-3000: not
        #                                740.5 ... 969.1 (six) nor 3074.9 and 3253.3


class R(unittest.TestCase):
    def test_geometry_agrees_with_layout_py(self):
        from test_backends import r_ready
        if not r_ready():
            self.skipTest("Rscript with ggplot2 and jsonlite not installed")
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d, ymax=105, xmin=1000, xmax=3000)
            r = subprocess.run(["Rscript", str(R_SCRIPT), str(f), "--layout"], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            lo, hi, ticks = r.stdout.split()
            figs, folder = read_figures(f / "figures.json")
            x, y = layout.window(*mpl.read_plain(str(Path(folder) / figs[0].csv)))
            plo, phi = layout.ylimits(y, figs[0].ymin, figs[0].ymax)
            self.assertAlmostEqual(float(lo), plo, places=6)
            self.assertAlmostEqual(float(hi), phi, places=6)
            self.assertEqual([float(v) for v in ticks.split(",")], layout.y_ticks(plo, phi))


class Preview(unittest.TestCase):
    def test_json_has_the_frame(self):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d, xmin=1000, xmax=3000, ymax=105)
            code, out, _ = run("preview", f / "SPA" / SAMPLE, "--json")
            obj = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(obj["xlim"], [3000.0, 1000.0])
            self.assertAlmostEqual(obj["ylim"][1], 105 + layout.UPPER_PAD * 110, places=6)
            code, out, _ = run("preview", f / "SPA" / SAMPLE, "--ascii", "--width", "80")
            self.assertIn("ymax:    105", out)
            self.assertIn("x axis:  3000 to 1000 cm-1 (cropped)", out)
            axis = [ln for ln in out.splitlines() if "3,000" in ln][0]
            self.assertTrue(axis.split()[0] == "3,000" and axis.split()[-1] == "1,000", axis)
            self.assertNotIn("4,000", out)

    def test_the_trace_is_drawn_on_the_cropped_scale(self):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d, xmin=1000, xmax=3000, peaks=[])
            info = preview.work_out(str(f / "SPA" / SAMPLE))
            lines, _ = preview.draw(info, 80, 12, True)
        xw, yw, (lo, hi) = info["_xw"], info["_yw"], info["ylim"]
        start = lines[0].index("|") + 1
        cols = len(lines[12]) - start     # the axis line is the only one not stripped of its end
        dots = preview.trace_dots(xw, yw, cols, 12, lo, hi, tuple(info["xlim"]))
        for r in range(12):
            for c in range(cols):
                want = preview.cell_char(dots[r * 4:r * 4 + 4, c * 2:c * 2 + 2], True)
                got = lines[r][start + c] if start + c < len(lines[r]) else " "
                self.assertEqual(got, want, f"row {r} column {c}")

    def test_default_frame(self):
        code, out, _ = run("preview", DATA / SAMPLE, "--json")
        obj = json.loads(out)
        self.assertEqual(obj["xlim"], [4000.0, 650.0])
        self.assertNotIn("x axis:", run("preview", DATA / SAMPLE)[1])

    def test_a_backwards_entry_is_a_preview_error(self):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d)
            mp = f / "manifest.json"
            entries = json.loads(mp.read_text(encoding="utf-8"))
            entries[0].update(xmin=3000, xmax=1000)
            mp.write_text(json.dumps(entries), encoding="utf-8")
            code, out, err = run("preview", f / "SPA" / SAMPLE)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("must be below xmax", err)


class EditChecksLimits(unittest.TestCase):
    def test_set_refuses_a_backwards_pair_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d)
            before = (f / "manifest.json").read_bytes()
            for args in (["xmin=3000", "xmax=1000"], ["ymin=50", "ymax=10"], ["xmin=2000", "xmax=2000"]):
                code, out, err = run("edit", f, STEM, "set", *args)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("must be below", err)
                self.assertEqual((f / "manifest.json").read_bytes(), before)
            code, _, _ = run("edit", f, STEM, "set", "xmin=1000", "xmax=3000", "ymax=105")
            self.assertEqual(code, 0)
            code, _, err = run("edit", f, STEM, "set", "xmin=3500")   # against the stored xmax
            self.assertEqual(code, 2)


@unittest.skipUnless(shutil.which("lualatex"), "lualatex not installed")
class TexAgrees(unittest.TestCase):
    """The same measurement as the readings above, repeated: the frame and the x ticks of a crop."""

    @classmethod
    def setUpClass(cls):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("pdfplumber not installed")

    def measure(self, **limits):
        import pdfplumber
        with tempfile.TemporaryDirectory() as d:
            f = make_session(d, **limits)
            figs, _ = read_figures(f / "figures.json")
            (f / "t.tex").write_text(texout.render_tex(figs), encoding="utf-8")
            texout.write_excerpt(str(f))
            r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                               cwd=f, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-500:])
            with pdfplumber.open(f / "t.pdf") as pdf:
                pg = pdf.pages[0]
                fr = pg.rects[0]
                words = [w for w in pg.extract_words()
                         if re.fullmatch(r"\d+", w["text"]) and w["x1"] < fr["x0"]]
                v = np.array([float(w["text"]) for w in words])
                yc = np.array([(w["top"] + w["bottom"]) / 2 for w in words])
                a, b = np.polyfit(v, yc, 1)
                frame = ((fr["bottom"] - b) / a, (fr["top"] - b) / a)
                ticks = sorted({round(l["x0"], 1) for l in pg.lines
                                if abs(l["x0"] - l["x1"]) < 0.01 and abs(l["top"] - fr["bottom"]) < 0.6})
                x0, x1 = fr["x0"], fr["x1"]
            return frame, ticks, (x0, x1)

    def test_ymax_frame(self):
        (lo, hi), _, _ = self.measure(ymax=110)
        want = layout.ylimits(np.array([44.45, 98.89]), -5, 110)
        self.assertAlmostEqual(lo, want[0], delta=0.1)
        self.assertAlmostEqual(hi, want[1], delta=0.1)

    def test_crop_ticks(self):
        _, ticks, (x0, x1) = self.measure(xmin=950, xmax=2930)
        values = sorted(round(2930 - (px - x0) / (x1 - x0) * (2930 - 950)) for px in ticks)
        self.assertEqual(values, list(range(1000, 2901, 100)))


if __name__ == "__main__":
    unittest.main()
