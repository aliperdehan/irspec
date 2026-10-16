"""Golden test: spa_tool must keep producing exactly what the
nulabreport tools produced for the author's own phenacetin spectrum.

tests/data/PHENACETIN_CRUDE_LR1-2.SPA is the author's own OMNIC file (diamond
ATR, LR1-2 crude product, 1 Sept 2026); golden_archival.csv / golden_plain.csv
are the two CSVs of the house convention that nulabreport's pipeline built from
it and the LR1-2 and LR7 reports used.  Run from the repo root:

    python3 -m unittest discover -s tests -v
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data"
STEM = "PHENACETIN_CRUDE_LR1-2"


class SpaConvertGolden(unittest.TestCase):
    def test_spa_to_house_csv_pair_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copy(DATA / f"{STEM}.SPA", td)
            r = subprocess.run(
                [sys.executable, "-m", "irspec.spa_tool", "convert", f"{STEM}.SPA"],
                cwd=td, capture_output=True, text=True,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((td / f"{STEM}.csv").read_bytes(),
                             (DATA / "golden_archival.csv").read_bytes(),
                             "archival CSV changed")
            self.assertEqual((td / f"{STEM}_plain.csv").read_bytes(),
                             (DATA / "golden_plain.csv").read_bytes(),
                             "plain CSV changed")


if __name__ == "__main__":
    unittest.main()
