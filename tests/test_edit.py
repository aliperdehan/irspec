"""irspec edit: set/unset/show on manifest.json."""
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
from irspec import cli, edit, ir_organize  # noqa: E402

DATA = ROOT / "tests" / "data"
SPA = "SPA/PHENACETIN_CRUDE_LR1-2.SPA"

ENTRIES = [
    {"file": SPA, "title": "Phenacetin (crude)",
     "peaks": [[740.5, 52.3], [1241.9, 47.3], [3253.3, 75.3]], "ymin": -5, "prominence": 3.0},
    {"file": "jdx/62-44-2-IR.jdx", "title": "Phenacetin ref", "args": ["--a", "b"], "name": "PHENACETIN"},
    {"file": "jdx/PHENACETIN_CRUDE_LR1-2.jdx", "title": "Same stem again"},
]


def run(*args):
    """irspec edit as a user runs it: exit status, stdout, stderr."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run([sys.executable, "-m", "irspec", "edit", *map(str, args)],
                       capture_output=True, text=True, env=env, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "session"
        self.dir.mkdir()
        ir_organize.save_manifest(str(self.dir), ENTRIES)  # the layout `irspec session` writes

    @property
    def mpath(self):
        return self.dir / "manifest.json"

    def load(self):
        return json.loads(self.mpath.read_text(encoding="utf-8"))

    def bytes(self):
        return self.mpath.read_bytes()


class SetUnset(Base):
    def test_numbers_are_json_numbers_and_text_is_text(self):
        code, out, err = run(self.dir, "PHENACETIN_CRUDE_LR1-2.SPA", "set", "ymin=-7", "ymax=100.5",
                             "xmin=650", "distance=1e1", "title=Phenacetin, recrystallised",
                             "axis=Absorbance")
        self.assertEqual((code, err), (0, ""))
        e = self.load()[0]
        self.assertEqual((e["ymin"], e["ymax"], e["xmin"], e["distance"]), (-7, 100.5, 650, 10.0))
        self.assertIs(type(e["ymin"]), int)
        self.assertIs(type(e["ymax"]), float)
        self.assertEqual((e["title"], e["axis"]), ("Phenacetin, recrystallised", "Absorbance"))
        run(self.dir, SPA, "set", "name=123")  # a text key keeps digits as text
        self.assertEqual(self.load()[0]["name"], "123")

    def test_text_value_keeps_its_spaces_and_key_may_be_spaced(self):
        run(self.dir, SPA, "set", "title= two  spaces ", "ymin =4")
        e = self.load()[0]
        self.assertEqual((e["title"], e["ymin"]), (" two  spaces ", 4))

    def test_value_may_contain_equals_sign(self):
        run(self.dir, SPA, "set", "title=a=b")
        self.assertEqual(self.load()[0]["title"], "a=b")

    def test_non_numeric_value_is_rejected_with_exit_2_and_nothing_written(self):
        before = self.bytes()
        for bad in ("ymin=abc", "ymin=", "xmax=1,5", "threshold=nan", "distance=inf", "ymax=0x10",
                    "prominence=1_0", "ymin=1e999"):
            code, out, err = run(self.dir, SPA, "set", bad)
            self.assertEqual(code, 2, bad)
            self.assertEqual(out, "", bad)
            self.assertIn(bad.split("=")[0], err)
            self.assertIn("number", err)
            self.assertEqual(self.bytes(), before, bad)

    def test_unknown_key_lists_the_allowed_ones(self):
        before = self.bytes()
        for args in (("set", "peaks=1"), ("unset", "file"), ("set", "colour=red")):
            code, out, err = run(self.dir, SPA, *args)
            self.assertEqual(code, 2)
            self.assertIn("unknown key", err)
            for k in edit.ALLOWED_KEYS:
                self.assertIn(k, err)
            self.assertEqual(self.bytes(), before)

    def test_assignment_without_equals_sign_is_rejected(self):
        before = self.bytes()
        code, out, err = run(self.dir, SPA, "set", "title")
        self.assertEqual(code, 2)
        self.assertIn("KEY=VALUE", err)
        self.assertEqual(self.bytes(), before)

    def test_one_bad_assignment_stops_the_whole_command(self):
        before = self.bytes()
        for args in (("ymin=1", "ymax=x"), ("ymin=1", "ymin=2"), ("ymin=1", "novalue"), ()):
            code, _, err = run(self.dir, SPA, "set", *args)
            self.assertEqual(code, 2, args)
            self.assertEqual(self.bytes(), before, args)

    def test_order_of_entries_and_keys_is_kept_new_key_goes_last(self):
        run(self.dir, SPA, "set", "title=T2", "xmax=4000", "ymin=-9")
        entries = self.load()
        self.assertEqual([e["file"] for e in entries], [e["file"] for e in ENTRIES])
        self.assertEqual(list(entries[0]), ["file", "title", "peaks", "ymin", "prominence", "xmax"])
        self.assertEqual(entries[0]["ymin"], -9)
        self.assertEqual(entries[1:], ENTRIES[1:])
        self.assertEqual(entries[0]["peaks"], ENTRIES[0]["peaks"])

    def test_unset_removes_the_key_and_keeps_the_rest(self):
        code, out, err = run(self.dir, SPA, "unset", "ymin", "prominence")
        self.assertEqual(code, 0)
        self.assertEqual(list(self.load()[0]), ["file", "title", "peaks"])

    def test_unset_of_a_missing_key_is_not_an_error_and_not_a_write(self):
        before = self.bytes()
        mtime = self.mpath.stat().st_mtime_ns
        code, out, err = run(self.dir, SPA, "unset", "ymax")
        self.assertEqual(code, 0)
        self.assertIn("no change", out)
        self.assertEqual((self.bytes(), self.mpath.stat().st_mtime_ns), (before, mtime))

    def test_running_twice_leaves_identical_bytes(self):
        for args in (("set", "ymin=-7", "title=New"), ("unset", "ymin"), ("set", "ymax=5.0")):
            run(self.dir, SPA, *args)
            once = self.bytes()
            code, out, err = run(self.dir, SPA, *args)
            self.assertEqual(code, 0)
            self.assertEqual(self.bytes(), once, args)
            self.assertIn("no change", out)

    def test_same_value_written_differently_is_not_a_change(self):
        code, out, err = run(self.dir, SPA, "set", "ymin=-5.0", "--json")  # it is -5 already
        self.assertEqual(json.loads(out)["changes"], [])
        self.assertIs(type(self.load()[0]["ymin"]), int)

    def test_a_second_entry_is_untouched_by_an_edit_of_the_first(self):
        run(self.dir, "jdx/62-44-2-IR.jdx", "set", "title=Ref")
        entries = self.load()
        self.assertEqual(entries[0], ENTRIES[0])
        self.assertEqual(entries[1]["title"], "Ref")
        self.assertEqual(entries[1]["args"], ["--a", "b"])

    def test_the_change_is_printed(self):
        code, out, err = run(self.dir, SPA, "set", "ymin=-7", "ymax=100")
        self.assertEqual(out.splitlines(), [SPA, "  ymin: -5 -> -7", "  ymax: (not set) -> 100"])
        code, out, err = run(self.dir, SPA, "unset", "ymin")
        self.assertEqual(out.splitlines(), [SPA, "  ymin: -7 -> (removed)"])

    def test_json_output_is_one_object_and_nothing_else(self):
        code, out, err = run(self.dir, SPA, "set", "ymin=-7", "ymax=100", "title=Z", "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.count("\n"), 1)
        self.assertEqual(json.loads(out), {
            "file": SPA,
            "changes": [{"key": "ymin", "old": -5, "new": -7},
                        {"key": "ymax", "old": None, "new": 100},
                        {"key": "title", "old": "Phenacetin (crude)", "new": "Z"}]})
        code, out, err = run(self.dir, "--json", SPA, "unset", "ymax")
        self.assertEqual(json.loads(out), {"file": SPA,
                                           "changes": [{"key": "ymax", "old": 100, "new": None}]})
        code, out, err = run(self.dir, SPA, "unset", "ymax", "--json")
        self.assertEqual(json.loads(out)["changes"], [])

    def test_errors_go_to_stderr_only_even_with_json(self):
        code, out, err = run(self.dir, SPA, "set", "ymin=x", "--json")
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("irspec edit: "))


class Choosing(Base):
    def test_entry_by_path_by_file_name_and_by_stem(self):
        for name in ("jdx/62-44-2-IR.jdx", "./jdx/62-44-2-IR.jdx", "62-44-2-IR.jdx", "62-44-2-IR"):
            code, out, err = run(self.dir, name, "set", "title=via " + name)
            self.assertEqual(code, 0, (name, err))
            self.assertEqual(self.load()[1]["title"], "via " + name)
            self.assertEqual(self.load()[0]["title"], "Phenacetin (crude)")

    def test_ambiguous_stem_is_an_error_but_the_path_works(self):
        before = self.bytes()
        code, out, err = run(self.dir, "PHENACETIN_CRUDE_LR1-2", "set", "title=X")
        self.assertEqual(code, 2)
        self.assertIn("ambiguous", err)
        self.assertIn(SPA, err)
        self.assertIn("jdx/PHENACETIN_CRUDE_LR1-2.jdx", err)
        self.assertEqual(self.bytes(), before)
        code, out, err = run(self.dir, "jdx/PHENACETIN_CRUDE_LR1-2.jdx", "set", "title=X")
        self.assertEqual(code, 0)
        self.assertEqual(self.load()[2]["title"], "X")

    def test_exact_path_beats_a_looser_match(self):
        ir_organize.save_manifest(str(self.dir), [{"file": "a", "title": "bare a"},
                                                  {"file": "SPA/a", "title": "path a"}])
        run(self.dir, "a", "set", "title=changed")
        self.assertEqual([e["title"] for e in self.load()], ["changed", "path a"])

    def test_no_match_names_the_entries(self):
        before = self.bytes()
        code, out, err = run(self.dir, "nothing", "set", "title=X")
        self.assertEqual(code, 2)
        self.assertIn("no manifest entry", err)
        self.assertIn("jdx/62-44-2-IR.jdx", err)
        self.assertEqual(self.bytes(), before)

    def test_legacy_spa_key_entry_is_found(self):
        ir_organize.save_manifest(str(self.dir), [{"spa": "SPA/old.SPA", "title": "old"}])
        code, out, err = run(self.dir, "old", "set", "ymin=1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.load()[0]["ymin"], 1)

    def test_no_manifest_is_exit_1(self):
        self.mpath.unlink()
        code, out, err = run(self.dir, "x", "set", "ymin=1")
        self.assertEqual(code, 1)
        self.assertIn("manifest.json", err)
        self.assertEqual(run(self.dir, "show")[0], 1)

    def test_broken_manifest_is_exit_1_and_left_alone(self):
        self.mpath.write_text("[{", encoding="utf-8")
        code, out, err = run(self.dir, "x", "set", "ymin=1")
        self.assertEqual(code, 1)
        self.assertEqual(self.bytes(), b"[{")
        self.mpath.write_text('{"file": "x"}', encoding="utf-8")
        self.assertEqual(run(self.dir, "show")[0], 1)

    def test_bad_usage_is_exit_2(self):
        for args in (("x",), (SPA, "frobnicate", "a=b"), (SPA, "unset"), (SPA, "set"), ("show", "a", "b")):
            code, out, err = run(self.dir, *args)
            self.assertEqual(code, 2, args)
            self.assertEqual(out, "", args)


class Layout(Base):
    def test_session_layout_is_what_save_manifest_would_write(self):
        run(self.dir, SPA, "set", "ymin=-7", "xmax=4000")
        want = [dict(e) for e in ENTRIES]
        want[0]["ymin"] = -7
        want[0]["xmax"] = 4000
        other = self.dir.parent / "other"
        other.mkdir()
        ir_organize.save_manifest(str(other), want)
        self.assertEqual(self.bytes(), (other / "manifest.json").read_bytes())

    def test_session_layout_without_peaks_keeps_inline_lists(self):
        entries = [{"file": "img/x.png", "title": "t", "args": ["--palleros", "--x-ticks", "1,2"]}]
        ir_organize.save_manifest(str(self.dir), entries)
        run(self.dir, "x", "set", "ymin=1")
        entries[0]["ymin"] = 1
        other = self.dir.parent / "other"
        other.mkdir()
        ir_organize.save_manifest(str(other), entries)
        self.assertEqual(self.bytes(), (other / "manifest.json").read_bytes())

    def test_a_hand_edited_session_file_keeps_its_peak_lines(self):
        text = self.mpath.read_text(encoding="utf-8").replace("[1241.9, 47.3]", "[ 1241.9 ,47.3 ]")
        self.mpath.write_text(text, encoding="utf-8")
        run(self.dir, "jdx/62-44-2-IR.jdx", "set", "title=Q")
        out = self.mpath.read_text(encoding="utf-8")
        self.assertIn('    "peaks": [\n      [740.5, 52.3],\n      [1241.9, 47.3],', out)
        self.assertIn('"args": ["--a", "b"]', out)

    def test_other_indentation_is_kept(self):
        want = [dict(e) for e in ENTRIES]
        want[1]["ymin"] = 3
        for indent in (4, "\t"):
            self.mpath.write_text(json.dumps(ENTRIES, indent=indent) + "\n", encoding="utf-8")
            run(self.dir, "jdx/62-44-2-IR.jdx", "set", "ymin=3")
            self.assertEqual(self.mpath.read_text(encoding="utf-8"),
                             json.dumps(want, indent=indent) + "\n")

    def test_trailing_newline_crlf_and_non_ascii_are_kept(self):
        self.mpath.write_text(json.dumps(ENTRIES, indent=2, ensure_ascii=False), encoding="utf-8")
        run(self.dir, "jdx/62-44-2-IR.jdx", "set", "title=Naphthalène")
        out = self.bytes().decode("utf-8")
        self.assertFalse(out.endswith("\n"))  # there was no final newline
        self.assertIn("Naphthalène", out)  # and no è escape
        self.mpath.write_bytes(json.dumps(ENTRIES, indent=2).replace("\n", "\r\n").encode() + b"\r\n")
        run(self.dir, "jdx/62-44-2-IR.jdx", "set", "ymin=3")
        raw = self.bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertTrue(raw.endswith(b"\r\n"))
        self.assertEqual(self.load()[1]["ymin"], 3)

    def test_json_escaped_non_ascii_stays_escaped(self):
        self.mpath.write_text(json.dumps([{"file": "a", "title": "café"}], indent=2) + "\n",
                              encoding="utf-8")
        run(self.dir, "a", "set", "ymin=1")
        self.assertIn("caf\\u00e9", self.mpath.read_text(encoding="utf-8"))

    def test_write_is_a_rename_and_leaves_no_temporary_file(self):
        ino = self.mpath.stat().st_ino
        os.chmod(self.mpath, 0o640)
        run(self.dir, "jdx/62-44-2-IR.jdx", "set", "ymin=3")
        self.assertNotEqual(self.mpath.stat().st_ino, ino)  # a new file renamed over the old one
        self.assertEqual(self.mpath.stat().st_mode & 0o777, 0o640)
        self.assertEqual(os.listdir(self.dir), ["manifest.json"])

    def test_a_failed_rename_leaves_the_original_and_no_temporary_file(self):
        before = self.bytes()
        with mock.patch("os.replace", side_effect=OSError("disk gone")):
            with self.assertRaises(OSError):
                edit.edit(str(self.dir), "jdx/62-44-2-IR.jdx", "set", ["ymin=3"])
        self.assertEqual(self.bytes(), before)
        self.assertEqual(os.listdir(self.dir), ["manifest.json"])


class Show(Base):
    def test_show_one_entry_as_text(self):
        code, out, err = run(self.dir, "show", "jdx/62-44-2-IR.jdx")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["jdx/62-44-2-IR.jdx", "  title: Phenacetin ref",
                                            '  args: ["--a", "b"]', "  name: PHENACETIN"])

    def test_show_peaks_as_positions(self):
        code, out, err = run(self.dir, "show", "PHENACETIN_CRUDE_LR1-2.SPA")
        self.assertIn("  peaks: 3 at 740.5, 1241.9, 3253.3", out.splitlines())
        self.assertIn("  ymin: -5", out.splitlines())

    def test_show_all_entries_as_text(self):
        code, out, err = run(self.dir, "show")
        self.assertEqual(code, 0)
        heads = [line for line in out.splitlines() if line.startswith("[")]
        self.assertEqual(heads, ["[1] " + SPA, "[2] jdx/62-44-2-IR.jdx",
                                 "[3] jdx/PHENACETIN_CRUDE_LR1-2.jdx"])

    def test_show_json(self):
        code, out, err = run(self.dir, "show", "--json")
        self.assertEqual(json.loads(out), ENTRIES)
        code, out, err = run(self.dir, "show", "62-44-2-IR", "--json")
        self.assertEqual(json.loads(out), ENTRIES[1])
        self.assertEqual(run(self.dir, "--json", "show", "nothing")[0], 2)

    def test_show_does_not_write(self):
        before = self.bytes()
        mtime = self.mpath.stat().st_mtime_ns
        run(self.dir, "show")
        run(self.dir, "show", "--json")
        self.assertEqual((self.bytes(), self.mpath.stat().st_mtime_ns), (before, mtime))


class WithSession(unittest.TestCase):
    def test_an_edit_survives_a_session_rerun_and_reaches_the_figure_spec(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "s"
            folder.mkdir()
            shutil.copy(DATA / "PHENACETIN_CRUDE_LR1-2.SPA", folder)
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))

            def session():
                r = subprocess.run([sys.executable, "-m", "irspec", "session", str(folder),
                                    "--build", "none"],
                                   capture_output=True, text=True, env=env, encoding="utf-8")
                self.assertEqual(r.returncode, 0, r.stderr)

            session()
            code, out, err = run(folder, "PHENACETIN_CRUDE_LR1-2", "set", "ymin=-7", "title=Edited")
            self.assertEqual(code, 0, err)
            session()
            entry = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))[0]
            self.assertEqual((entry["ymin"], entry["title"]), (-7, "Edited"))
            self.assertGreater(len(entry["peaks"]), 3)
            spec = (folder / "figures.json").read_text(encoding="utf-8")
            self.assertIn('"ymin": -7', spec)


class Registered(unittest.TestCase):
    def test_edit_is_a_command(self):
        self.assertEqual(cli.COMMANDS["edit"], "edit")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main([])
        self.assertIn("irspec edit", buf.getvalue())

    def test_help_names_the_keys(self):
        code, out, err = run("--help")
        self.assertEqual(code, 0)
        for k in edit.ALLOWED_KEYS:
            self.assertIn(k, out)


if __name__ == "__main__":
    unittest.main()
