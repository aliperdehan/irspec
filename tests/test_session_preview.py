"""irspec session DIR --preview: the planned moves and every spectrum drawn as text, nothing written.

Folders are made from the author's sample .SPA and the three .jdx fixtures (tests/data), copied to a
temp dir as loose files, the way a lab folder arrives.
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, figure, preview, session  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
SMALL = ("--width", "56", "--height", "8", "--ascii")


def run_cli(*argv):
    """(exit status, stdout, stderr) of `irspec <argv>`, in this process."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main(["session", *[str(a) for a in argv]])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    return code, out.getvalue(), err.getvalue()


def real_run(folder):
    """A real `irspec session --build none` run (its progress lines are not wanted here)."""
    with contextlib.redirect_stdout(io.StringIO()):
        session.run(str(folder), build="none")


def loose_folder(d, quantir=False):
    """A folder with the sample .SPA and two .jdx files lying loose in it."""
    f = Path(d) / "lab_29-09"
    f.mkdir()
    shutil.copy(DATA / SAMPLE, f)
    shutil.copy(DATA / "phenacetin_T.jdx", f / "62-44-2-IR.jdx")
    shutil.copy(DATA / "phenacetin_A.jdx", f / "50-00-0-IR.jdx")
    if quantir:
        shutil.copy(DATA / "phenacetin_quantir.jdx", f / "1634-04-4-IR.jdx")
    (f / "cas_names.json").write_text(json.dumps({"62-44-2": "PHENACETIN_T"}))
    return f


def tree(folder):
    """Every folder and file under `folder` with its size and modification time."""
    out = []
    for root, dirs, files in os.walk(folder):
        for n in dirs + files:
            p = os.path.join(root, n)
            st = os.stat(p)
            out.append((os.path.relpath(p, folder), os.path.isdir(p), st.st_size, st.st_mtime_ns))
    return sorted(out)


GOLDEN_SPA_BLOCK = """\
=== SPA/PHENACETIN_CRUDE_LR1-2.SPA  (now PHENACETIN_CRUDE_LR1-2.SPA) ===
title:   PHENACETIN_CRUDE_LR1-2
csv:     csv/PHENACETIN_CRUDE_LR1-2.csv
plain:   plain/PHENACETIN_CRUDE_LR1-2_plain.csv

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
"""


class Untouched(unittest.TestCase):
    """--preview writes nothing: no folder, file, manifest, figure list, and nothing moved."""

    def test_a_loose_folder_is_the_same_tree_afterwards(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            before = tree(f)
            for extra in ([], ["--json"], ["--dry-run"], ["--build", "latex", "--formats", "png"]):
                code, out, _ = run_cli(f, "--preview", *SMALL, *extra)
                self.assertEqual(code, 0, extra)
                self.assertTrue(out)
                self.assertEqual(tree(f), before, extra)
            for name in ("SPA", "jdx", "csv", "plain", "manifest.json", "figures.json"):
                self.assertFalse((f / name).exists(), name)

    def test_a_filed_folder_with_a_manifest_is_the_same_tree_afterwards(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            real_run(f)                  # a real run: filed, manifest, CSVs
            shutil.copy(DATA / "phenacetin_A.jdx", f / "new-1.jdx")   # and one new loose file
            before = tree(f)
            code, out, _ = run_cli(f, "--preview", *SMALL)
            self.assertEqual(code, 0)
            self.assertIn("would move: new-1.jdx -> jdx/new-1.jdx", out)
            self.assertEqual(tree(f), before)


class Text(unittest.TestCase):
    def test_the_moves_are_those_of_dry_run_then_each_spectrum_headed_by_its_names(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            _, dry, _ = run_cli(f, "--dry-run")
            code, out, err = run_cli(f, "--preview", *SMALL, "--sort", "name")
            self.assertEqual((code, err), (0, ""))
            self.assertTrue(out.startswith(dry), "the moves come first, as --dry-run prints them")
            self.assertIn(GOLDEN_SPA_BLOCK, out)
            for head in ("=== jdx/62-44-2-IR.jdx  (now 62-44-2-IR.jdx) ===\n"
                         "title:   Phenacetin t\n"
                         "csv:     csv/PHENACETIN_T.csv\n"
                         "plain:   plain/PHENACETIN_T.csv\n",
                         "=== jdx/50-00-0-IR.jdx  (now 50-00-0-IR.jdx) ===\n"
                         "title:   Phenacetin crude (test fixture)\n"
                         "csv:     csv/50-00-0-IR.csv\n"
                         "plain:   plain/50-00-0-IR.csv\n"):
                self.assertIn(head, out)
            self.assertIn("converted: %T = 100 x 10^-A", out)       # the absorbance .jdx
            self.assertTrue(out.rstrip().endswith("preview only: nothing was written."))

    def test_a_file_already_filed_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            real_run(f)
            code, out, _ = run_cli(f, "--preview", *SMALL)
            self.assertEqual(code, 0)
            self.assertNotIn("would move", out)
            self.assertIn("=== SPA/PHENACETIN_CRUDE_LR1-2.SPA  (already there) ===", out)
            self.assertIn("(manifest.json entry used)", out)

    def test_width_and_height_are_those_of_irspec_preview(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            _, out, _ = run_cli(f, "--preview", "--ascii")
            self.assertEqual(max(len(ln) for ln in out.splitlines() if " |" in ln), 80)   # piped: 80
            _, narrow, _ = run_cli(f, "--preview", "--ascii", "--width", "40", "--height", "5")
            self.assertLessEqual(max(len(ln) for ln in narrow.splitlines() if " |" in ln), 40)

    def test_title_option_is_honoured_in_the_header(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            _, out, _ = run_cli(f, "--preview", *SMALL, "--title", "PHENACETIN_CRUDE_LR1-2=Crude, day 1")
            self.assertIn("title:   Crude, day 1\n", out)

    def test_pictures_are_listed_not_drawn_and_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            (f / "img").mkdir()
            (f / "img" / "67-56-1-IR.gif").write_bytes(b"not an image")   # never opened here
            (f / "loose.gif").write_bytes(b"x")                           # loose: goes to other/, not img/
            code, out, _ = run_cli(f, "--preview", *SMALL)
            self.assertEqual(code, 0)
            self.assertIn("img/67-56-1-IR.gif  ->  csv/67-56-1-IR.csv, plain/67-56-1-IR.csv", out)
            self.assertIn("digitized by `irspec session`, not drawn here", out)
            self.assertNotIn("loose.gif  ->", out)


class ManifestWins(unittest.TestCase):
    def test_peaks_and_title_of_an_existing_manifest_are_used(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            (f / "manifest.json").write_text(json.dumps(
                [{"file": f"SPA/{SAMPLE}", "title": "Mine", "peaks": [[1604.5, 60.0], [2917.8, 80.0]]}]))
            code, out, _ = run_cli(f, "--preview", "--json")
            self.assertEqual(code, 0)
            sp = {s["will_be_filed_as"]: s for s in json.loads(out)["spectra"]}
            mine = sp[f"SPA/{SAMPLE}"]
            self.assertEqual(mine["peaks"], [[1604.5, 60.0], [2917.8, 80.0]])
            self.assertEqual((mine["peaks_from"], mine["title"]), ("manifest.json", "Mine"))
            self.assertEqual(sp["jdx/62-44-2-IR.jdx"]["peaks_from"], "automatic")
            _, text, _ = run_cli(f, "--preview", *SMALL)
            self.assertIn("title:   Mine\n", text)
            self.assertIn("peaks:   2 (from manifest.json)", text)


    def test_a_title_less_entry_of_a_loose_jdx_gets_the_title_inside_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            (f / "cas_names.json").unlink()
            (f / "manifest.json").write_text(json.dumps([{"file": "jdx/62-44-2-IR.jdx"}]))
            code, out, _ = run_cli(f, "--preview", "--json")
            self.assertEqual(code, 0)
            titles = {s["will_be_filed_as"]: s["title"] for s in json.loads(out)["spectra"]}
            self.assertEqual(titles["jdx/62-44-2-IR.jdx"], "Phenacetin crude (test fixture)")


class Json(unittest.TestCase):
    def test_one_object_on_stdout_and_what_the_session_then_writes(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            code, out, err = run_cli(f, "--preview", "--json")
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(out.count("\n"), 1)
            obj = json.loads(out)
            self.assertEqual(set(obj), {"moves", "spectra", "images"})
            self.assertEqual(obj["images"], [])
            self.assertEqual(sorted((m["from"], m["to"]) for m in obj["moves"]),
                             [("50-00-0-IR.jdx", "jdx/50-00-0-IR.jdx"),
                              ("62-44-2-IR.jdx", "jdx/62-44-2-IR.jdx"),
                              (SAMPLE, f"SPA/{SAMPLE}")])
            for s in obj["spectra"]:
                self.assertTrue({"file", "kind", "axis", "converted_from", "points", "range",
                                 "ymin", "peaks", "peaks_from", "will_be_filed_as"} <= set(s))
                self.assertFalse(os.path.isabs(s["file"]))
            got = {s["will_be_filed_as"]: s for s in obj["spectra"]}
            self.assertEqual(got["jdx/50-00-0-IR.jdx"]["converted_from"], "Absorbance")
            # ... and what a real run on the same folder then writes: the same peaks and ymin,
            # in the manifest and in figures.json (the list the drawing backends read)
            real_run(f)
            manifest = {e["file"]: e for e in json.loads((f / "manifest.json").read_text())}
            figures = {fig.csv: fig for fig in figure.read_figures(f / "figures.json")[0]}
            for rel, s in got.items():
                self.assertEqual(s["peaks"], manifest[rel]["peaks"], rel)
                fig = figures[s["plain"]]
                self.assertEqual([list(p) for p in fig.peaks], s["peaks"], rel)
                self.assertEqual(fig.ymin, s["ymin"], rel)

    def test_the_spectrum_part_is_what_irspec_preview_prints_for_the_filed_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            _, out, _ = run_cli(f, "--preview", "--json")
            got = {s["will_be_filed_as"]: s for s in json.loads(out)["spectra"]}
            real_run(f)
            for rel, s in got.items():
                alone = preview.public(preview.work_out(str(f / rel)))
                alone["file"] = s["file"]            # names where the file is now
                alone["peaks_from"] = s["peaks_from"]     # the real run has since written a manifest
                self.assertEqual({k: s[k] for k in alone}, alone, rel)


class Failures(unittest.TestCase):
    def test_an_unreadable_file_is_listed_with_its_error_and_the_others_still_shown(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            (f / "broken.jdx").write_text("this is not a JCAMP-DX file\n")
            code, out, _ = run_cli(f, "--preview", *SMALL)
            self.assertEqual(code, 1)
            self.assertIn("=== jdx/broken.jdx  (now broken.jdx) ===", out)
            self.assertRegex(out, r"error:   broken\.jdx: ")
            self.assertNotIn(str(f), out)                       # relative names only
            self.assertIn(GOLDEN_SPA_BLOCK, out)                # the spectra after it are drawn
            code, out, _ = run_cli(f, "--preview", "--json")
            self.assertEqual(code, 1)
            bad = [s for s in json.loads(out)["spectra"] if "error" in s]
            self.assertEqual([s["will_be_filed_as"] for s in bad], ["jdx/broken.jdx"])
            self.assertEqual(len(json.loads(out)["spectra"]), 4)

    def test_a_quantir_file_without_peak_a_is_an_error_entry_not_a_stop(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d, quantir=True)
            code, out, _ = run_cli(f, "--preview", "--json")
            self.assertEqual(code, 1)
            bad = [s for s in json.loads(out)["spectra"] if "error" in s]
            self.assertEqual([s["will_be_filed_as"] for s in bad], ["jdx/1634-04-4-IR.jdx"])
            self.assertIn("peak_a", bad[0]["error"])

    def test_exit_2_for_a_missing_folder_an_empty_one_and_a_bad_size(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = run_cli(Path(d) / "nope", "--preview")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("not a directory", err)
            empty = Path(d) / "empty"
            empty.mkdir()
            code, out, err = run_cli(empty, "--preview", "--json")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("no spectra found", err)
            self.assertEqual(os.listdir(empty), [])
            f = loose_folder(d)
            code, out, err = run_cli(f, "--preview", "--width", "10")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("--width must be at least", err)

    def test_a_broken_manifest_is_exit_2_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            (f / "manifest.json").write_text("{not json")
            code, out, err = run_cli(f, "--preview")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("manifest.json cannot be used", err)

    def test_the_preview_options_need_preview(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            before = tree(f)
            code, out, err = run_cli(f, "--json", "--dry-run")
            self.assertEqual(code, 2)
            self.assertIn("--json goes with --preview", err)
            self.assertEqual(tree(f), before)


class DryRunIsUnchanged(unittest.TestCase):
    def test_dry_run_alone_prints_only_the_moves(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            before = tree(f)
            code, out, err = run_cli(f, "--dry-run")
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(out, "would move: 50-00-0-IR.jdx -> jdx/50-00-0-IR.jdx\n"
                                  "would move: 62-44-2-IR.jdx -> jdx/62-44-2-IR.jdx\n"
                                  f"would move: {SAMPLE} -> SPA/{SAMPLE}\n")
            self.assertEqual(tree(f), before)

    def test_preview_with_dry_run_means_the_same_as_preview(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            self.assertEqual(run_cli(f, "--preview", *SMALL), run_cli(f, "--preview", "--dry-run", *SMALL))

    def test_a_real_run_still_moves_and_writes(self):
        with tempfile.TemporaryDirectory() as d:
            f = loose_folder(d)
            code, out, _ = run_cli(f, "--build", "none")
            self.assertEqual(code, 0)
            self.assertIn(f"moved: {SAMPLE} -> SPA/{SAMPLE}", out)
            self.assertTrue((f / "manifest.json").exists() and (f / "figures.json").exists())


if __name__ == "__main__":
    unittest.main()
