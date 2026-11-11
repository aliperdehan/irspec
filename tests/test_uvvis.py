"""The UV-Vis kind in a session (kinds.UVVIS, uvvis.py), on the author's own scan
(tests/data/uvvis.vspd). The oracles: the peak list a figure gets is what `irspec vspd peaks`
(nulabreport's vspd_tool.py, unchanged) prints for the same window; the TeX figure is one page and
its frame is the one layout.py predicts from the measurements (docs/roadmap.md, item 6).
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
from irspec import cli, kinds, layout, session, texout, uvvis  # noqa: E402
from irspec.figure import read_figures  # noqa: E402

DATA = ROOT / "tests" / "data"
SCAN = DATA / "uvvis.vspd"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"


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


def uv_folder(d, loose=True):
    f = Path(d) / "lab_11-11"
    f.mkdir()
    if loose:
        shutil.copy(SCAN, f / "scan.vspd")
    else:
        (f / "uv").mkdir()
        shutil.copy(SCAN, f / "uv" / "scan.vspd")
    return f


def quiet_run(f, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return session.run(str(f), **kw)


def set_entry(f, **keys):
    mp = f / "manifest.json"
    entries = json.loads(mp.read_text(encoding="utf-8"))
    entries[0].update(keys)
    mp.write_text(json.dumps(entries), encoding="utf-8")


class Session(unittest.TestCase):
    def test_a_scan_is_filed_and_drawn_with_its_stored_picks(self):
        with tempfile.TemporaryDirectory() as d:
            f = uv_folder(d)
            figs = quiet_run(f, build="none")
            self.assertTrue((f / "uv" / "scan.vspd").exists())
            entry = json.loads((f / "manifest.json").read_text())[0]
            self.assertEqual((entry["kind"], entry["peaks"]), ("uvvis", [[255.0, 5.1616], [510.0, 0.6757]]))
            fig = figs[0]
            self.assertEqual((fig.kind, fig.axis, fig.ymax, fig.apex), ("uvvis", "Absorbance", 6.0, [4.8659, 0.3799]))
            # the oracle: what `irspec vspd peaks` prints for the whole scan
            code, out, err = run("vspd", "peaks", SCAN)
            self.assertEqual(fig.peaklist(), out.strip())
            self.assertIn("ymax suggestion: 5.58", err)
            self.assertEqual((f / "csv" / "scan.csv").read_bytes(), (DATA / "uvvis_golden.csv").read_bytes())
            self.assertEqual((f / "plain" / "scan.csv").read_bytes(), (DATA / "uvvis_golden.csv").read_bytes())
            md = next(f.glob("*.md")).read_text()
            self.assertIn("\\labplot\n  [kind=uvvis,width=\\linewidth,height=6.8in,ymax=6.0]\n"
                          "  {plain/scan.csv}\n  {255/4.8659/5.1616/{},510/0.3799/0.6757/{}}\n  {scan}\n", md)

    def test_a_crop_keeps_the_picks_inside_it(self):
        with tempfile.TemporaryDirectory() as d:
            f = uv_folder(d, loose=False)
            self.assertEqual(len(quiet_run(f, build="none")[0].peaks), 2)
            set_entry(f, xmin=300, xmax=700)
            entries = json.loads((f / "manifest.json").read_text())
            del entries[0]["peaks"]                     # take the stored picks again
            (f / "manifest.json").write_text(json.dumps(entries))
            fig = quiet_run(f, build="none")[0]
            code, out, err = run("vspd", "peaks", SCAN, "--xmin", 300, "--xmax", 700)
            self.assertEqual(fig.peaklist(), out.strip())
            self.assertEqual(fig.ymax, 5.0)  # session rounds upwards on the layout tick step

    def test_json_preview_and_a_mixed_folder(self):
        with tempfile.TemporaryDirectory() as d:
            f = uv_folder(d)
            code, out, err = run("session", f, "--preview", "--json")
            self.assertEqual(code, 0, err)
            obj = json.loads(out)
            self.assertEqual(obj["kind"], "uvvis")
            s = obj["spectra"][0]
            self.assertEqual((s["kind"], s["format"], s["will_be_filed_as"], s["plain"], s["xlim"]),
                             ("uvvis", "vspd", "uv/scan.vspd", "plain/scan.csv", [200.0, 700.0]))
            code, out, err = run("session", f, "--build", "none", "--json")
            self.assertEqual((code, json.loads(out)["kind"]), (0, "uvvis"))
            shutil.copy(DATA / SAMPLE, f / SAMPLE)
            code, out, err = run("session", f, "--build", "none", "--json")
            obj = json.loads(out)
            self.assertEqual(obj["kind"], "mixed")
            self.assertEqual(sorted(s["kind"] for s in obj["spectra"]), ["ir", "uvvis"])
            md = next(f.glob("*.md")).read_text()
            self.assertIn("\\irspectrum\n", md)
            self.assertIn("\\labplot\n  [kind=uvvis", md)

    def test_edit(self):
        with tempfile.TemporaryDirectory() as d:
            f = uv_folder(d)
            quiet_run(f, build="none")
            code, out, err = run("edit", f, "scan", "peak", "add", "300")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("`peak` edits IR spectra only so far; for a uvvis entry", err)
            code, out, err = run("edit", f, "scan", "set", "xmin=300", "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["kind"], "uvvis")
            code, out, err = run("edit", f, "scan", "set", "xmin=800")   # beyond the data: session says
            self.assertEqual(code, 0, err)
            code, out, err = run("session", f, "--build", "none")
            self.assertEqual(code, 1)
            self.assertIn("uv/scan.vspd: ", err)

    def test_preview_of_the_file(self):
        code, out, err = run("preview", SCAN, "--json")
        self.assertEqual(code, 0, err)
        obj = json.loads(out)
        self.assertEqual((obj["kind"], obj["format"], obj["axis"], obj["points"]), ("uvvis", "vspd", "Absorbance", 101))
        code, out, err = run("preview", SCAN, "--ascii", "--width", 90, "--height", 10)
        self.assertIn("Absorbance against wavelength (nm)", out)
        self.assertIn("range:   200 to 700 nm", out)

    def test_the_kind_is_the_measured_one(self):
        k = kinds.UVVIS
        self.assertEqual((k.xlim, k.x_descending, k.pad, k.y_scope, k.labels, k.macro),
                         (None, False, (0.0985, 0.0017), "frame", "apex", "labplot"))
        self.assertIs(kinds.for_path("uv/a.vspd"), k)
        self.assertEqual(session.filing_folder("A.VSPD"), "uv")


@unittest.skipUnless(shutil.which("lualatex"), "lualatex not installed")
class TexAgrees(unittest.TestCase):
    """A session of the scan is one page, and its frame is the one layout.frame predicts."""

    @classmethod
    def setUpClass(cls):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("pdfplumber not installed")

    def measure(self, bundled, **limits):
        import pdfplumber
        with tempfile.TemporaryDirectory() as d:
            f = uv_folder(d, loose=False)
            quiet_run(f, build="none")
            if limits:
                set_entry(f, **limits)
                quiet_run(f, build="none")
            figs, _ = read_figures(f / "figures.json")
            tex = texout.render_tex(figs)
            if bundled:   # what a machine without nulabreport gets
                tex = tex.replace("\\IfFileExists{nulabreport.sty}", "\\IfFileExists{no-nulabreport.sty}")
            (f / "t.tex").write_text(tex, encoding="utf-8")
            texout.write_excerpt(str(f))
            r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                               cwd=f, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-500:])
            with pdfplumber.open(f / "t.pdf") as pdf:
                pages = len(pdf.pages)
                pg = pdf.pages[0]
                fr = max(pg.rects, key=lambda q: q["width"] * q["height"])
                ws = pg.extract_words()

                def num(t):
                    t = t.replace("−", "-")
                    return float(t) if re.fullmatch(r"-?\d+(\.\d+)?", t) else None
                yl = [(num(w["text"]), (w["top"] + w["bottom"]) / 2) for w in ws
                      if num(w["text"]) is not None and 0 < fr["x0"] - w["x1"] < 15]
                a, b = np.polyfit([v for v, _ in yl], [c for _, c in yl], 1)
                frame_y = ((fr["bottom"] - b) / a, (fr["top"] - b) / a)
            return pages, frame_y, figs[0]

    def check(self, bundled, **limits):
        pages, (lo, hi), fig = self.measure(bundled, **limits)
        self.assertEqual(pages, 1)
        a = np.genfromtxt(DATA / "uvvis_golden.csv", delimiter=",", skip_header=1)
        _, want, _, _ = layout.frame(a[:, 0], a[:, 1], kinds.UVVIS, fig.xmin, fig.xmax, fig.ymin, fig.ymax)
        self.assertAlmostEqual(lo, want[0], delta=0.003)
        self.assertAlmostEqual(hi, want[1], delta=0.003)

    def test_whole_scan(self):
        self.check(False)

    def test_crop_with_the_bundled_excerpt(self):
        self.check(True, xmin=300, xmax=650)


if __name__ == "__main__":
    unittest.main()
