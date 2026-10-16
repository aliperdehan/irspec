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


def with_gas_manifest(f):
    (f / "manifest.json").write_text(json.dumps(
        [{"file": "jdx/1634-04-4-IR.jdx", "name": "PHENACETIN_GAS", "peak_a": 1}]))


class Folder(unittest.TestCase):
    """What a folder looks like after the run, and what the run leaves alone."""

    def test_running_twice_does_not_file_the_figure_list_away(self):
        with tempfile.TemporaryDirectory() as d:
            f = synthetic(d)
            with_gas_manifest(f)
            session.run(str(f), build="none")
            self.assertTrue((f / "figures.json").exists())
            session.run(str(f), build="none")
            self.assertTrue((f / "figures.json").exists())
            self.assertFalse((f / "other" / "figures.json").exists())

    def test_a_new_reference_entry_starts_with_a_readable_title(self):
        with tempfile.TemporaryDirectory() as d:
            f = synthetic(d)
            with_gas_manifest(f)
            session.run(str(f), build="none")
            titles = {e["file"]: e["title"] for e in json.loads((f / "manifest.json").read_text())}
            self.assertEqual(titles["jdx/62-44-2-IR.jdx"], "Phenacetin t")    # cas_names.json
            self.assertEqual(titles["jdx/1634-04-4-IR.jdx"], "Phenacetin gas")   # a hand-written entry too
            self.assertEqual(titles["SPA/PHENACETIN_CRUDE_LR1-2.SPA"], "PHENACETIN_CRUDE_LR1-2")

    def test_a_title_in_the_file_is_used_when_there_is_no_name(self):
        with tempfile.TemporaryDirectory() as d:
            f = synthetic(d)
            (f / "cas_names.json").unlink()
            self.assertEqual(session.default_title(str(f), "jdx/62-44-2-IR.jdx"), "Phenacetin crude (test fixture)")
            # an explicit --title always wins over both
            e = session.build_manifest(str(f), {"62-44-2-IR": "Mine"}, "name")
            self.assertEqual([x["title"] for x in e if x["file"] == "jdx/62-44-2-IR.jdx"], ["Mine"])

    def test_a_book_figure_s_printed_bands_become_the_peaks(self):
        """--palleros with --check: ir_digitize's own --peaklist is asked for, and what it prints is the
        peak list (the book's numbers, not the peak finder's). ir_digitize is replaced by a stub here:
        the figure itself is a textbook page and is not published (docs: README, 'Pictures')."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "book"
            (f / "img").mkdir(parents=True)
            (f / "img" / "fig.png").write_bytes(b"not a picture: the stub never opens it")
            (f / "manifest.json").write_text(json.dumps([{
                "file": "img/fig.png", "name": "BOOK_FIG", "check": "3027.1,1717.2",
                "args": ["--palleros", "--x-ticks", "3500,3000", "--y-ends", "72.7:24.5"]}]))
            seen = {}
            real = session.call

            def stub(module, argv):
                if module != "ir_digitize":
                    return real(module, argv)
                seen["argv"] = list(argv)
                out = argv[argv.index("--plain-out") + 1]
                Path(out).write_text("wavenumber,intensity\n3500,60\n3027,40\n2000,70\n1717,30\n650,65\n")
                Path(argv[argv.index("--out") + 1]).write_text("x\n")
                return 0, "  peaklist: 1717.2/29.9,3027.1/52.8\n", ""

            session.call = stub
            try:
                session.run(str(f), build="none")
            finally:
                session.call = real
            self.assertIn("--peaklist", seen["argv"])
            m = json.loads((f / "manifest.json").read_text())
            self.assertEqual(m[0]["peaks"], [[1717.2, 29.9], [3027.1, 52.8]])
            # and a hand-edited "peaks" is never replaced by the printed ones
            m[0]["peaks"] = [[3027.1, 55.0]]
            (f / "manifest.json").write_text(json.dumps(m))
            session.call = stub
            try:
                session.run(str(f), build="none")
            finally:
                session.call = real
            self.assertEqual(json.loads((f / "manifest.json").read_text())[0]["peaks"], [[3027.1, 55.0]])


class FilesAreClosed(unittest.TestCase):
    def test_reading_a_spa_leaves_no_open_file_behind(self):
        import gc
        import warnings
        from irspec import spa_peaks, spa_tool
        for reader in (spa_tool.read_spa, spa_peaks.read_spa):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                reader(str(DATA / "PHENACETIN_CRUDE_LR1-2.SPA"))
                gc.collect()
            self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [],
                             reader.__module__)


class PdfmdLookup(unittest.TestCase):
    def test_explicit_then_environment_then_path_and_nothing_personal(self):
        from irspec import ir_organize
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.py", Path(d) / "b.py"
            a.write_text(""); b.write_text("")
            old = os.environ.get("PDFMD")
            try:
                os.environ["PDFMD"] = str(b)
                self.assertEqual(ir_organize.find_pdfmd(str(a)), str(a))
                self.assertEqual(ir_organize.find_pdfmd(), str(b))
                os.environ["PDFMD"] = str(Path(d) / "missing.py")
                self.assertNotIn("dev/py", str(ir_organize.find_pdfmd() or ""))
            finally:
                os.environ.pop("PDFMD", None)
                if old is not None:
                    os.environ["PDFMD"] = old
        self.assertFalse(hasattr(ir_organize, "DEFAULT_PDFMD"))


class CommandLine(unittest.TestCase):
    def test_python_dash_m_irspec_runs_the_command(self):
        r = subprocess.run([sys.executable, "-m", "irspec", "--version"], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("irspec "))

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
