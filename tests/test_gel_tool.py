"""Original gel recordings and the demo smoke checks on synthetic planted masses."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from make_gel import LADDER, LANES, PLANTED
from record_gel_tool import prepare
from tool_recording import replay

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (Path(__file__).parent / "data" / "gel_tool_expected.json").read_text(
        encoding="utf-8"
    )
)


class Recorded(unittest.TestCase):
    pass


def recorded_test(name):
    def test(self):
        replay(self, "gel", CASES, prepare, name)

    return test


for name in CASES:
    setattr(Recorded, "test_" + name, recorded_test(name))


class SyntheticSmoke(unittest.TestCase):
    def check_gel(self, mirror):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            prepare(folder, "all_right" if mirror else "all_left")
            result = subprocess.run(
                [sys.executable, "-m", "irspec", "gel", "all", "gel.json"],
                cwd=folder,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            numbers = "2, 3, 5, 6" if mirror else "1, 2, 4, 5"
            self.assertIn("humps are lanes " + numbers + ";", result.stdout)
            cfg = json.loads((folder / "gel.json").read_text(encoding="utf-8"))
            self.assertEqual(
                sorted(float(k) for k in cfg["ladder"]["assign"]), sorted(LADDER)
            )
            with (folder / "estimates.csv").open(encoding="utf-8") as f:
                estimates = [r for r in csv.DictReader(f) if r["at_front"] == "0"]
            for lane, masses in PLANTED.items():
                lane = str(LANES + 1 - int(lane)) if mirror else lane
                got = [float(r["est_kDa"]) for r in estimates if r["lane"] == lane]
                self.assertTrue(got, "missing planted sample lane " + lane)
                for mass in masses:
                    nearest = min(got, key=lambda value: abs(value - mass))
                    self.assertLess(abs(nearest - mass) / mass, 0.01)
            with (folder / "gel_labels.csv").open(encoding="utf-8") as f:
                marks = [r for r in csv.DictReader(f) if r["kind"] == "mark"]
            self.assertEqual(len(marks), 9)
            self.assertEqual(
                {r["x"] for r in marks}, {"1.0000" if mirror else "0.0000"}
            )
            self.assertIn(
                "# fit", (folder / "calibration.csv").read_text(encoding="utf-8")
            )

    def test_ladder_left(self):
        self.check_gel(False)

    def test_ladder_right(self):
        self.check_gel(True)


if __name__ == "__main__":
    unittest.main()
