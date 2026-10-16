"""PNG/TIFF/SVG from the figure PDF: one file per spectrum, named after it, and
each format is what it says it is. Needs lualatex (to make the PDF), poppler,
and for the editable SVG mutool; each test is skipped without its tools.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from irspec import export, session  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
HAVE = {t: shutil.which(t) is not None for t in ("lualatex", "pdftoppm", "pdftocairo", "mutool")}


def make_session(d):
    folder = Path(d) / "s"
    (folder / "SPA").mkdir(parents=True)
    (folder / "jdx").mkdir()
    shutil.copy(DATA / "PHENACETIN_CRUDE_LR1-2.SPA", folder / "SPA")
    shutil.copy(DATA / "phenacetin_T.jdx", folder / "jdx")
    return folder


class Formats(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(export.parse_formats("png, svg,png"), ["png", "svg"])
        self.assertEqual(export.parse_formats(""), [])
        with self.assertRaises(SystemExit) as c:
            export.parse_formats("png,gif")
        self.assertIn("gif", str(c.exception))
        self.assertIn("svg-text", str(c.exception))

    def test_stems(self):
        from irspec.figure import Figure
        figs = [Figure("plain/A_plain.csv", "a"), Figure("plain/METHANOL.csv", "m")]
        self.assertEqual(export.stems_of(figs), ["A", "METHANOL"])


@unittest.skipUnless(all(HAVE[t] for t in ("lualatex", "pdftoppm", "pdftocairo")),
                     "needs lualatex and poppler")
class FromSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = make_session(cls.tmp.name)
        formats = ["png", "tiff", "svg"] + (["svg-text"] if HAVE["mutool"] else [])
        session.run(str(cls.folder), build="latex", formats=formats, dpi=100)
        cls.fig = cls.folder / "figures"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_one_file_per_spectrum_and_format(self):
        names = sorted(p.name for p in self.fig.iterdir())
        for stem in ("PHENACETIN_CRUDE_LR1-2", "phenacetin_T"):
            for suffix in (".png", ".tiff", ".svg"):
                self.assertIn(stem + suffix, names)

    def test_png_size_follows_dpi(self):
        from PIL import Image
        with Image.open(self.fig / "phenacetin_T.png") as im:
            self.assertEqual(im.size, (1170, 827))      # A4 landscape at 100 dpi

    def test_tiff_same_pixels_as_png_and_compressed(self):
        from PIL import Image
        import numpy as np
        a = np.array(Image.open(self.fig / "phenacetin_T.png").convert("RGB"))
        with Image.open(self.fig / "phenacetin_T.tiff") as t:
            self.assertEqual(t.info.get("compression"), "tiff_lzw")
            b = np.array(t.convert("RGB"))
        self.assertEqual(a.shape, b.shape)
        self.assertEqual(int((a != b).sum()), 0)

    def test_each_file_is_its_own_page(self):
        # page order = manifest order (time, then name): the SPA, then the .jdx
        pdf = str(self.folder / "ir_s.pdf")
        for page, stem in ((1, "PHENACETIN_CRUDE_LR1-2"), (2, "phenacetin_T")):
            ref = self.folder / f"ref{page}"
            subprocess.run(["pdftoppm", "-r", "100", "-f", str(page), "-l", str(page),
                            "-png", "-singlefile", pdf, str(ref)], check=True)
            self.assertEqual((self.fig / f"{stem}.png").read_bytes(),
                             Path(str(ref) + ".png").read_bytes())
        self.assertNotEqual((self.fig / "PHENACETIN_CRUDE_LR1-2.png").read_bytes(),
                            (self.fig / "phenacetin_T.png").read_bytes())

    def test_svg_is_xml_with_outlined_text(self):
        root = ET.parse(self.fig / "phenacetin_T.svg").getroot()
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(len([e for e in root.iter() if e.tag.endswith("}text")]), 0)

    @unittest.skipUnless(HAVE["mutool"], "needs mutool")
    def test_svg_text_keeps_text(self):
        root = ET.parse(self.fig / "phenacetin_T_text.svg").getroot()
        text = "".join("".join(e.itertext()) for e in root.iter() if e.tag.endswith("}text"))
        for s in ("4,000", "Wavenumber", "3253.3"):
            self.assertIn(s, text)

    def test_needs_the_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            folder = make_session(d)
            with self.assertRaises(SystemExit) as c:
                session.run(str(folder), build="none", formats=["png"])
            self.assertIn("PDF", str(c.exception))


if __name__ == "__main__":
    unittest.main()
