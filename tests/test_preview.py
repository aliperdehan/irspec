"""irspec preview FILE: one spectrum as plain text."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, layout, preview  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
SMALL = ("--width", "56", "--height", "8", "--ascii")

GOLDEN_SPA = """\
PHENACETIN_CRUDE_LR1-2.SPA  --  Transmittance % against wavenumber (cm-1)

    |*********:........:***::**:::::::**|:   .:  . ..
 90 |          ** *****            Q    ||..|||:||||||.*
    |           V  UTSR                 |N||**||*|**|||
 50 |                                   P *KIG*BA*75||1
    |                                   O MJHFD 986 43
 20 |                                     L  EC      2
    |
-10 |
    ++------+-------+------+-------+------+-------+-----
     4,000        3,000  2,500   2,000  1,500        650

file:    PHENACETIN_CRUDE_LR1-2.SPA
axis:    Transmittance %
points:  3734 (3474 between 650 and 4000 cm-1)
range:   3999.64 to 400.157 cm-1; intensity 44.45 to 98.89
ymin:    -5
peaks:   31 (picked automatically); wavenumber/label height
  1 740.5/52.3   2 784.9/47.3   3 825.4/39.4
  4 837.0/34.4   5 923.7/62.5   6 969.1/71.0
  7 1013.4/59.7  8 1045.2/49.4  9 1106.9/58.7
  A 1116.6/53.7  B 1174.4/53.8  C 1241.9/47.3
  D 1265.1/42.3  E 1305.6/37.3  F 1324.9/32.3
  G 1362.5/27.3  H 1392.4/22.3  I 1411.6/17.3
  J 1446.4/12.3  K 1480.1/7.3   L 1505.2/2.3
  M 1551.5/59.1  N 1604.5/69.5  O 1644.0/56.5
  P 1656.6/51.5  Q 2018.1/86.9  R 2848.3/77.1
  S 2917.8/72.4  T 2982.4/76.3  U 3074.9/80.9
  V 3253.3/75.3
"""

GOLDEN_JDX_T = """\
phenacetin_T.jdx  --  Transmittance % against wavenumber (cm-1)

    |*********:........:***::**:::::::*||:   .:  . ..
 90 |          ********            Q    ||..|||:||||||.|
    |           V  UTSR                 |N||**||*|**|||
 50 |                                   P *KIG*BA*75||1
    |                                   O MJHFD 986 43
 20 |                                     L  EC      2
    |
-10 |
    ++------+-------+------+-------+------+-------+-----
     4,000        3,000  2,500   2,000  1,500        650

file:    phenacetin_T.jdx
axis:    Transmittance %
points:  3474 (3474 between 650 and 4000 cm-1)
range:   3999.64 to 650.857 cm-1; intensity 44.45 to 98.89
ymin:    -5
peaks:   31 (picked automatically); wavenumber/label height
  1 740.5/52.3   2 784.9/47.3   3 825.4/39.4
  4 837.0/34.4   5 923.7/62.5   6 969.1/71.0
  7 1013.4/59.7  8 1045.2/49.4  9 1106.9/58.7
  A 1116.6/53.7  B 1174.4/53.8  C 1241.9/47.3
  D 1265.1/42.3  E 1305.6/37.3  F 1324.9/32.3
  G 1362.5/27.3  H 1392.4/22.3  I 1411.6/17.3
  J 1446.3/12.3  K 1480.1/7.3   L 1505.2/2.3
  M 1551.5/59.1  N 1604.5/69.5  O 1644.0/56.5
  P 1656.6/51.5  Q 2018.1/86.9  R 2848.3/77.1
  S 2917.8/72.4  T 2982.4/76.3  U 3074.9/80.9
  V 3253.3/75.3
"""

GOLDEN_JDX_A = """\
phenacetin_A.jdx  --  Transmittance % against wavenumber (cm-1)

    |*********:........:***::**:::::::*||:   .:  . ..
 90 |          ********            Q    ||..|||:||||||.|
    |           V  UTSR                 |N||**||*|**|||
 50 |                                   P *KIG*BA*75||1
    |                                   O MJHFD 986 43
 20 |                                     L  EC      2
    |
-10 |
    ++------+-------+------+-------+------+-------+-----
     4,000        3,000  2,500   2,000  1,500        650

file:    phenacetin_A.jdx
axis:    Transmittance % (the file is Absorbance, converted: %T = 100 x 10^-A)
points:  3474 (3474 between 650 and 4000 cm-1)
range:   3999.64 to 650.857 cm-1; intensity 44.44 to 98.88
ymin:    -5
peaks:   31 (picked automatically); wavenumber/label height
  1 740.5/52.3   2 784.9/47.3   3 825.4/39.4
  4 837.0/34.4   5 923.7/62.5   6 969.1/71.1
  7 1013.4/59.7  8 1045.2/49.5  9 1106.9/58.8
  A 1116.6/53.8  B 1174.4/53.8  C 1241.9/47.3
  D 1265.1/42.3  E 1305.6/37.3  F 1324.9/32.3
  G 1362.5/27.3  H 1392.4/22.3  I 1411.6/17.3
  J 1446.3/12.3  K 1480.1/7.3   L 1505.2/2.3
  M 1551.5/59.0  N 1604.5/69.5  O 1644.0/56.5
  P 1656.6/51.5  Q 2019.1/86.9  R 2848.3/77.1
  S 2917.8/72.4  T 2982.4/76.2  U 3074.9/80.9
  V 3253.3/75.3
"""

GOLDEN_BRAILLE = """\
PHENACETIN_CRUDE_LR1-2.SPA  --  Transmittance % against wavenumber (cm-1)

90 |⠒⠒⠒⠒⠒⠒⠒⠲⠴⠶⠶⢶⠖⠒⠒⠒⠒⠚⠒⠒⠒⠒⠚⠉⠹⣴⣆⣠⣴⣆⣤⣄⣤⢦⣄⡤
   |        V UTR        Q   ⠇⠻⠛⠃⠿⠛⠹⠈⢸⠛⠁
40 |           S             PMJGDB8642
   |                         OLIFCA7531
   ++----+----+-----+----+----+-----+---
    4,000   3,000 2,500     1,500    650

file:    PHENACETIN_CRUDE_LR1-2.SPA
axis:    Transmittance %
points:  3734 (3474 between 650 and 4000 cm-1)
range:   3999.64 to 400.157 cm-1; intensity 44.45 to 98.89
ymin:    -5
peaks:   31 (picked automatically); wavenumber/label height
  1 740.5/52.3   2 784.9/47.3
  3 825.4/39.4   4 837.0/34.4
  5 923.7/62.5   6 969.1/71.0
  7 1013.4/59.7  8 1045.2/49.4
  - 1106.9/58.7  A 1116.6/53.7
  B 1174.4/53.8  C 1241.9/47.3
  D 1265.1/42.3  - 1305.6/37.3
  F 1324.9/32.3  G 1362.5/27.3
  - 1392.4/22.3  I 1411.6/17.3
  J 1446.4/12.3  - 1480.1/7.3
  L 1505.2/2.3   M 1551.5/59.1
  - 1604.5/69.5  O 1644.0/56.5
  P 1656.6/51.5  Q 2018.1/86.9
  R 2848.3/77.1  S 2917.8/72.4
  T 2982.4/76.3  U 3074.9/80.9
  V 3253.3/75.3
  (- : listed, not marked in the plot)
"""


def run(*args, cwd=DATA, encoding="utf-8"):
    """irspec preview as a user runs it (stdout is a pipe): exit status, stdout, stderr."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING=encoding)
    r = subprocess.run([sys.executable, "-m", "irspec", "preview", *map(str, args)],
                       capture_output=True, text=True, env=env, cwd=str(cwd), encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def plot_rows(text):
    """The rows of plot (between the header and the x axis) and the axis line."""
    lines = text.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.lstrip().startswith("++"))
    return lines[2:i], lines[i]


class Golden(unittest.TestCase):
    def test_spa_ascii(self):
        code, out, err = run(SAMPLE, *SMALL)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, GOLDEN_SPA)

    def test_jdx_transmittance_ascii(self):
        code, out, err = run("phenacetin_T.jdx", *SMALL)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, GOLDEN_JDX_T)

    def test_jdx_absorbance_is_converted_and_says_so(self):
        code, out, err = run("phenacetin_A.jdx", *SMALL)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, GOLDEN_JDX_A)
        self.assertIn("the file is Absorbance, converted", out)

    def test_braille(self):
        code, out, err = run(SAMPLE, "--width", "40", "--height", "4")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, GOLDEN_BRAILLE)
        self.assertTrue(any(0x2800 <= ord(c) <= 0x28FF for c in out))


class Width(unittest.TestCase):
    def test_piped_default_is_80_columns(self):
        for name in (SAMPLE, "phenacetin_T.jdx", "phenacetin_A.jdx"):
            with self.subTest(name=name):
                code, out, _ = run(name, "--ascii")
                self.assertEqual(code, 0)
                _, axis = plot_rows(out)
                self.assertEqual(len(axis), 80)
                self.assertLessEqual(max(len(ln) for ln in out.splitlines()), 80)

    def test_width_and_height_override(self):
        code, out, _ = run(SAMPLE, "--ascii", "--width", "100", "--height", "12")
        rows, axis = plot_rows(out)
        self.assertEqual(len(axis), 100)
        self.assertEqual(len(rows), 12)
        self.assertLessEqual(max(len(ln) for ln in out.splitlines()), 100)

    def test_the_default_height_is_20_rows(self):
        rows, _ = plot_rows(run(SAMPLE, "--ascii")[1])
        self.assertEqual(len(rows), 20)

    def test_terminal_width_is_used_when_stdout_is_a_terminal(self):
        with mock.patch.object(sys.stdout, "isatty", return_value=True), \
                mock.patch("shutil.get_terminal_size", return_value=os.terminal_size((97, 30))):
            self.assertEqual(preview.default_width(), 97)
        with mock.patch.object(sys.stdout, "isatty", return_value=False), \
                mock.patch("shutil.get_terminal_size", return_value=os.terminal_size((97, 30))):
            self.assertEqual(preview.default_width(), 80)

    def test_too_small_is_exit_2(self):
        for args in (("--width", "29"), ("--width", "10"), ("--height", "2")):
            code, out, err = run(SAMPLE, *args)
            self.assertEqual((code, out), (2, ""))
            self.assertTrue(err.startswith("irspec preview:"), err)


class Characters(unittest.TestCase):
    def test_braille_only_for_a_utf8_stdout_and_never_with_ascii(self):
        braille = run(SAMPLE, "--width", "60", "--height", "6")[1]
        self.assertTrue(any(0x2800 <= ord(c) <= 0x28FF for c in braille))
        ascii_flag = run(SAMPLE, "--width", "60", "--height", "6", "--ascii")[1]
        self.assertTrue(ascii_flag.isascii())
        code, out, err = run(SAMPLE, "--width", "60", "--height", "6", encoding="ascii")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, ascii_flag)

    def test_ascii_uses_only_the_four_trace_characters(self):
        out = run(SAMPLE, "--width", "80", "--height", "12", "--ascii")[1]
        plot = [ln.split("|", 1)[1] for ln in plot_rows(out)[0]]
        trace = set("".join(plot)) - set(" ")
        symbols = set(preview.SYMBOLS)
        self.assertTrue(trace - symbols <= set(".:*|"), trace - symbols)
        self.assertTrue({".", ":", "*", "|"} <= trace)


class Axes(unittest.TestCase):
    def test_x_axis_runs_from_the_figure_limits_left_to_right(self):
        out = run(SAMPLE, *SMALL)[1]
        labels = next(ln for ln in out.splitlines() if "4,000" in ln)
        self.assertTrue(labels.lstrip().startswith("4,000"))
        self.assertIn("650", labels)
        self.assertLess(labels.index("4,000"), labels.index("3,000"))
        self.assertLess(labels.index("3,000"), labels.index("650"))

    def test_limits_come_from_layout(self):
        with mock.patch.object(layout, "XLIM", (3000.0, 1000.0)):
            info = preview.work_out(str(DATA / SAMPLE))
            text = preview.render(info, 56, 8, False)
        labels = next(ln for ln in text.splitlines() if "3,000" in ln and "1,000" in ln)
        self.assertTrue(labels.lstrip().startswith("3,000"))
        self.assertIn("1,000", labels)
        self.assertNotIn("4,000", labels)
        self.assertIn("between 1000 and 3000 cm-1", text)
        rows, _ = plot_rows(text)
        body = [ln.split("|", 1)[1] for ln in rows]
        # the data covers the whole of the drawn range, so the trace reaches both edges
        self.assertTrue(any(ln[:1] in tuple(".:*|") for ln in body))
        self.assertTrue(any(ln.rstrip()[-1:] in tuple(".:*|") for ln in body if ln.strip()))

    def test_peak_symbols_are_in_the_plot_and_in_the_list(self):
        out = run(SAMPLE, "--width", "100", "--height", "16", "--ascii")[1]
        rows, _ = plot_rows(out)
        plot = "".join(ln.split("|", 1)[1] for ln in rows)
        listing = out[out.index("\npeaks:"):]
        for n in (0, 8, 9, 30):  # 1, 9, A, V
            self.assertIn(f"{preview.SYMBOLS[n]} ", listing)
        marked = [s for s in preview.SYMBOLS[:31] if s in plot]
        self.assertGreaterEqual(len(marked), 25)
        self.assertIn("Q", plot)  # 2018.1, an isolated band: always marked


class Absorbance(unittest.TestCase):
    """A spectrum that is an absorbance on its axis (an archival CSV) is drawn as one: bands point
    up and the symbols sit above them."""

    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        import math
        lines = (DATA / "golden_plain.csv").read_text(encoding="utf-8").splitlines()[1:]
        rows = [tuple(map(float, ln.split(","))) for ln in lines if ln.strip()]
        text = ";ABS;\nWavenumbers [1/cm];Absorbance;\n" + "".join(
            f"{x:.3f};{-math.log10(y / 100.0):.5f};\n".replace(".", ",") for x, y in rows)
        self.path = Path(self._work.name) / "abs.csv"
        self.path.write_text(text, encoding="utf-8")

    def test_peaks_point_up_and_the_symbols_are_above_them(self):
        code, out, err = run(self.path.name, "--width", "100", "--height", "16", "--ascii",
                             cwd=self.path.parent)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("drawn as absorbance, bands point up", out)
        self.assertIn("the data's own minimum", out)
        rows, _ = plot_rows(out)
        body = [ln.split("|", 1)[1].ljust(100) for ln in rows]
        symbols = set(preview.SYMBOLS)
        above = total = 0
        for r in range(len(body) - 1):
            for c, ch in enumerate(body[r]):
                if ch in symbols:
                    total += 1
                    above += body[r + 1][c] in ".:*|"
        self.assertGreaterEqual(total, 20)
        self.assertGreaterEqual(above, 0.8 * total)

    def test_json(self):
        obj = json.loads(run(self.path.name, "--json", cwd=self.path.parent)[1])
        self.assertEqual((obj["axis"], obj["ymin"], obj["converted_from"]), ("Absorbance", None, None))
        self.assertGreater(len(obj["peaks"]), 20)
        self.assertTrue(all(ly > 0 for _, ly in obj["peaks"]))


class Json(unittest.TestCase):
    def test_one_object_and_no_plot(self):
        code, out, err = run(SAMPLE, "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.count("\n"), 1)
        obj = json.loads(out)
        self.assertEqual(set(obj), {"file", "kind", "axis", "converted_from", "points", "range",
                                    "ymin", "peaks", "peaks_from"})
        self.assertEqual((obj["file"], obj["kind"], obj["axis"]), (SAMPLE, "spa", "Transmittance %"))
        self.assertEqual((obj["points"], obj["ymin"], obj["peaks_from"]), (3734, -5, "automatic"))
        self.assertEqual(len(obj["peaks"]), 31)
        self.assertEqual(obj["peaks"][0], [740.5, 52.3])
        self.assertEqual(set(obj["range"]), {"x", "y"})
        self.assertNotIn("+--", out)

    def test_absorbance_jdx_says_what_it_converted(self):
        obj = json.loads(run("phenacetin_A.jdx", "--json")[1])
        self.assertEqual((obj["kind"], obj["axis"], obj["converted_from"]),
                         ("jdx", "Transmittance %", "Absorbance"))
        self.assertIsNone(json.loads(run("phenacetin_T.jdx", "--json")[1])["converted_from"])


class SameAsTheSession(unittest.TestCase):
    """The preview must not lie: its peaks are the ones a session writes."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.session = Path(cls._tmp.name) / "s"
        for sub, name in (("SPA", SAMPLE), ("jdx", "phenacetin_A.jdx"), ("jdx", "phenacetin_T.jdx")):
            (cls.session / sub).mkdir(parents=True, exist_ok=True)
            shutil.copy(DATA / name, cls.session / sub / name)
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        r = subprocess.run([sys.executable, "-m", "irspec", "session", str(cls.session),
                            "--build", "none"], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        cls.manifest = json.loads((cls.session / "manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_a_file_outside_any_folder_gets_the_peaks_a_session_picks(self):
        for entry in self.manifest:
            with self.subTest(file=entry["file"]):
                obj = json.loads(run(os.path.basename(entry["file"]), "--json")[1])
                self.assertEqual(obj["peaks_from"], "automatic")
                self.assertEqual(obj["peaks"], entry["peaks"])

    def test_figures_json_ymin_and_peaks(self):
        figures = json.loads((self.session / "figures.json").read_text(encoding="utf-8"))
        by_title = {f["title"]: f for f in figures}
        obj = json.loads(run(SAMPLE, "--json")[1])
        fig = by_title["PHENACETIN_CRUDE_LR1-2"]
        self.assertEqual(obj["ymin"], fig["ymin"])
        self.assertEqual(obj["peaks"], [list(p) for p in fig["peaks"]])

    def test_a_file_listed_in_a_manifest_uses_that_entry(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        folder = work / "s"
        shutil.copytree(self.session, folder)
        path = folder / "manifest.json"
        entries = json.loads(path.read_text(encoding="utf-8"))
        entries[0]["peaks"] = [[1720.0, 60.0], [3000.0, 70.0]]
        entries[0]["ymin"] = -20
        path.write_text(json.dumps(entries), encoding="utf-8")
        code, out, _ = run(f"SPA/{SAMPLE}", "--json", cwd=folder)
        obj = json.loads(out)
        self.assertEqual((code, obj["peaks_from"]), (0, "manifest.json"))
        self.assertEqual(obj["peaks"], [[1720.0, 60.0], [3000.0, 70.0]])
        self.assertEqual(obj["ymin"], -20)
        text = run(f"SPA/{SAMPLE}", *SMALL, cwd=folder)[1]
        self.assertIn("from manifest.json", text)
        self.assertIn("manifest.json entry used", text)
        # the same file elsewhere is not affected
        self.assertEqual(json.loads(run(SAMPLE, "--json")[1])["peaks_from"], "automatic")

    def test_the_entrys_axis_is_used(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        folder = work / "s"
        shutil.copytree(self.session, folder)
        path = folder / "manifest.json"
        entries = json.loads(path.read_text(encoding="utf-8"))
        entries[0].pop("peaks")
        entries[0]["axis"] = "Absorbance"
        path.write_text(json.dumps(entries), encoding="utf-8")
        obj = json.loads(run(f"SPA/{SAMPLE}", "--json", cwd=folder)[1])
        self.assertEqual((obj["axis"], obj["ymin"]), ("Absorbance", None))
        self.assertEqual(obj["peaks_from"], "automatic")  # the entry has no peaks of its own
        self.assertNotEqual(len(obj["peaks"]), 31)  # the %T data picked as absorbance

    def test_a_manifest_edit_is_what_the_preview_shows(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        folder = work / "s"
        shutil.copytree(self.session, folder)
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        subprocess.run([sys.executable, "-m", "irspec", "edit", str(folder), SAMPLE, "peak",
                        "remove", "740", "3253"], check=True, capture_output=True, env=env)
        obj = json.loads(run(f"SPA/{SAMPLE}", "--json", cwd=folder)[1])
        self.assertEqual(len(obj["peaks"]), 29)
        self.assertNotIn(740.5, [p[0] for p in obj["peaks"]])


class Unreadable(unittest.TestCase):
    def check(self, *args):
        code, out, err = run(*args)
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.strip().splitlines()[-1].startswith("irspec preview: "), err)
        self.assertNotIn("Traceback", err)
        return err

    def test_missing_file(self):
        self.assertIn("no such file", self.check("nothing-here.SPA"))

    def test_a_folder(self):
        self.check(".")

    def test_unknown_extension(self):
        self.assertIn("unrecognised extension", self.check("differential_expected.json"))

    def test_garbage_with_the_right_name(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        for name, data in (("bad.SPA", b"not a spectrum" * 50), ("bad.jdx", b"##TITLE=x\n"),
                           ("bad.csv", b"wavenumber,intensity\nabc,def\n"), ("empty.csv", b""),
                           ("short.SPA", b"")):
            (work / name).write_bytes(data)
            with self.subTest(name=name):
                code, out, err = run(name, cwd=work)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.strip().splitlines()[-1].startswith("irspec preview: "), err)
                self.assertNotIn("Traceback", err)

    def test_quantir_file_without_its_scale_is_not_drawn(self):
        self.assertIn("peak_a", self.check("phenacetin_quantir.jdx"))

    def test_quantir_file_with_its_scale_in_a_manifest_is_drawn_as_the_session_draws_it(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        (work / "jdx").mkdir()
        shutil.copy(DATA / "phenacetin_quantir.jdx", work / "jdx" / "q.jdx")
        (work / "manifest.json").write_text(
            json.dumps([{"file": "jdx/q.jdx", "name": "QUANT", "peak_a": 1}]), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        r = subprocess.run([sys.executable, "-m", "irspec", "session", str(work), "--build", "none"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        stored = json.loads((work / "manifest.json").read_text(encoding="utf-8"))[0]["peaks"]
        code, out, _ = run("jdx/q.jdx", "--json", cwd=work)
        obj = json.loads(out)
        self.assertEqual((code, obj["converted_from"]), (0, "Absorbance"))
        self.assertEqual(obj["peaks"], stored)

    def test_nothing_is_written(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        shutil.copy(DATA / SAMPLE, work / SAMPLE)
        run(SAMPLE, cwd=work)
        run(SAMPLE, "--json", cwd=work)
        self.assertEqual(os.listdir(work), [SAMPLE])


class Csv(unittest.TestCase):
    def test_plain_and_archival_csv_draw_the_same_spectrum(self):
        a = json.loads(run("golden_plain.csv", "--json")[1])
        b = json.loads(run("golden_archival.csv", "--json")[1])
        self.assertEqual((a["kind"], a["axis"]), ("csv", "Transmittance %"))
        self.assertEqual(a["peaks"], b["peaks"])
        self.assertEqual(len(a["peaks"]), 31)


class Registered(unittest.TestCase):
    def test_command_and_help(self):
        self.assertEqual(cli.COMMANDS["preview"], "preview")
        code, out, _ = run("--help")
        self.assertEqual(code, 0)
        flat = " ".join(out.split())
        for word in ("--width", "--height", "--ascii", "--json", "Braille",
                     "shape, ranges, peak positions and which peaks are marked",
                     "not fonts"):
            self.assertIn(word, flat)


if __name__ == "__main__":
    unittest.main()
