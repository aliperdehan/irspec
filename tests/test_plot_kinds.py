"""`irspec plot` draws the non-IR kinds a session makes: UV-Vis (the author's scan, tests/data/uvvis.vspd)
and GC (LR4's run, tests/data/gc_lab4.RAW, full and cropped). Labels stand above the band
(nulabreport's \\Lab@apexpeak). The oracle is the TeX figure: TEX_* below were measured with pdfplumber
on lualatex pages of these same sessions (texout.render_tex, full package and bundled excerpt alike),
2026-11-14, in bp, from the leaders' ends and the label characters' baselines. Each backend's own PDF
or SVG is measured the same way here.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import kinds, layout, session  # noqa: E402
from irspec.figure import read_figures  # noqa: E402

DATA = ROOT / "tests" / "data"
LR4 = {"file": "gc/gc_lab4.RAW", "title": "Group 1",
       "compounds": "2.84=Methanol,3.02=Ethanol,3.65=1-Propanol,5.31=1-Butanol,9.05=1-Pentanol",
       "solvent": "3.30=Acetone", "baseline": "2.5,4.5,6.6,8.0,8.5,8.97,9.6",
       "crop": {"xmin": 2.6, "xmax": 9.6, "correct": True, "exclude": "3.24-3.46"}}
GAP = (3.24, 3.46)            # the crop's excluded range: no trace across it

# Measured on the TeX figure: the bottom line's baseline above label_y (the leader's upper end),
# per label text; the name's baseline above the number's; the leader's gap above apex_y.
TEX_BASE = {"2.84": 1.287, "3.02": 1.298, "3.30": 1.292, "3.64": 1.296, "5.30": 1.295,
            "9.05": 1.301, "510": 1.298, "255": 1.298}
TEX_LINE = (9.455, 9.475)     # 9.46-9.47 on all eleven GC labels (\scriptsize's 9.5 pt = 9.4645 bp)
TEX_GAP = 1.494
TEX_LABEL_SIZE = 7.97         # \scriptsize; the backends use IR's 8 pt
TOL = 0.03


def sessions(d):
    """(uvvis folder, gc folder), each run through `irspec session`."""
    uv, gc = Path(d) / "uv_11-11", Path(d) / "gc_lab4"
    (uv / "uv").mkdir(parents=True)
    shutil.copy(DATA / "uvvis.vspd", uv / "uv" / "scan.vspd")
    (gc / "gc").mkdir(parents=True)
    shutil.copy(DATA / "gc_lab4.RAW", gc / "gc" / "gc_lab4.RAW")
    (gc / "manifest.json").write_text(json.dumps([LR4]), encoding="utf-8")
    for f in (uv, gc):
        with contextlib.redirect_stdout(io.StringIO()):
            session.run(str(f), build="none")
    return uv, gc


def frame_of(fig, folder):
    a = np.genfromtxt(Path(folder) / fig.csv, delimiter=",", skip_header=1)
    return layout.frame(a[:, 0], a[:, 1], kinds.get(fig.kind), fig.xmin, fig.xmax, fig.ymin, fig.ymax)[:2]


class Measured:
    """Label and frame checks on one backend's PDF page or SVG, given as plain numbers: `rows` is
    [(text, size, baseline y, centre x)] of the label lines (page y grows downwards), `leaders`
    [(x, upper y, lower y, width)] of the grey vertical lines, `frame` (x0, x1, top, bottom)."""

    def check_labels(self, fig, folder, rows, leaders, frame, size):
        (xl, xr), (lo, hi) = frame_of(fig, folder)
        x0, x1, top, bottom = frame
        X = lambda v: x0 + (v - xl) / (xr - xl) * (x1 - x0)          # noqa: E731
        Y = lambda v: bottom - (v - lo) / (hi - lo) * (bottom - top)   # noqa: E731
        labels = layout.apex_labels(fig)
        self.assertEqual(len(labels), len(fig.peaks))
        self.assertTrue(labels)
        for px, apex, ly, text, name in labels:
            # the leader: at x, from just above the apex up to label_y
            lead = [ld for ld in leaders if abs(ld[0] - X(px)) < 0.1]
            self.assertEqual(len(lead), 1, f"one leader at {text}")
            _, upper, lower, width = lead[0]
            self.assertAlmostEqual(upper, Y(ly), delta=0.05, msg=f"leader end at label_y, {text}")
            self.assertAlmostEqual(Y(apex) - lower, TEX_GAP, delta=TOL, msg=f"leader gap, {text}")
            self.assertAlmostEqual(width, layout.TICK_PT, delta=0.01)
            # the x value on the bottom line, the name above it, centred on x
            num = [r for r in rows if r[0] == text and abs(r[3] - X(px)) < 0.1]
            self.assertEqual(len(num), 1, f"the number {text} once, at its peak")
            self.assertAlmostEqual(upper - num[0][2], TEX_BASE[text], delta=TOL, msg=f"baseline of {text}")
            self.assertAlmostEqual(num[0][1], size, delta=0.01)
            if name:
                nm = [r for r in rows if r[0] == name and abs(r[3] - X(px)) < 0.1]
                self.assertEqual(len(nm), 1, f"the name {name} once, at its peak")
                self.assertTrue(TEX_LINE[0] - TOL <= num[0][2] - nm[0][2] <= TEX_LINE[1] + TOL,
                                f"{name} over {text}: {num[0][2] - nm[0][2]:.3f}")


def pdf_measure(path):
    """[(rows, leaders, frame, trace curves)] per page of a PDF, read with pdfplumber."""
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            def colour(c):
                c = c.get("stroking_color")
                return tuple(c) if isinstance(c, (list, tuple)) else (c,)
            leaders, trace = [], []
            for ln in pg.lines + pg.curves:
                pts = ln.get("pts") or []
                col = colour(ln)
                if len(pts) == 2 and abs(pts[0][0] - pts[1][0]) < 0.01 and abs(col[0] - 0.675) < 0.01:
                    leaders.append((pts[0][0], min(p[1] for p in pts), max(p[1] for p in pts),
                                    ln.get("linewidth")))
                elif len(pts) > 2 and len(col) == 3 and abs(col[0] - 0xB0 / 255) < 0.01:
                    trace.append(pts)
            byline = {}
            for c in pg.chars:
                if c["size"] < 9 and c["upright"]:
                    byline.setdefault(round(pg.height - c["matrix"][5], 2), []).append(c)
            rows = []
            for cs in byline.values():
                cs.sort(key=lambda c: c["x0"])
                # split one baseline into words where the gap is wide (two labels side by side)
                word = [cs[0]]
                for c in cs[1:] + [None]:
                    if c is not None and c["x0"] - word[-1]["x1"] < 2:
                        word.append(c)
                        continue
                    rows.append(("".join(w["text"] for w in word), word[0]["size"],
                                 pg.height - word[0]["matrix"][5],
                                 (word[0]["x0"] + word[-1]["x1"]) / 2))
                    word = [c] if c is not None else []
            page_area = pg.width * pg.height
            fr = max((r for r in pg.rects if r["width"] * r["height"] < 0.95 * page_area),
                     key=lambda r: r["width"] * r["height"])
            pages.append((rows, leaders, (fr["x0"], fr["x1"], fr["top"], fr["bottom"]), trace))
    return pages


class Matplotlib(Measured, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import matplotlib  # noqa: F401
            import pdfplumber  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("matplotlib or pdfplumber not installed")
        from irspec import mpl
        cls.mpl = mpl
        cls.tmp = tempfile.TemporaryDirectory()
        cls.uv, cls.gc = sessions(cls.tmp.name)
        cls.out = Path(cls.tmp.name) / "out"
        for f in (cls.uv, cls.gc):
            with contextlib.redirect_stdout(io.StringIO()):
                mpl.render(str(f), ["pdf", "svg-text"], str(cls.out / f.name), size=(10, 6.6))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def figures(self, folder):
        return read_figures(folder / "figures.json")[0]

    def test_labels_frame_and_gap_in_the_pdf(self):
        for folder in (self.uv, self.gc):
            figs = self.figures(folder)
            self.assertEqual([f.kind for f in figs], ["uvvis"] if folder is self.uv else ["gc", "gc"])
            for fig in figs:
                stem = Path(fig.csv).stem.replace("_plain", "")
                (rows, leaders, frame, trace), = pdf_measure(self.out / folder.name / f"{stem}.pdf")
                with self.subTest(fig.csv):
                    self.check_labels(fig, folder, rows, leaders, frame, layout.LABEL_PT)
                    # the frame is the axes box, whose limits are layout.frame's (test_frame)
                    if fig.csv.endswith("_crop.csv"):
                        (xl, xr), _ = frame_of(fig, folder)
                        X = lambda v: frame[0] + (v - xl) / (xr - xl) * (frame[1] - frame[0])  # noqa: E731
                        self.assertGreaterEqual(len(trace), 2, "the trace breaks at the excluded range")
                        inside = [p for c in trace for p in c if X(GAP[0] + 0.01) < p[0] < X(GAP[1] - 0.01)]
                        self.assertEqual(inside, [], "no trace point in the excluded range")
                    else:
                        self.assertEqual(len(trace), 1)

    def test_frame_ticks_and_titles(self):
        for folder in (self.uv, self.gc):
            for fig in self.figures(folder):
                out = self.mpl.draw(fig, str(folder))
                ax = out.axes[0]
                (xl, xr), (lo, hi) = frame_of(fig, folder)
                self.assertEqual(ax.get_xlim(), (xl, xr))
                self.assertEqual(ax.get_ylim(), (lo, hi))
                kind = kinds.get(fig.kind)
                self.assertEqual(ax.get_xlabel(), kind.x_label)
                self.assertEqual(ax.get_ylabel(), fig.axis)
                out.canvas.draw()
                ticks = [t.get_text() for t in ax.get_yticklabels()]
                if fig.kind == "gc":     # fixed point, a sixth of an em between thousands (TeX's \,)
                    self.assertIn("1\u2006100\u2006000" if fig.ymax > 1e6 else "80\u2006000", ticks)
                    self.assertFalse(any("," in t or "e" in t for t in ticks))
                    majors, minor = layout.x_ticks((xl, xr), kind)
                    self.assertAlmostEqual(minor, (majors[1] - majors[0]) / 2)   # minor x tick num=1
                else:
                    self.assertEqual(ticks[:2], ["0", "1"])
                self.assertEqual([t.get_text() for t in out.texts], [fig.title])

    def test_gap_is_in_the_drawn_line(self):
        fig = next(f for f in self.figures(self.gc) if f.csv.endswith("_crop.csv"))
        ax = self.mpl.draw(fig, str(self.gc)).axes[0]
        x, y = ax.lines[0].get_xdata(), ax.lines[0].get_ydata()
        inside = (x > GAP[0] + 0.01) & (x < GAP[1] - 0.01)
        self.assertTrue(inside.any())
        self.assertTrue(np.isnan(y[inside]).all())

    def test_svg_text_keeps_the_labels(self):
        svg = (self.out / self.gc.name / "gc_lab4_text.svg").read_text(encoding="utf-8")
        for word in ("Methanol", "2.84", "Acetone", "3.30", "Retention time / min", "FID signal / counts"):
            self.assertIn(word, svg)

    def test_fan_labels_are_still_refused(self):
        import dataclasses

        from irspec.export import ExportError
        fan = dataclasses.replace(kinds.UVVIS, name="fanned", labels="fan")
        fig = self.figures(self.uv)[0]
        fig.kind = "fanned"
        kinds.REGISTRY["fanned"] = fan
        try:
            with self.assertRaises(ExportError) as cm:
                self.mpl.draw(fig, str(self.uv))
        finally:
            del kinds.REGISTRY["fanned"]
        self.assertIn("a fanned figure's labels (fan) are not in yet", str(cm.exception.code))


class TexOracle(unittest.TestCase):
    """The TEX_* numbers hold for TeX's own figure today (lualatex and pdfplumber needed)."""

    @unittest.skipUnless(shutil.which("lualatex"), "lualatex not installed")
    def test_tex_figure_measures_as_recorded(self):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            self.skipTest("pdfplumber not installed")
        import subprocess

        from irspec import texout
        with tempfile.TemporaryDirectory() as d:
            for folder in sessions(d):
                figs = read_figures(folder / "figures.json")[0]
                tex = texout.render_tex(figs).replace(r"\IfFileExists{nulabreport.sty}",
                                                      r"\IfFileExists{no-nulabreport.sty}")
                (folder / "t.tex").write_text(tex, encoding="utf-8")
                texout.write_excerpt(str(folder))
                r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                                   cwd=folder, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout[-1500:])
                for fig, (rows, leaders, frame, _) in zip(figs, pdf_measure(folder / "t.pdf")):
                    for px, apex, ly, text, name in layout.apex_labels(fig):
                        lead = [ld for ld in leaders if any(abs(ld[0] - (row[3])) < 0.1
                                                            for row in rows if row[0] == text)]
                        self.assertEqual(len(lead), 1, text)
                        num = [row for row in rows if row[0] == text and abs(row[3] - lead[0][0]) < 0.1]
                        # pgfplots places a GC label to about 0.01 bp (its arithmetic on ~1e6 counts)
                        self.assertAlmostEqual(lead[0][1] - num[0][2], TEX_BASE[text], delta=0.015)
                        self.assertAlmostEqual(num[0][1], TEX_LABEL_SIZE, delta=0.01)
                        if name:
                            nm = [row for row in rows if row[0] == name and abs(row[3] - lead[0][0]) < 0.1]
                            self.assertTrue(TEX_LINE[0] <= num[0][2] - nm[0][2] <= TEX_LINE[1])


if __name__ == "__main__":
    unittest.main()
