"""irspec session: a folder of spectra in, CSVs + peaks + figure out.

Synthetic session (the author's phenacetin as SPA and as three .jdx), plus
an oracle on the author's real LR6 reference folders when IRSPEC_LR6_IR points
at them (read-only; copied to a temp dir): `session` must make the same CSVs,
byte for byte, as the HOWTO recipes did by hand.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, session  # noqa: E402

DATA = ROOT / "tests" / "data"
LR6 = os.environ.get("IRSPEC_LR6_IR")


def synthetic(d):
    f = Path(d) / "session_29-09"
    (f / "SPA").mkdir(parents=True)
    (f / "jdx").mkdir()
    shutil.copy(DATA / "PHENACETIN_CRUDE_LR1-2.SPA", f / "SPA")
    shutil.copy(DATA / "phenacetin_T.jdx", f / "jdx" / "62-44-2-IR.jdx")
    shutil.copy(DATA / "phenacetin_A.jdx", f / "jdx" / "50-00-0-IR.jdx")
    shutil.copy(DATA / "phenacetin_quantir.jdx", f / "jdx" / "1634-04-4-IR.jdx")
    (f / "cas_names.json").write_text(json.dumps(
        {"62-44-2": "PHENACETIN_T", "50-00-0": "PHENACETIN_A"}))
    return f


class Synthetic(unittest.TestCase):
    def test_every_source_ends_as_percent_transmittance(self):
        with tempfile.TemporaryDirectory() as d:
            f = synthetic(d)
            (f / "manifest.json").write_text(json.dumps(
                [{"file": "jdx/1634-04-4-IR.jdx", "name": "PHENACETIN_GAS", "peak_a": 1}]))
            figs = session.run(str(f), build="none")
            self.assertEqual(len(figs), 4)
            self.assertTrue(all(g.axis == "Transmittance %" for g in figs))
            for rel in ("plain/PHENACETIN_T.csv", "plain/PHENACETIN_A.csv",
                        "plain/PHENACETIN_GAS.csv", "plain/PHENACETIN_CRUDE_LR1-2_plain.csv"):
                self.assertTrue((f / rel).exists(), rel)
            # the Absorbance copy, converted back, is the original %T to rounding:
            # A is written to 4 decimals (+-5e-5), and dT = T ln(10) dA reaches
            # 100 * 2.303 * 5e-5 = 0.0115 %T at T = 100
            ref = session.read_plain(str(f / "plain" / "PHENACETIN_T.csv"))[1]
            back = session.read_plain(str(f / "plain" / "PHENACETIN_A.csv"))[1]
            self.assertLess(abs(ref - back).max(), 0.02)
            md = (f / "ir_29-09.md").read_text()
            self.assertEqual(md.count("\\irspectrum\n"), 4)
            # the manifest now carries the names and the picked peaks
            m = json.loads((f / "manifest.json").read_text())
            self.assertTrue(all("peaks" in e for e in m))
            self.assertEqual(sorted(e["name"] for e in m if "name" in e),
                             ["PHENACETIN_A", "PHENACETIN_GAS", "PHENACETIN_T"])

    def test_a_quantir_file_without_peak_a_stops_with_instructions(self):
        with tempfile.TemporaryDirectory() as d:
            f = synthetic(d)
            with self.assertRaises(SystemExit) as cm:
                session.run(str(f), build="none")
            self.assertIn("peak_a", str(cm.exception))

    @unittest.skipUnless(shutil.which("lualatex") and shutil.which("pdfinfo"), "needs lualatex")
    def test_build_latex_makes_one_landscape_page_per_spectrum(self):
        with tempfile.TemporaryDirectory() as d:
            f = synthetic(d)
            (f / "manifest.json").write_text(json.dumps(
                [{"file": "jdx/1634-04-4-IR.jdx", "name": "PHENACETIN_GAS", "peak_a": 1}]))
            session.run(str(f), build="latex")
            info = subprocess.run(["pdfinfo", str(f / "ir_29-09.pdf")], capture_output=True,
                                  text=True).stdout
            self.assertIn("Pages:           4", info)
            self.assertIn("841.89 x 595.276", info)   # a wide page, not a rotated one


class CommandLine(unittest.TestCase):
    def test_version_and_unknown_command(self):
        r = subprocess.run([sys.executable, "-m", "irspec.cli", "--version"], capture_output=True,
                           text=True, env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
        self.assertRegex(r.stdout, r"^irspec 0\.\d+\.\d+")
        with self.assertRaises(SystemExit):
            cli.main(["nonsense"])

    def test_every_command_names_a_module_with_main(self):
        import importlib
        for cmd, mod in cli.COMMANDS.items():
            self.assertTrue(callable(importlib.import_module(f"irspec.{mod}").main), cmd)


@unittest.skipUnless(LR6 and Path(LR6).is_dir(), "set IRSPEC_LR6_IR to the author's LR6/ir folder")
class Lr6Oracle(unittest.TestCase):
    """Same bytes as the recipes made by hand (webbook/HOWTO.md, sdbs/HOWTO.md)."""

    def compare(self, src, dst, names, subdirs=("csv", "plain")):
        for n in names:
            for sd in subdirs:
                a, b = Path(src) / sd / f"{n}.csv", Path(dst) / sd / f"{n}.csv"
                self.assertEqual(b.read_bytes(), a.read_bytes(), f"{sd}/{n}.csv differs")

    def test_webbook(self):
        src = Path(LR6) / "webbook"
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "webbook"
            shutil.copytree(src / "jdx", f / "jdx")
            shutil.copy(src / "cas_names.json", f)
            (f / "manifest.json").write_text(json.dumps(
                [{"file": "jdx/1634-04-4-IR.jdx", "peak_a": 1}]))
            session.run(str(f), build="none")
            self.compare(src, f, ["METHANOL_GAS", "METHYL_CINNAMATE_GAS",
                                  "TERT_BUTYL_METHYL_ETHER_GAS"])

    def test_sdbs(self):
        src = Path(LR6) / "sdbs"
        names = {"140-10-3_IR1_2.jpg": "TRANS_CINNAMIC_ACID",
                 "140-10-3_IR2.gif": "TRANS_CINNAMIC_ACID_NUJOL",
                 "1634-04-4_IR2.gif": "TERT_BUTYL_METHYL_ETHER"}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "sdbs"
            shutil.copytree(src / "img", f / "img")
            (f / "manifest.json").write_text(json.dumps(
                [{"file": f"img/{k}", "name": v} for k, v in names.items()]))
            session.run(str(f), build="none")
            self.compare(src, f, names.values())
            for n in names.values():
                self.assertTrue((f / "check" / f"{n}.log").exists())
                self.assertEqual((f / "check" / f"{n}_overlay.png").read_bytes(),
                                 (src / "check" / f"{n}_overlay.png").read_bytes())


if __name__ == "__main__":
    unittest.main()
