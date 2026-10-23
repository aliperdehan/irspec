"""irspec edit ... peak add/remove/clear/auto: the peaks of a manifest entry."""
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
from irspec import edit, ir_organize, spa_tool  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
SPA = "SPA/" + SAMPLE
STEM = "PHENACETIN_CRUDE_LR1-2"
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"))


def irspec(*args):
    r = subprocess.run([sys.executable, "-m", "irspec", *map(str, args)],
                       capture_output=True, text=True, env=ENV, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def run(*args):
    return irspec("edit", *args)


class Base(unittest.TestCase):
    """A session folder made once by `irspec session --build none` on the sample .SPA,
    copied afresh for each test."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.template = Path(cls._tmp.name) / "template"
        (cls.template / "SPA").mkdir(parents=True)
        shutil.copy(DATA / SAMPLE, cls.template / "SPA" / SAMPLE)
        code, out, err = irspec("session", cls.template, "--build", "none")
        assert code == 0, err
        cls.fresh = (cls.template / "manifest.json").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self._work = tempfile.TemporaryDirectory()
        self.addCleanup(self._work.cleanup)
        self.dir = Path(self._work.name) / "session"
        shutil.copytree(self.template, self.dir)

    @property
    def mpath(self):
        return self.dir / "manifest.json"

    def entry(self):
        return json.loads(self.mpath.read_text(encoding="utf-8"))[0]

    def peaks(self):
        return self.entry()["peaks"]

    def xs(self):
        return [p[0] for p in self.peaks()]

    def write_entry(self, **changes):
        entries = json.loads(self.mpath.read_text(encoding="utf-8"))
        for k, v in changes.items():
            if v is None:
                entries[0].pop(k, None)
            else:
                entries[0][k] = v
        ir_organize.save_manifest(str(self.dir), entries)

    def peak(self, *args):
        return run(self.dir, STEM, "peak", *args)


class Add(Base):
    def test_snaps_to_the_nearest_local_band_and_keeps_the_list_sorted(self):
        x, y = spa_tool.read_spa(DATA / SAMPLE)
        ((bx, by),) = spa_tool.find_peaks_manual(x, y, [1720], "Transmittance %")
        before = self.peaks()
        code, out, err = self.peak("add", "1720")
        self.assertEqual((code, err), (0, ""))
        self.assertIn(f"{round(bx, 1)}, {round(by - 5.0, 1)}", out)
        after = self.peaks()
        self.assertEqual(after, sorted(before + [[round(bx, 1), round(by - 5.0, 1)]]))
        self.assertEqual(len(after), len(before) + 1)

    def test_label_height_is_the_one_session_gives_a_bare_wavenumber(self):
        self.peak("add", "1720", "3000")
        edited = self.peaks()
        # the same bare numbers in the manifest, resolved by session itself
        self.write_entry(peaks=[1720, 3000])
        self.assertEqual(irspec("session", self.dir, "--build", "none")[0], 0)
        by_session = self.peaks()
        self.assertEqual(len(by_session), 2)
        self.assertTrue(all(p in edited for p in by_session))

    def test_several_at_once_and_a_second_run_changes_nothing(self):
        code, out, _ = self.peak("add", "1720", "3000", "2850")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("(not set) ->"), 2)  # 2850 is already a band (2848.3)
        once = self.mpath.read_bytes()
        code, out, _ = self.peak("add", "1720", "3000", "2850")
        self.assertEqual((code, out.strip()), (0, f"{SPA}: no change"))
        self.assertEqual(self.mpath.read_bytes(), once)

    def test_a_band_already_there_changes_nothing(self):
        code, out, _ = self.peak("add", "740")
        self.assertEqual((code, out.strip()), (0, f"{SPA}: no change"))
        self.assertEqual(self.mpath.read_bytes(), self.fresh)

    def test_a_band_with_a_staggered_label_is_not_added_twice(self):
        stored = self.peaks()
        self.assertTrue(any(abs(ly - (self.trough(x) - 5.0)) > 0.06 for x, ly in stored))
        code, out, _ = self.peak("add", *[str(x) for x, _ in stored], "1720")
        self.assertEqual(code, 0)
        after = self.peaks()
        self.assertEqual(len(after), len(stored) + 1)
        self.assertEqual(len(set(self.xs())), len(after))
        self.assertTrue(all(p in after for p in stored))  # their labels are untouched

    def trough(self, wavenumber):
        x, y = spa_tool.read_spa(DATA / SAMPLE)
        return float(y[abs(x - wavenumber).argmin()])

    def test_no_peaks_key_starts_from_what_session_would_pick(self):
        self.write_entry(peaks=None)
        n = len(json.loads(self.fresh)[0]["peaks"])
        self.peak("add", "1720")
        self.assertEqual(len(self.peaks()), n + 1)

    def test_out_of_the_data_is_exit_2_and_nothing_is_written(self):
        code, out, err = self.peak("add", "1720", "99999")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("99999", err)
        self.assertEqual(self.mpath.read_bytes(), self.fresh)

    def test_json_is_one_object(self):
        code, out, _ = self.peak("add", "1720", "--json")
        self.assertEqual(code, 0)
        obj = json.loads(out)
        self.assertEqual(obj["file"], SPA)
        (c,) = obj["changes"]
        self.assertEqual((c["key"], c["old"]), ("peak", None))
        self.assertEqual(len(c["new"]), 2)
        self.assertEqual(out.count("\n"), 1)

    def test_other_keys_order_and_layout_are_kept(self):
        self.write_entry(ymin=-7, note="keep me")
        before = self.entry()
        self.peak("add", "1720")
        after = self.entry()
        self.assertEqual(list(after), list(before))
        self.assertEqual({k: v for k, v in after.items() if k != "peaks"},
                         {k: v for k, v in before.items() if k != "peaks"})
        self.assertIn('      [740.5, 52.3],\n', self.mpath.read_text(encoding="utf-8"))


class Remove(Base):
    def test_removes_the_nearest_stored_peak(self):
        code, out, _ = self.peak("remove", "830")  # 825.4 is 4.6 away, 837.0 is 7.0
        self.assertEqual(code, 0)
        self.assertNotIn(825.4, self.xs())
        self.assertIn(837.0, self.xs())
        self.assertIn("[825.4, 39.4] -> (removed)", out)
        self.assertEqual(len(self.peaks()), len(json.loads(self.fresh)[0]["peaks"]) - 1)

    def test_several_and_a_second_run_changes_nothing(self):
        self.peak("remove", "740", "1242", "3250")
        self.assertTrue({740.5, 1241.9, 3253.3}.isdisjoint(self.xs()))
        once = self.mpath.read_bytes()
        code, out, err = self.peak("remove", "740", "1242", "3250")
        self.assertEqual((code, out.strip()), (0, f"{SPA}: no change"))
        self.assertEqual(self.mpath.read_bytes(), once)

    def test_nothing_within_the_tolerance_is_a_note_not_an_error(self):
        code, out, err = self.peak("remove", "2400")  # nearest is 2018.1 or 2848.3
        self.assertEqual((code, out.strip()), (0, f"{SPA}: no change"))
        self.assertIn("2400", err)
        self.assertEqual(self.mpath.read_bytes(), self.fresh)

    def test_tolerance_is_the_snapping_window(self):
        self.assertEqual(edit.PEAK_TOLERANCE, 15.0)
        self.peak("remove", "3268")  # 14.7 from 3253.3
        self.assertNotIn(3253.3, self.xs())
        self.peak("remove", "3330")  # nothing left near
        self.assertEqual(len(self.peaks()), len(json.loads(self.fresh)[0]["peaks"]) - 1)

    def test_json_lists_the_removed_pair(self):
        code, out, _ = self.peak("remove", "3253", "--json")
        self.assertEqual(json.loads(out)["changes"],
                         [{"key": "peak", "old": [3253.3, 75.3], "new": None}])

    def test_add_then_remove_gives_the_manifest_back(self):
        self.peak("add", "1720")
        self.peak("remove", "1720")
        self.assertEqual(self.mpath.read_bytes(), self.fresh)


class Clear(Base):
    def test_clear_writes_an_empty_list_and_is_idempotent(self):
        code, out, _ = self.peak("clear")
        self.assertEqual(code, 0)
        self.assertEqual(self.peaks(), [])
        self.assertIn('"peaks": []', self.mpath.read_text(encoding="utf-8"))
        once = self.mpath.read_bytes()
        code, out, _ = self.peak("clear")
        self.assertEqual((code, out.strip()), (0, f"{SPA}: no change"))
        self.assertEqual(self.mpath.read_bytes(), once)

    def test_add_after_clear_gives_just_that_peak(self):
        self.peak("clear")
        self.peak("add", "1720")
        self.assertEqual(len(self.peaks()), 1)

    def test_removing_the_last_peak_leaves_none(self):
        self.write_entry(peaks=[[1715.0, 90.0]])
        self.peak("remove", "1715")
        self.assertEqual(self.peaks(), [])


class Auto(Base):
    def test_on_a_fresh_session_it_is_what_session_picked(self):
        code, out, _ = self.peak("auto")
        self.assertEqual((code, out.splitlines()[0]), (0, f"{SPA}: no change"))
        self.assertEqual(self.mpath.read_bytes(), self.fresh)

    def test_replaces_hand_edits_and_says_so(self):
        self.peak("remove", "740", "3253")
        self.peak("add", "1720")
        code, out, _ = self.peak("auto")
        self.assertEqual(code, 0)
        self.assertEqual(self.mpath.read_bytes(), self.fresh)
        self.assertIn("replaces the stored peaks, hand edits included", out)
        self.assertIn("dropped: 1732.7", out)
        self.assertIn("(not set) -> [740.5, 52.3]", out)

    def test_follows_the_entrys_own_sensitivity(self):
        n = len(self.peaks())
        run(self.dir, STEM, "set", "prominence=10", "threshold=20")
        self.peak("auto")
        self.assertLess(len(self.peaks()), n)
        self.assertEqual(run(self.dir, STEM, "set", "prominence=10")[2], "")
        self.assertEqual(self.peak("auto")[1].strip(),
                         f"{SPA}: no change\npeak auto replaces the stored peaks, hand edits included")

    def test_a_second_run_changes_nothing(self):
        self.peak("clear")
        self.peak("auto")
        once = self.mpath.read_bytes()
        self.peak("auto")
        self.assertEqual(self.mpath.read_bytes(), once)

    def test_absorbance_peaks_point_up_and_labels_go_above(self):
        run(self.dir, STEM, "set", "axis=Absorbance")
        self.write_entry(peaks=None)  # session picks again, as absorbance this time
        self.assertEqual(irspec("session", self.dir, "--build", "none")[0], 0)
        by_session = self.mpath.read_bytes()
        self.assertNotEqual(by_session, self.fresh)
        self.peak("clear")
        self.peak("auto")
        self.assertEqual(self.mpath.read_bytes(), by_session)
        code, out, _ = self.peak("add", "1720", "--json")
        ((x_, ly),) = [c["new"] for c in json.loads(out)["changes"]]
        x, y = spa_tool.read_spa(DATA / SAMPLE)
        self.assertGreater(ly, float(y[abs(x - x_).argmin()]))


class Arguments(Base):
    def test_bad_commands_are_exit_2_and_leave_the_file_alone(self):
        for args in (("add",), ("add", "abc"), ("remove",), ("remove", "1e999"), ("clear", "5"),
                     ("auto", "5"), ("rename", "1"), ()):
            with self.subTest(args=args):
                code, out, err = self.peak(*args)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("irspec edit:"), err)
                self.assertEqual(self.mpath.read_bytes(), self.fresh)

    def test_unknown_file_is_exit_2(self):
        code, _, err = run(self.dir, "NOPE", "peak", "clear")
        self.assertEqual(code, 2)
        self.assertIn("NOPE", err)

    def test_missing_manifest_is_exit_1(self):
        self.mpath.unlink()
        self.assertEqual(self.peak("clear")[0], 1)

    def test_no_spectrum_is_exit_2_and_names_what_is_missing(self):
        shutil.rmtree(self.dir / "SPA")
        shutil.rmtree(self.dir / "plain")
        shutil.rmtree(self.dir / "csv")
        code, out, err = self.peak("add", "1720")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("plain", err)
        self.assertEqual(self.mpath.read_bytes(), self.fresh)

    def test_without_the_spa_the_copies_are_read(self):
        shutil.rmtree(self.dir / "SPA")
        self.assertEqual(self.peak("add", "1720")[0], 0)
        shutil.rmtree(self.dir / "plain")  # csv/ is left
        self.assertEqual(self.peak("add", "3000")[0], 0)
        self.assertEqual(self.peak("add", "600")[0], 2)  # csv/ holds the whole range, plain/ stops at 650
        self.assertEqual(len(self.peaks()), len(json.loads(self.fresh)[0]["peaks"]) + 2)

    def test_a_reference_spectrum_is_read_from_its_plain_csv(self):
        ref = Path(self._work.name) / "ref"
        (ref / "jdx").mkdir(parents=True)
        shutil.copy(DATA / "phenacetin_T.jdx", ref / "jdx" / "62-44-2-IR.jdx")
        self.assertEqual(irspec("session", ref, "--build", "none")[0], 0)
        name = json.loads((ref / "manifest.json").read_text(encoding="utf-8"))[0]["name"]
        fresh = (ref / "manifest.json").read_bytes()
        code, out, err = run(ref, "62-44-2-IR", "peak", "auto")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual((ref / "manifest.json").read_bytes(), fresh)
        self.assertEqual(run(ref, "62-44-2-IR", "peak", "add", "1720")[0], 0)
        os.unlink(ref / "plain" / f"{name}.csv")
        code, out, err = run(ref, "62-44-2-IR", "peak", "clear")
        self.assertEqual((code, out), (2, ""))
        self.assertIn(f"{name}.csv", err)


class SessionKeepsTheEdit(Base):
    def test_session_after_edits_keeps_them_and_figures_json_has_them(self):
        self.peak("remove", "740", "3253")
        self.peak("add", "1720", "3000")
        edited = self.peaks()
        manifest = self.mpath.read_bytes()
        code, out, err = irspec("session", self.dir, "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.mpath.read_bytes(), manifest)
        figures = json.loads((self.dir / "figures.json").read_text(encoding="utf-8"))
        figure = figures["figures"][0] if isinstance(figures, dict) else figures[0]
        self.assertEqual([list(p) for p in figure["peaks"]], edited)
        self.assertNotIn(740.5, [p[0] for p in figure["peaks"]])
        md = (self.dir / "ir_session.md").read_text(encoding="utf-8")
        label = next(p[1] for p in edited if p[0] == 1732.7)
        self.assertIn(f"1732.7/{label}", md.replace(" ", ""))
        self.assertNotIn("740.5/", md)

    def test_session_after_clear_draws_no_peaks(self):
        self.peak("clear")
        code, out, err = irspec("session", self.dir, "--build", "none")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.peaks(), [])
        figures = json.loads((self.dir / "figures.json").read_text(encoding="utf-8"))
        figure = figures["figures"][0] if isinstance(figures, dict) else figures[0]
        self.assertEqual(figure["peaks"], [])
        self.assertIn("peaks=0", out)


if __name__ == "__main__":
    unittest.main()
