"""irspec edit ... --build MODE: the session is re-run after the edit, so the files follow it.

The folder is made by `irspec session --build none` on the sample .SPA and two .jdx fixtures
(tests/data), copied afresh for each test. The markdown is named after the folder
(`default_md_name`: ir_29-09 for lab_29-09), so nothing here globs for *.md.
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
DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
SPA = "SPA/" + SAMPLE
T = "jdx/62-44-2-IR.jdx"
A = "jdx/50-00-0-IR.jdx"
MD = "ir_29-09.md"        # default_md_name: a date in the folder name names the markdown
MD_PDF = "ir_29-09.pdf"
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
HAVE_LUALATEX = shutil.which("lualatex") is not None


def irspec(*args, env=None):
    r = subprocess.run([sys.executable, "-m", "irspec", *map(str, args)],
                       capture_output=True, text=True, env=env or ENV, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.template = Path(cls._tmp.name) / "lab_29-09"
        cls.template.mkdir()
        shutil.copy(DATA / SAMPLE, cls.template)
        shutil.copy(DATA / "phenacetin_T.jdx", cls.template / "62-44-2-IR.jdx")
        shutil.copy(DATA / "phenacetin_A.jdx", cls.template / "50-00-0-IR.jdx")
        code, out, err = irspec("session", cls.template, "--build", "none")
        assert code == 0, err

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        self.dir = Path(self._work.name) / "lab_29-09"
        shutil.copytree(self.template, self.dir)

    def md(self):
        return (self.dir / MD).read_text(encoding="utf-8")


class BuildNoneTest(Base):
    def test_without_build_nothing_but_the_manifest_changes(self):
        md = self.md()
        code, out, err = irspec("edit", self.dir, A, "set", "title=Formaldehyde")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.md(), md)  # the old behaviour: no redraw

    def test_build_none_rewrites_markdown_and_figures(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Formaldehyde, edited",
                                "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertIn("Formaldehyde, edited", self.md())
        figs = (self.dir / "figures.json").read_text(encoding="utf-8")
        self.assertIn("Formaldehyde, edited", figs)

    def test_move_is_followed_by_the_markdown_order(self):
        before = self.md()
        code, out, err = irspec("edit", self.dir, A, "move", "--to", "1", "--build", "none")
        self.assertEqual(code, 0, err)
        after = self.md()
        self.assertNotEqual(before, after)
        # the first figure of the report is now the .jdx moved to the top
        self.assertLess(after.index("50-00-0-IR"), after.index(SAMPLE.split(".")[0]))

    def test_an_edit_that_changes_nothing_still_rebuilds(self):
        (self.dir / MD).unlink()
        code, out, err = irspec("edit", self.dir, A, "set", "ymin=-5", "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.dir / MD).exists())

    def test_progress_goes_to_stdout_after_the_edit_text(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertLess(out.index("title"), out.index("wrote "))


class JsonTest(Base):
    def test_json_stays_one_object_and_says_it_built(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--build", "none", "--json")
        self.assertEqual(code, 0, err)
        obj = json.loads(out)  # exactly one object: json.loads fails on anything else
        self.assertEqual(obj["build"], {"mode": "none", "ok": True})
        self.assertEqual(obj["changes"][0]["new"], "Z")
        self.assertIn("wrote ", err)  # the session's progress went to stderr

    def test_json_without_build_has_no_build_key(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--json")
        self.assertNotIn("build", json.loads(out))


class FailureTest(Base):
    def env_without_pdfmd(self):
        env = dict(ENV, PATH="/usr/bin:/bin")
        env.pop("PDFMD", None)
        return env

    def test_failed_rebuild_keeps_the_edit_and_exits_3(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Kept", "--build", "pdfmd",
                                env=self.env_without_pdfmd())
        self.assertEqual(code, 3)
        self.assertIn("the edit was written, but the rebuild failed", err)
        self.assertIn("pdfmd not found", err)
        entry = [e for e in json.loads((self.dir / "manifest.json").read_text()) if e["file"] == A][0]
        self.assertEqual(entry["title"], "Kept")

    def test_failed_rebuild_with_json_is_still_one_object(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Kept", "--build", "pdfmd",
                                "--json", env=self.env_without_pdfmd())
        self.assertEqual(code, 3)
        obj = json.loads(out)
        self.assertFalse(obj["build"]["ok"])
        self.assertEqual(obj["build"]["mode"], "pdfmd")
        self.assertIn("pdfmd not found", obj["build"]["error"])

    def test_a_refused_edit_does_not_rebuild(self):
        (self.dir / MD).unlink()
        code, out, err = irspec("edit", self.dir, A, "set", "bogus=1", "--build", "none")
        self.assertEqual(code, 2)
        self.assertFalse((self.dir / MD).exists())


class UsageTest(Base):
    def test_show_refuses_build(self):
        code, out, err = irspec("edit", self.dir, "show", "--build", "none")
        self.assertEqual(code, 2)
        self.assertIn("--build", err)

    def test_md_name_needs_build(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--md-name", "other")
        self.assertEqual(code, 2)
        self.assertFalse((self.dir / "other.md").exists())

    def test_md_name_is_passed_on(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--build", "none",
                                "--md-name", "other")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.dir / "other.md").exists())

    def test_unknown_mode_is_refused(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--build", "word")
        self.assertEqual(code, 2)


@unittest.skipUnless(HAVE_LUALATEX, "needs lualatex")
class LatexTest(Base):
    def test_build_latex_makes_the_pdf(self):
        code, out, err = irspec("edit", self.dir, A, "set", "title=Z", "--build", "latex")
        self.assertEqual(code, 0, err)
        pdf = self.dir / MD_PDF
        self.assertTrue(pdf.exists() and pdf.stat().st_size > 1000)


if __name__ == "__main__":
    unittest.main()
