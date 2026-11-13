"""Replay nulabreport's GC output, including every file written."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from irspec import cli


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
RAW = "gc_lab4.RAW"
CASES = json.loads((DATA / "gc_expected.json").read_text(encoding="utf-8"))


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file()}


class GcTool(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name).resolve()
        shutil.copyfile(DATA / RAW, self.folder / RAW)
        self.env = {**os.environ, "PYTHONPATH": str(ROOT / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1"}

    def run_gc(self, argv):
        return subprocess.run([sys.executable, "-m", "irspec", "gc", *argv],
                              cwd=self.folder, env=self.env, capture_output=True,
                              text=True, encoding="utf-8")

    def replay(self, name):
        case = CASES[name]
        for rel, value in case["files_before"].items():
            path = self.folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        if name == "verify":
            result = self.run_gc(["convert", RAW, "--out", "ref"])
            self.assertEqual(result.returncode, 0, result.stderr)
            (self.folder / "ref_plain.csv").unlink()
        before = snapshot(self.folder)
        result = self.run_gc(case["argv"])

        def normalise(value):
            return value.replace(str(self.folder), "<TMP>")

        self.assertEqual(result.returncode, case["code"], result.stderr)
        self.assertEqual(normalise(result.stdout), normalise(case["stdout"]))
        self.assertEqual(normalise(result.stderr), normalise(case["stderr"]))
        changed = {p: digest for p, digest in snapshot(self.folder).items()
                   if before.get(p) != digest}
        self.assertEqual(changed, case["files"])

    def test_crop_lr4(self):
        """The author's LR4 figure: trimmed to 2.6-9.6 min, with the rising
        baseline under the oven ramp flattened through anchors at
        2.5,4.5,6.6,8.0,8.5,8.97,9.6 min and the acetone front at
        3.24-3.46 min removed as a gap.
        """
        self.replay("crop_lr4")

    def test_info_in_process(self):
        out = io.StringIO()
        path = str(self.folder / RAW)
        with mock.patch.object(sys, "argv", list(sys.argv)), contextlib.redirect_stdout(out):
            cli.main(["gc", "info", path, "--brief"])
        self.assertEqual(out.getvalue().replace(path, RAW), CASES["info_brief"]["stdout"])


def recorded_test(name):
    def test(self):
        self.replay(name)
    test.__doc__ = "Replay the recorded %s command." % name
    return test


for case_name in CASES:
    if case_name != "crop_lr4":
        setattr(GcTool, "test_" + case_name, recorded_test(case_name))


if __name__ == "__main__":
    unittest.main()
