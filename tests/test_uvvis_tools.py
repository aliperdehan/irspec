"""irspec vspd and irspec vqud: the Shimadzu UV-Vis readers moved from nulabreport (tools/vspd_tool.py,
tools/parse_vqud.py). The expected outputs below are what nulabreport's own scripts wrote for the
same files (2026-11-11), so the move changed nothing; they were also run on the author's original,
un-anonymised files, with byte-identical output from both. The three files are the author's own
measurements, anonymised (tests/data/README.md says how).
"""
import contextlib
import csv
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, vqud_tool  # noqa: E402

DATA = ROOT / "tests" / "data"
VSPD = DATA / "uvvis.vspd"
QCA = DATA / "quant_510nm.vqud"
BLOCKS = DATA / "quant_540nm_blocks.vqud"

# sha256 of nulabreport's parse_vqud.py output for quant_510nm.vqud
QCA_SHA = {
    "calibration": "77287bb04ed0b6fe2e62b976255a5d9250d4fb2f4f310ddf2c812e1716c29f46",
    "sample_full": "40af103c74ad7fdec11e576963562c59112ef81d56b72ce9dae666b52338858f",
    "sample_summary": "f1a4f9eab3753bad1790591d36b1066eab8e1f988f3d940973985e3be8c4cbfe",
    "standard_full": "6becb92a76b1b4f62c5dba77d0d8ee822f3fd50e1c86944e69cc3aea6c12ef07",
    "standard_summary": "911d0366d91b25f353ced5e157701a6cbd5be4f60712a901c2b9caabce6cfffb",
}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main([str(a) for a in argv])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    return code, out.getvalue(), err.getvalue()


def text(path):
    with open(path, newline="") as f:
        return f.read()


class Vspd(unittest.TestCase):
    def test_convert_is_the_golden_csv(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "uv.csv"
            code, stdout, _ = run("vspd", "convert", VSPD, "--out", out)
            self.assertEqual(code, 0)
            self.assertIn("101 points, 200 -> 700 nm", stdout)
            self.assertEqual(out.read_bytes(), (DATA / "uvvis_golden.csv").read_bytes())

    def test_info_reads_the_scan_and_the_picks(self):
        code, out, _ = run("vspd", "info", VSPD)
        self.assertEqual(code, 0)
        self.assertIn("spectrum 1: 101 points, 200-700 nm, step 5 nm, stored descending, "
                      "y -0.0639 .. 4.8659", out)
        for line in ("pick Valley375.000: x=375  y=0.1248", "pick Peak255.000: x=255  y=4.8659",
                     "pick Peak510.000: x=510  y=0.3799"):
            self.assertIn(line, out)

    def test_peaks_are_the_stored_peak_picks(self):
        code, out, err = run("vspd", "peaks", VSPD)
        self.assertEqual((code, out), (0, "255/4.8659/5.1616/{},510/0.3799/0.6757/{}\n"))
        self.assertIn("ymax suggestion: 5.58", err)
        code, out, err = run("vspd", "peaks", VSPD, "--xmin", 300, "--xmax", 700)
        self.assertEqual(out, "510/0.3799/0.6458/{}\n")   # the label offset: 6% of the window's span


class Vqud(unittest.TestCase):
    def csvs(self, path):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d))
        code, out, _ = run("vqud", path, Path(d) / "q")
        self.assertEqual(code, 0)
        return Path(d), out

    def test_one_calibration_and_the_authors_unknown(self):
        d, out = self.csvs(QCA)
        for name, sha in QCA_SHA.items():
            with self.subTest(csv=name):
                self.assertEqual(hashlib.sha256((d / f"q_{name}.csv").read_bytes()).hexdigest(), sha)
        self.assertEqual(text(d / "q_sample_summary.csv"),
                         "Group,Sample Name,Type,Conc (mg/L),Absorbance (510nm)\r\n"
                         "2,Unknown 1,UNK-Avg,0.874,0.162\r\n")
        self.assertEqual(text(d / "q_calibration.csv"),
                         "Block,Points,K1 (mg/L per Abs),K0 (mg/L),r2,File K1,File K0,File fit agrees\r\n"
                         "1,6,5.16493,0.0373612,0.99838,5.16493,0.0373612,yes\r\n")
        self.assertIn("[file stores K1 5.16493, K0 0.0373612: agrees]", out)

    def test_an_older_file_with_a_modified_column_and_starred_rows(self):
        # WL540.0 Modified is the reading column; the removed groups read "*****" or "******"
        d, out = self.csvs(BLOCKS)
        with open(d / "q_standard_full.csv", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0][-1], "Absorbance (540nm)")
        self.assertEqual(len(rows) - 1, 28)
        self.assertEqual(sorted({int(r[0]) for r in rows[1:]}), list(range(41, 48)))
        self.assertEqual(text(d / "q_sample_summary.csv"),
                         "Group,Sample Name,Type,Conc (mg/L),Absorbance (540nm)\r\n"
                         "6,Unk 1,UNK-Avg,3.791,0.232\r\n")
        self.assertEqual(text(d / "q_calibration.csv"),
                         "Block,Points,K1 (mg/L per Abs),K0 (mg/L),r2,File K1,File K0,File fit agrees\r\n"
                         "1,7,18.3711,-0.264888,0.99441,0.0625624,-0.0054158,NO\r\n")
        self.assertIn("DIFFERS from this refit", out)

    def test_no_reading_is_empty_or_only_stars(self):
        for t in ("", "*****", "******"):
            self.assertFalse(vqud_tool.has_reading(t), t)
        for t in ("0.162", "-0.000", "*1*"):
            self.assertTrue(vqud_tool.has_reading(t), t)

    def test_info(self):
        code, out, _ = run("vqud", "info", QCA)
        self.assertEqual(code, 0)
        self.assertIn("stored calibration: concentration = 5.16493 * A + 0.0373612", out)
        self.assertIn("Sample Table: reading column WL510.0, 4 rows with a reading", out)
        self.assertIn("2-Avg  Unknown 1", out)


if __name__ == "__main__":
    unittest.main()
