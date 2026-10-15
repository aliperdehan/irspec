"""TeX output: render_md must equal what ir_organize wrote before irspec
existed; render_tex must build with lualatex, and the two ways it can build (the
real nulabreport.sty, or the bundled excerpt) must draw the same page.

The build tests need lualatex and STIX Two; they are skipped without them, and
the excerpt one also needs nulabreport.sty installed (to compare against).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from irspec import ir_organize, texout  # noqa: E402
from irspec.figure import Figure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data"
HAVE_LUALATEX = shutil.which("lualatex") is not None
HAVE_STIX = shutil.which("fc-list") and "STIX Two Text" in subprocess.run(
    ["fc-list"], capture_output=True, text=True).stdout


def session(d):
    """A session folder with the author's SPA and the T .jdx, processed the way
    `ir_organize --no-pdf` does; returns (folder, results)."""
    folder = Path(d) / "session_29-09"
    folder.mkdir()
    shutil.copy(DATA / "PHENACETIN_CRUDE_LR1-2.SPA", folder)
    shutil.copy(DATA / "phenacetin_T.jdx", folder / "62-44-2-IR.jdx")
    ir_organize.organize(str(folder), False)
    entries = ir_organize.build_manifest(str(folder), {}, "name")
    csv_dir, plain_dir = folder / "csv", folder / "plain"
    csv_dir.mkdir(exist_ok=True)
    plain_dir.mkdir(exist_ok=True)
    results = []
    for e in entries:
        path = str(folder / e["file"])
        proc = ir_organize.process_spa if path.lower().endswith(ir_organize.SPA_EXT) \
            else ir_organize.process_jdx
        results.append(proc(path, e, str(csv_dir), str(plain_dir)))
    return folder, results


class RenderMd(unittest.TestCase):
    def test_equals_ir_organize_render_md(self):
        with tempfile.TemporaryDirectory() as d:
            folder, results = session(d)
            old = ir_organize.render_md(results, str(folder))
            figs = [Figure.from_organize_result(r, str(folder)) for r in results]
            self.assertEqual(texout.render_md(figs), old)

    def test_entry_round_trip(self):
        f = Figure(csv="plain/x.csv", title="Methanol", axis="Absorbance",
                   peaks=[(3316.0, 76.3), (1022.1, 26.8)], ymin=20)
        self.assertEqual(Figure.from_entry(f.to_entry()), f)
        self.assertEqual(f.peaklist(), "3316.0/76.3,1022.1/26.8")


def build(tex_dir, env=None):
    r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "fig.tex"],
                       cwd=tex_dir, capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    log = (Path(tex_dir) / "fig.log").read_text(errors="replace")
    return r.returncode, log


def raster(pdf, out_prefix):
    subprocess.run(["pdftoppm", "-r", "100", "-png", str(pdf), str(out_prefix)], check=True)
    return Path(f"{out_prefix}-1.png")


@unittest.skipUnless(HAVE_LUALATEX and HAVE_STIX, "needs lualatex and STIX Two Text")
class RenderTex(unittest.TestCase):
    def make(self, d, name):
        wd = Path(d) / name
        wd.mkdir()
        (wd / "plain").mkdir()
        shutil.copy(DATA / "golden_plain.csv", wd / "plain" / "p.csv")
        fig = Figure(csv="plain/p.csv", title="Phenacetin (crude)",
                     peaks=[(1241.9, 40.0), (1511.0, 55.0), (2980.0, 90.0)], ymin=20)
        (wd / "fig.tex").write_text(texout.render_tex([fig]), encoding="utf-8")
        texout.write_excerpt(str(wd))
        return wd

    def test_full_package_and_excerpt_draw_the_same_page(self):
        from PIL import Image, ImageChops
        import numpy as np
        if not subprocess.run(["kpsewhich", "nulabreport.sty"], capture_output=True,
                              text=True).stdout.strip():
            self.skipTest("nulabreport.sty is not installed")
        with tempfile.TemporaryDirectory() as d:
            a = self.make(d, "full")
            rc, log = build(a)
            self.assertEqual(rc, 0, log[-600:])
            self.assertIn("nulabreport", log)
            self.assertNotIn("Using the bundled excerpt", log)
            b = self.make(d, "excerpt")
            empty = Path(d) / "empty-texmfhome"
            empty.mkdir()
            rc, log = build(b, {"TEXMFHOME": str(empty)})
            self.assertEqual(rc, 0, log[-600:])
            self.assertIn("Using the bundled excerpt", log)
            pa = Image.open(raster(a / "fig.pdf", Path(d) / "a")).convert("L")
            pb = Image.open(raster(b / "fig.pdf", Path(d) / "b")).convert("L")
            self.assertEqual(pa.size, pb.size)
            diff = int((np.array(ImageChops.difference(pa, pb)) > 0).sum())
            self.assertEqual(diff, 0, f"{diff} pixels differ between full package and excerpt")


if __name__ == "__main__":
    unittest.main()
