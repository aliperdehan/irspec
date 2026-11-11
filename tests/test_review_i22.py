"""Output collisions are resolved before processing, stably across re-runs."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from irspec import ir_organize, session

DATA = Path(__file__).parent / "data"
SPA = DATA / "PHENACETIN_CRUDE_LR1-2.SPA"


class SessionNames(unittest.TestCase):
    def test_uploads_references_and_plain_suffix_collisions(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "SPA").mkdir()
            (folder / "jdx").mkdir()
            files = ["SPA/1782821956657_reagent.SPA", "SPA/1782821956658_reagent.SPA",
                     "SPA/A.SPA", "jdx/one.jdx", "jdx/two.jdx", "jdx/three.jdx"]
            for f in files[:3]:
                shutil.copy(SPA, folder / f)
            for f in files[3:]:
                shutil.copy(DATA / "phenacetin_T.jdx", folder / f)
            entries = [{"file": f, "peaks": []} for f in files]
            for e, name in zip(entries[3:], ["gas", "gas", "A_plain"]):
                e["name"] = name
            (folder / "manifest.json").write_text(json.dumps(entries))
            note = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(note):
                figs = session.run(d, build="none")
            self.assertEqual(len({f.csv for f in figs}), len(files))
            self.assertEqual(len(list((folder / "csv").glob("*.csv"))), len(files))
            for f in files:
                self.assertIn(f, note.getvalue())
            saved = json.loads((folder / "manifest.json").read_text())
            expected = {e["file"]: session.planned_names(d, e) for e in saved}
            (folder / "manifest.json").write_text(json.dumps(saved[::-1]))
            with contextlib.redirect_stdout(io.StringIO()):
                session.run(d, build="none")
            again = json.loads((folder / "manifest.json").read_text())
            self.assertEqual({e["file"]: session.planned_names(d, e) for e in again}, expected)

    def test_legacy_preflight_and_duplicate_refusal(self):
        entries = [{"file": f"SPA/{p}_reagent.SPA"} for p in (1782821956657, 1782821956658)]
        with contextlib.redirect_stderr(io.StringIO()):
            ir_organize.allocate_output_names(entries)
        self.assertEqual(len({e["name"] for e in entries}), 2)
        with self.assertRaisesRegex(ValueError, "same input file twice"):
            ir_organize.allocate_output_names([entries[0], entries[0]])
        with self.assertRaisesRegex(ValueError, "single filename component"):
            ir_organize.allocate_output_names([{"file": "SPA/s.SPA", "name": "../escape"}])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "SPA").mkdir()
            shutil.copy(SPA, Path(d) / "SPA" / "s.SPA")
            (Path(d) / "manifest.json").write_text(json.dumps([{"file": "SPA/s.SPA"}] * 2))
            with self.assertRaisesRegex(session.SessionError, "same input file twice"):
                session.run(d, build="none")
            code, _, err = session.call("ir_organize", [d, "--no-pdf"])
            self.assertNotEqual(code, 0)
            self.assertIn("same input file twice", err)
            self.assertNotIn("Traceback", err)
