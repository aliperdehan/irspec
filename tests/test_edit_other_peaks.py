"""Peak editing uses each kind's stored requests and units."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OtherPeaks(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        (self.folder / "plain").mkdir()
        (self.folder / "plain" / "scan.csv").write_text(
            "wavelength,absorbance\n200,0\n250,1\n300,0.5\n350,2\n400,0\n",
            encoding="utf-8",
        )

    def save(self, entry):
        (self.folder / "manifest.json").write_text(
            json.dumps([entry]), encoding="utf-8"
        )

    def run_edit(self, *args):
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "irspec",
                "edit",
                str(self.folder),
                "scan",
                "peak",
                *args,
                "--json",
            ],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        obj = json.loads(r.stdout)
        entry = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8"))[
            0
        ]
        return obj, entry

    def test_uvvis_add_exact_position_and_frame_span(self):
        self.save(
            {
                "file": "uv/scan.vspd",
                "kind": "uvvis",
                "xmin": 250,
                "xmax": 300,
                "peaks": [],
            }
        )
        obj, e = self.run_edit("add", "275.123")
        self.assertEqual(e["peaks"], [[275.123, 0.7788]])
        self.assertEqual(
            obj["changes"], [{"key": "peak", "old": None, "new": [275.123, 0.7788]}]
        )
        obj, e = self.run_edit("add", "275.123")
        self.assertEqual(obj["changes"], [])

    def test_uvvis_remove_clear_auto(self):
        self.save(
            {
                "file": "uv/scan.vspd",
                "kind": "uvvis",
                "peaks": [[250, 1.12], [300, 0.62]],
            }
        )
        _, e = self.run_edit("remove", "256")
        self.assertEqual(len(e["peaks"]), 2)
        obj, e = self.run_edit("remove", "255")
        self.assertEqual(e["peaks"], [[300, 0.62]])
        self.assertEqual(obj["changes"][0]["old"], [250, 1.12])
        _, e = self.run_edit("clear")
        self.assertEqual(e["peaks"], [])
        obj, e = self.run_edit("auto")
        self.assertNotIn("peaks", e)
        self.assertEqual(obj["changes"], [{"key": "peaks", "old": [], "new": None}])

    def test_gc_requests_and_solvent(self):
        self.save({"file": "gc/scan.RAW", "kind": "gc", "solvent": "3.3=Acetone"})
        obj, e = self.run_edit("add", "2.84=Methanol", "3.02")
        self.assertEqual(e["compounds"], "2.84=Methanol,3.02")
        self.assertEqual(
            obj["changes"][0], {"key": "peak", "old": None, "new": [2.84, "Methanol"]}
        )
        _, e = self.run_edit("remove", "2.75")
        self.assertEqual(e["compounds"], "2.84=Methanol,3.02")
        _, e = self.run_edit("remove", "2.8")
        self.assertEqual(e["compounds"], "3.02")
        _, e = self.run_edit("clear")
        self.assertNotIn("compounds", e)
        self.assertEqual(e["solvent"], "3.3=Acetone")
        self.run_edit("add", "2.84=Methanol")
        _, e = self.run_edit("auto")
        self.assertNotIn("compounds", e)

    def test_uvvis_remove_needs_no_trace(self):
        self.save(
            {
                "file": "uv/scan.vspd",
                "name": "scan",
                "kind": "uvvis",
                "peaks": [[275, 1]],
            }
        )
        (self.folder / "plain" / "scan.csv").unlink()
        _, entry = self.run_edit("remove", "275")
        self.assertEqual(entry["peaks"], [])

    def test_gc_add_preserves_time_precision(self):
        self.save({"file": "gc/scan.RAW", "kind": "gc"})
        _, entry = self.run_edit("add", "2.84000123=Named")
        self.assertEqual(entry["compounds"], "2.84000123=Named")

    def test_gc_custom_window(self):
        self.save(
            {
                "file": "gc/scan.RAW",
                "kind": "gc",
                "window": 0.02,
                "compounds": "2.84=Methanol,3.02=Ethanol",
            }
        )
        _, e = self.run_edit("remove", "2.8")
        self.assertEqual(e["compounds"], "2.84=Methanol,3.02=Ethanol")
        _, e = self.run_edit("remove", "2.83")
        self.assertEqual(e["compounds"], "3.02=Ethanol")

    def test_invalid_named_ir_and_gc_nonfinite_leave_bytes(self):
        for kind, file, value in [
            ("ir", "scan.SPA", "2.84=Methanol"),
            ("gc", "gc/scan.RAW", "nan=Methanol"),
        ]:
            self.save({"file": file, "kind": kind})
            before = (self.folder / "manifest.json").read_bytes()
            r = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "irspec",
                    "edit",
                    str(self.folder),
                    "scan",
                    "peak",
                    "add",
                    value,
                ],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertEqual((self.folder / "manifest.json").read_bytes(), before)
