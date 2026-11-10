"""--json on `session` (a real run) and `peaks`, `kind` on every object, and docs/schema.md.

Folders are made from the author's sample .SPA and the .jdx fixtures (tests/data), copied to a
temp dir as loose files, the way a lab folder arrives. The folder is named lab_29-09, so the
markdown is ir_29-09.md.
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, edit, figure  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
SCHEMA = (ROOT / "docs" / "schema.md").read_text(encoding="utf-8")


def run(*argv):
    """(exit status, stdout, stderr) of `irspec <argv>`, in this process."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main([str(a) for a in argv])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
            if isinstance(e.code, str):   # what the interpreter would print on exit
                err.write(e.code + "\n")
    return code, out.getvalue(), err.getvalue()


def lab_folder(d, quantir=False):
    f = Path(d) / "lab_29-09"
    f.mkdir()
    shutil.copy(DATA / SAMPLE, f)
    shutil.copy(DATA / "phenacetin_T.jdx", f / "62-44-2-IR.jdx")
    shutil.copy(DATA / "phenacetin_A.jdx", f / "50-00-0-IR.jdx")
    if quantir:
        shutil.copy(DATA / "phenacetin_quantir.jdx", f / "1634-04-4-IR.jdx")
    return f


def listing(folder):
    return sorted(os.path.relpath(os.path.join(r, n), folder)
                  for r, dirs, files in os.walk(folder) for n in dirs + files)


def one_object(test, out):
    """The stdout must be exactly one JSON object on one line."""
    test.assertEqual(out.count("\n"), 1, out[:200])
    return json.loads(out)


class SessionJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.folder = lab_folder(cls._tmp.name)
        cls.code, cls.out, cls.err = run("session", cls.folder, "--build", "none", "--json")
        cls.obj = json.loads(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_one_object_and_the_progress_goes_to_stderr(self):
        self.assertEqual(self.code, 0)
        one_object(self, self.out)
        self.assertNotIn("moved:", self.out)
        self.assertIn("moved: 50-00-0-IR.jdx -> jdx/50-00-0-IR.jdx", self.err)
        self.assertIn("ir_29-09.md (3 spectra)", self.err)

    def test_the_top_level_keys(self):
        self.assertEqual(set(self.obj), {"kind", "folder", "dry_run", "moves", "spectra",
                                         "outputs", "build"})
        self.assertEqual((self.obj["kind"], self.obj["dry_run"]), ("ir", False))
        self.assertEqual(self.obj["folder"], str(self.folder))
        self.assertEqual(sorted((m["from"], m["to"]) for m in self.obj["moves"]),
                         [("50-00-0-IR.jdx", "jdx/50-00-0-IR.jdx"),
                          ("62-44-2-IR.jdx", "jdx/62-44-2-IR.jdx"),
                          (SAMPLE, f"SPA/{SAMPLE}")])
        self.assertEqual(self.obj["build"], {"mode": "none", "ok": True})
        self.assertEqual(self.obj["outputs"], {
            "manifest": "manifest.json", "figures": "figures.json", "markdown": "ir_29-09.md",
            "tex": None, "pdf": None, "pictures": []})

    def test_spectra_are_what_the_files_hold(self):
        manifest = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8"))
        figs = json.loads((self.folder / "figures.json").read_text(encoding="utf-8"))
        spectra = self.obj["spectra"]
        self.assertEqual([s["file"] for s in spectra], [e["file"] for e in manifest])
        self.assertEqual(len(spectra), 3)
        for s, e, fig in zip(spectra, manifest, figs):
            self.assertEqual(set(s), {"file", "kind", "title", "name", "axis", "peaks", "n_peaks",
                                      "ymin", "csv", "plain"})
            self.assertEqual(s["kind"], "ir")
            self.assertEqual(s["peaks"], fig["peaks"])
            self.assertEqual(s["peaks"], e["peaks"])
            self.assertEqual((s["title"], s["axis"], s["ymin"]),
                             (fig["title"], fig["axis"], fig.get("ymin")))
            self.assertEqual(s["n_peaks"], len(s["peaks"]))
            self.assertEqual(s["plain"], fig["csv"])
            self.assertTrue((self.folder / s["csv"]).exists())
            self.assertTrue((self.folder / s["plain"]).exists())
        first = next(s for s in spectra if s["file"] == f"SPA/{SAMPLE}")
        self.assertEqual((first["n_peaks"], first["peaks"][0], first["ymin"]),
                         (31, [740.5, 52.3], -5))
        self.assertEqual(first["plain"], "plain/PHENACETIN_CRUDE_LR1-2_plain.csv")

    def test_a_second_run_reports_no_moves(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            run("session", f, "--build", "none", "--json")
            code, out, _ = run("session", f, "--build", "none", "--json")
            self.assertEqual((code, one_object(self, out)["moves"]), (0, []))


class SessionJsonOther(unittest.TestCase):
    def test_dry_run_gives_the_moves_only_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            before = listing(f)
            code, out, err = run("session", f, "--dry-run", "--json")
            obj = one_object(self, out)
            self.assertEqual(code, 0)
            self.assertEqual(set(obj), {"kind", "folder", "dry_run", "moves"})
            self.assertTrue(obj["dry_run"])
            self.assertEqual(len(obj["moves"]), 3)
            self.assertIn("would move", err)
            self.assertEqual(listing(f), before)

    def test_a_failed_build_still_prints_the_object_and_exits_1(self):
        # --formats needs the PDF, and --build none makes none: the work is done, the build fails
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            code, out, err = run("session", f, "--build", "none", "--formats", "png", "--json")
            obj = one_object(self, out)
            self.assertEqual(code, 1)
            self.assertFalse(obj["build"]["ok"])
            self.assertIn("--formats needs the PDF", obj["build"]["error"])
            self.assertEqual(obj["build"]["mode"], "none")
            self.assertEqual(len(obj["spectra"]), 3)
            self.assertTrue((f / "manifest.json").exists())
            self.assertIn("--formats needs the PDF", err)

    def test_a_stop_before_the_build_prints_no_object(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d, quantir=True)
            code, out, err = run("session", f, "--build", "none", "--json")
            self.assertNotEqual(code, 0)
            self.assertEqual(out, "")
            self.assertIn("QUANT-IR", err)

    def test_not_a_directory_prints_no_object(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = run("session", Path(d) / "nope", "--json")
            self.assertEqual((code != 0, out), (True, ""))
            self.assertIn("not a directory", err)

    def test_width_still_needs_preview_but_json_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            code, out, err = run("session", f, "--width", "50", "--json")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("--width goes with --preview", err)

    def test_preview_records_say_kind_and_format(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d, quantir=True)
            code, out, _ = run("session", f, "--preview", "--json")
            obj = one_object(self, out)
            self.assertEqual(code, 1)   # the QUANT-IR file cannot be drawn without peak_a
            self.assertTrue(all(s["kind"] == "ir" for s in obj["spectra"]))
            ok = [s for s in obj["spectra"] if "error" not in s]
            self.assertEqual(sorted(s["format"] for s in ok), ["jdx", "jdx", "spa"])


class PeaksJson(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        for name in (SAMPLE, "phenacetin_A.jdx", "phenacetin_T.jdx"):
            shutil.copy(DATA / name, self.dir)

    def peaks(self, name, *args):
        return run("peaks", self.dir / name, *args)

    def test_spa_gives_one_object_and_lists_the_csvs_it_wrote(self):
        code, out, err = self.peaks(SAMPLE, "--json")
        obj = one_object(self, out)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(set(obj), {"kind", "file", "format", "axis", "mode", "peaks", "bands",
                                    "peaklist", "ymin_suggestion", "ymax_suggestion", "settings",
                                    "written"})
        self.assertEqual((obj["kind"], obj["format"], obj["axis"], obj["mode"]),
                         ("ir", "spa", "Transmittance %", "auto"))
        self.assertEqual(len(obj["peaks"]), 31)
        self.assertEqual(obj["peaks"][0], [740.5, 52.3])
        self.assertEqual(len(obj["bands"]), 31)
        self.assertEqual(obj["bands"][0], 57.2566)
        self.assertEqual((obj["ymin_suggestion"], obj["ymax_suggestion"]), (-5, None))
        stem = str(self.dir / "PHENACETIN_CRUDE_LR1-2")
        self.assertEqual(obj["written"], [stem + ".csv", stem + "_plain.csv"])
        for p in obj["written"]:
            self.assertTrue(os.path.exists(p))
        self.assertEqual(obj["settings"], {"threshold": 5.0, "prominence": 3.0, "distance": 8.0,
                                           "gap": 5.0, "collision_cm": 45.0, "step": 5.0})

    def test_peaks_are_the_pairs_session_writes(self):
        _, out, _ = self.peaks(SAMPLE, "--json")
        obj = json.loads(out)
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            _, sout, _ = run("session", f, "--build", "none", "--json")
            sess = next(s for s in json.loads(sout)["spectra"] if s["file"] == f"SPA/{SAMPLE}")
        self.assertEqual(obj["peaks"], sess["peaks"])
        self.assertEqual(obj["peaklist"], ",".join(f"{x:.1f}/{y:.1f}" for x, y in sess["peaks"]))

    def test_an_absorbance_file_suggests_ymax(self):
        code, out, err = self.peaks("phenacetin_A.jdx", "--json", "--prominence", "0.03", "--gap", "0.05",
                                   "--step", "0.05")
        obj = json.loads(out)
        self.assertEqual((code, obj["format"], obj["axis"]), (0, "jdx", "Absorbance"))
        self.assertIsNone(obj["ymin_suggestion"])
        self.assertIsInstance(obj["ymax_suggestion"], int)
        self.assertEqual(obj["written"], [])
        self.assertIn("note: Absorbance input", err)   # the note stays on stderr

    def test_manual_mode(self):
        _, out, _ = self.peaks("phenacetin_T.jdx", "--json", "--mode", "manual",
                               "--peaks", "3253,1241")
        obj = json.loads(out)
        self.assertEqual(obj["mode"], "manual")
        self.assertEqual(len(obj["peaks"]), 2)
        self.assertEqual(sorted(round(p[0]) for p in obj["peaks"]), [1242, 3253])

    def test_without_json_the_text_is_the_review_table(self):
        code, out, _ = self.peaks("phenacetin_T.jdx")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("# "))
        self.assertIn("peaklist: ", out)
        self.assertFalse(out.lstrip().startswith("{"))


class KindInFiles(unittest.TestCase):
    ENTRY = {"csv": "plain/x.csv", "title": "t", "peaks": [[1000.0, 50.0]]}

    def test_a_missing_kind_and_ir_are_the_same(self):
        a = figure.Figure.from_entry(self.ENTRY)
        b = figure.Figure.from_entry({**self.ENTRY, "kind": "ir"})
        self.assertEqual(a, b)

    def test_another_kind_is_refused_not_drawn_as_ir(self):
        with self.assertRaises(ValueError) as cm:
            figure.Figure.from_entry({**self.ENTRY, "kind": "uvvis"})
        self.assertIn("uvvis", str(cm.exception))

    def test_read_figures_refuses_it_too(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "figures.json"
            p.write_text(json.dumps([{**self.ENTRY, "kind": "uvvis"}]))
            with self.assertRaises(ValueError):
                figure.read_figures(p)

    def test_the_writer_does_not_emit_kind_yet(self):
        self.assertNotIn("kind", figure.Figure(csv="a.csv", title="t").to_entry())


class EditJson(unittest.TestCase):
    def test_edit_objects_say_kind(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            run("session", f, "--build", "none")
            for verb in (["set", "ymin=-7"], ["move", "--to", "last"]):
                code, out, _ = run("edit", f, f"SPA/{SAMPLE}", *verb, "--json")
                self.assertEqual((code, one_object(self, out)["kind"]), (0, "ir"))
            code, out, _ = run("edit", f, "jdx/50-00-0-IR.jdx", "remove", "--json")
            obj = one_object(self, out)
            self.assertEqual((code, obj["kind"], obj["moved_to"]), (0, "ir", "removed/50-00-0-IR.jdx"))


class SchemaDocument(unittest.TestCase):
    """docs/schema.md names every key irspec writes or prints."""

    def documented(self, key):
        self.assertIn(f"`{key}`", SCHEMA, f"docs/schema.md does not mention the key {key!r}")

    def test_the_session_object(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            _, out, _ = run("session", f, "--build", "none", "--json")
            obj = json.loads(out)
            keys = set(obj) | set(obj["spectra"][0]) | set(obj["outputs"]) | set(obj["build"]) \
                | set(obj["moves"][0])
            _, out, _ = run("session", f, "--preview", "--json")
            prev = json.loads(out)
            keys |= set(prev) | set(prev["spectra"][0])
        for k in keys:
            self.documented(k)

    def test_peaks_and_edit_objects(self):
        with tempfile.TemporaryDirectory() as d:
            f = lab_folder(d)
            _, out, _ = run("peaks", f / SAMPLE, "--json")
            obj = json.loads(out)
            keys = set(obj) | set(obj["settings"])
            run("session", f, "--build", "none")
            _, out, _ = run("edit", f, f"SPA/{SAMPLE}", "set", "ymin=-7", "--build", "none", "--json")
            e = json.loads(out)
            keys |= set(e) | set(e["changes"][0]) | set(e["build"])
            _, out, _ = run("edit", f, "jdx/50-00-0-IR.jdx", "remove", "--json")
            keys |= set(json.loads(out))
            _, out, _ = run("preview", f / "jdx" / "62-44-2-IR.jdx", "--json")
            keys |= set(json.loads(out)) | set(json.loads(out)["range"])
        for k in keys:
            self.documented(k)

    def test_the_file_keys(self):
        keys = set(figure.Figure(csv="a", title="t", ymin=1, width="1in", height="1in").to_entry())
        keys |= set(edit.ALLOWED_KEYS) | {"file", "peaks", "kind", "peak_a", "cl", "check", "args"}
        for k in keys:
            self.documented(k)

    def test_the_spec_version_is_the_documented_one(self):
        m = re.search(r"\(`figure\.py`, now (\d+)\)", SCHEMA)
        self.assertEqual(int(m.group(1)), figure.SPEC_VERSION)


if __name__ == "__main__":
    unittest.main()
