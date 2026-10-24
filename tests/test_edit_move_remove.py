"""irspec edit ... move --to / remove: the order of the manifest, and taking a spectrum out of it.

The folder is made once by `irspec session --build none` on the sample .SPA and two .jdx fixtures
(tests/data), copied afresh for each test. The markdown is named after the folder
(`default_md_name`), so nothing here globs for *.md.
"""
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
from irspec import edit  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
SPA = "SPA/" + SAMPLE
T = "jdx/62-44-2-IR.jdx"
A = "jdx/50-00-0-IR.jdx"
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"))


def irspec(*args):
    r = subprocess.run([sys.executable, "-m", "irspec", *map(str, args)],
                       capture_output=True, text=True, env=ENV, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def tree(folder):
    """Every folder and file under `folder` with its size and modification time."""
    out = []
    for root, dirs, files in os.walk(folder):
        for n in dirs + files:
            p = os.path.join(root, n)
            st = os.stat(p)
            out.append((os.path.relpath(p, folder), st.st_size if os.path.isfile(p) else None,
                        st.st_mtime_ns))
    return sorted(out)


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
        cls.order = [SPA, T, A]
        assert [e["file"] for e in json.loads((cls.template / "manifest.json").read_text())] == cls.order

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        self.dir = Path(self._work.name) / "lab_29-09"
        shutil.copytree(self.template, self.dir)

    @property
    def mpath(self):
        return self.dir / "manifest.json"

    def entries(self):
        return json.loads(self.mpath.read_text(encoding="utf-8"))

    def files(self):
        return [e["file"] for e in self.entries()]

    def run_edit(self, *args):
        return irspec("edit", self.dir, *args)


class MoveTest(Base):
    def test_to_first(self):
        before = {e["file"]: e for e in self.entries()}
        code, out, err = self.run_edit(A, "move", "--to", "1")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.files(), [A, SPA, T])
        self.assertIn("position: 3 -> 1", out)
        for e in self.entries():  # every entry is untouched, only the order differs
            self.assertEqual(e, before[e["file"]])

    def test_to_middle(self):
        code, out, err = self.run_edit(SPA, "move", "--to", "2")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.files(), [T, SPA, A])

    def test_to_last_and_past_the_end(self):
        self.assertEqual(self.run_edit(SPA, "move", "--to", "last")[0], 0)
        self.assertEqual(self.files(), [T, A, SPA])
        code, out, err = self.run_edit(T, "move", "--to", "99")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.files(), [A, SPA, T])
        self.assertIn("position: 1 -> 3", out)
        self.assertEqual(self.run_edit(A, "move", "--to", "LAST")[0], 0)
        self.assertEqual(self.files(), [SPA, T, A])

    def test_below_one_is_refused_and_changes_nothing(self):
        before = self.mpath.read_bytes()
        for bad in ("0", "-1", "two", "1.5", ""):
            code, out, err = self.run_edit(SPA, "move", "--to", bad)
            self.assertEqual(code, 2, bad)
            self.assertEqual(out, "")
            self.assertIn("--to", err)
        self.assertEqual(self.mpath.read_bytes(), before)

    def test_to_is_required_and_belongs_to_move(self):
        before = self.mpath.read_bytes()
        code, out, err = self.run_edit(SPA, "move")
        self.assertEqual(code, 2)
        self.assertIn("--to", err)
        code, out, err = self.run_edit(SPA, "set", "title=X", "--to", "1")
        self.assertEqual(code, 2)
        self.assertIn("move only", err)
        code, out, err = self.run_edit(SPA, "move", "extra", "--to", "1")
        self.assertEqual(code, 2)
        self.assertEqual(self.mpath.read_bytes(), before)

    def test_already_there_changes_nothing(self):
        before, st = self.mpath.read_bytes(), self.mpath.stat().st_mtime_ns
        for to in ("1", "last"):
            target = SPA if to == "1" else A
            code, out, err = self.run_edit(target, "move", "--to", to)
            self.assertEqual((code, err), (0, ""))
            self.assertIn("no change", out)
        self.assertEqual(self.mpath.read_bytes(), before)
        self.assertEqual(self.mpath.stat().st_mtime_ns, st)

    def test_twice_leaves_identical_bytes(self):
        self.run_edit(A, "move", "--to", "1")
        once = self.mpath.read_bytes()
        code, out, err = self.run_edit(A, "move", "--to", "1")
        self.assertEqual(code, 0)
        self.assertEqual(self.mpath.read_bytes(), once)

    def test_layout_is_kept(self):
        """Moving only reorders: the same entries written in the layout `session` writes."""
        self.run_edit(A, "move", "--to", "1")
        text = self.mpath.read_text(encoding="utf-8")
        self.assertEqual(text, edit._session_style(json.loads(text)))

    def test_json(self):
        code, out, err = self.run_edit(T, "move", "--to", "last", "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out),
                         {"file": T, "changes": [{"key": "position", "old": 2, "new": 3}]})
        self.assertEqual(out.count("\n"), 1)
        code, out, err = self.run_edit(T, "move", "--to", "3", "--json")
        self.assertEqual(json.loads(out), {"file": T, "changes": []})

    def test_unknown_file_and_broken_manifest(self):
        before = self.mpath.read_bytes()
        code, out, err = self.run_edit("nothing-here", "move", "--to", "1")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no manifest entry", err)
        self.assertEqual(self.mpath.read_bytes(), before)
        self.mpath.write_text("[ not json", encoding="utf-8")
        code, out, err = self.run_edit(SPA, "move", "--to", "1")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("not valid JSON", err)
        self.mpath.unlink()
        self.assertEqual(self.run_edit(SPA, "move", "--to", "1")[0], 1)

    def test_figures_follow_the_new_order(self):
        self.run_edit(A, "move", "--to", "1")
        code, out, err = irspec("session", self.dir, "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.files(), [A, SPA, T])
        text = (self.dir / "figures.json").read_text(encoding="utf-8")
        self.assertLess(text.index("50-00-0-IR"), text.index("PHENACETIN_CRUDE"))
        self.assertLess(text.index("PHENACETIN_CRUDE"), text.index("62-44-2-IR"))


class RemoveTest(Base):
    def test_entry_out_file_to_removed(self):
        others = [e for e in self.entries() if e["file"] != T]
        csv_before = sorted(os.listdir(self.dir / "csv")) + sorted(os.listdir(self.dir / "plain"))
        code, out, err = self.run_edit(T, "remove")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.entries(), others)
        self.assertFalse((self.dir / T).exists())
        self.assertTrue((self.dir / "removed" / "62-44-2-IR.jdx").is_file())
        self.assertEqual((self.dir / "removed" / "62-44-2-IR.jdx").read_bytes(),
                         (DATA / "phenacetin_T.jdx").read_bytes())
        self.assertEqual(sorted(os.listdir(self.dir / "csv")) + sorted(os.listdir(self.dir / "plain")),
                         csv_before)  # what session made for it stays
        self.assertIn("removed/62-44-2-IR.jdx", out)

    def test_own_spa_too(self):
        code, out, err = self.run_edit(SAMPLE, "remove")  # by file name
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.files(), [T, A])
        self.assertTrue((self.dir / "removed" / SAMPLE).is_file())

    def test_session_does_not_bring_it_back(self):
        self.assertEqual(self.run_edit(T, "remove")[0], 0)
        code, out, err = irspec("session", self.dir, "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.files(), [SPA, A])
        self.assertTrue((self.dir / "removed" / "62-44-2-IR.jdx").is_file())
        self.assertFalse((self.dir / "jdx" / "62-44-2-IR.jdx").exists())
        self.assertFalse((self.dir / "other").exists(), "removed/ must not be filed into other/")
        self.assertEqual(os.listdir(self.dir / "removed"), ["62-44-2-IR.jdx"])
        self.assertNotIn("62-44-2-IR", (self.dir / "figures.json").read_text(encoding="utf-8"))
        # a second run is stable
        before = tree(self.dir / "removed")
        self.assertEqual(irspec("session", self.dir, "--build", "none")[0], 0)
        self.assertEqual(tree(self.dir / "removed"), before)

    def test_without_removed_the_file_would_come_back(self):
        """The reason for removed/: a file left in jdx/ is listed again by the next run."""
        entries = [e for e in self.entries() if e["file"] != T]
        (self.dir / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
        self.assertEqual(irspec("session", self.dir, "--build", "none")[0], 0)
        self.assertIn(T, self.files())

    def test_name_collision_changes_nothing(self):
        (self.dir / "removed").mkdir()
        (self.dir / "removed" / "62-44-2-IR.jdx").write_text("an older one")
        before = tree(self.dir)
        manifest = self.mpath.read_bytes()
        code, out, err = self.run_edit(T, "remove")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("already exists", err)
        self.assertEqual(tree(self.dir), before)
        self.assertEqual(self.mpath.read_bytes(), manifest)
        self.assertEqual((self.dir / "removed" / "62-44-2-IR.jdx").read_text(), "an older one")

    def test_failed_move_puts_the_manifest_back(self):
        before = self.mpath.read_bytes()
        with mock.patch.object(edit.shutil, "move", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(edit.EditError) as cm:
                edit.remove_entry(str(self.dir), T)
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("manifest.json is as it was", str(cm.exception))
        self.assertEqual(self.mpath.read_bytes(), before)
        self.assertTrue((self.dir / T).is_file())

    def test_manifest_is_written_before_the_file_is_moved(self):
        seen = {}
        real_move = shutil.move

        def spy(src, dst):
            seen["files"] = self.files()
            seen["src_there"] = os.path.exists(src)
            return real_move(src, dst)

        with mock.patch.object(edit.shutil, "move", side_effect=spy):
            edit.remove_entry(str(self.dir), T)
        self.assertEqual(seen, {"files": [SPA, A], "src_there": True})

    def test_json_has_the_whole_entry(self):
        entry = next(e for e in self.entries() if e["file"] == T)
        code, out, err = self.run_edit(T, "remove", "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), {"file": T, "removed": entry, "moved_to": "removed/62-44-2-IR.jdx"})
        self.assertIn("peaks", entry)
        self.assertEqual(out.count("\n"), 1)

    def test_entry_whose_file_is_gone(self):
        (self.dir / T).unlink()
        code, out, err = self.run_edit(T, "remove", "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertIsNone(json.loads(out)["moved_to"])
        self.assertEqual(self.files(), [SPA, A])
        self.assertFalse((self.dir / "removed").exists())

    def test_a_path_outside_the_folder_is_never_moved(self):
        outside = Path(self._work.name) / "elsewhere.jdx"
        outside.write_text("x")
        entries = self.entries()
        entries[1]["file"] = str(outside)
        self.mpath.write_text(json.dumps(entries), encoding="utf-8")
        code, out, err = self.run_edit(str(outside), "remove")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(outside.is_file())
        self.assertFalse((self.dir / "removed").exists())

    def test_unknown_file_ambiguous_and_broken_manifest(self):
        before = tree(self.dir)
        code, out, err = self.run_edit("nothing-here", "remove")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no manifest entry", err)
        code, out, err = self.run_edit(T, "remove", "extra")
        self.assertEqual(code, 2)
        self.assertIn("no arguments", err)
        self.assertEqual(tree(self.dir), before)
        self.mpath.write_text("{}", encoding="utf-8")
        code, out, err = self.run_edit(T, "remove")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue((self.dir / T).is_file())

    def test_removing_the_last_entry_leaves_an_empty_list(self):
        for f in (SPA, T, A):
            self.assertEqual(self.run_edit(f, "remove")[0], 0)
        self.assertEqual(self.entries(), [])
        self.assertEqual(sorted(os.listdir(self.dir / "removed")),
                         sorted([SAMPLE, "62-44-2-IR.jdx", "50-00-0-IR.jdx"]))


if __name__ == "__main__":
    unittest.main()
