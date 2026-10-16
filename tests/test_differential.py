"""Differential test: moving the scripts into the package must change nothing.

Every case runs one command on a fresh copy of the inputs as `python -m irspec.<module>`
and compares the exit code, stdout, stderr and the sha256 of every file it left behind
with what the original scripts (the nulabreport tools, copied byte for byte into
legacy/ while the package was made) did on the same inputs. That outcome is recorded in
tests/data/differential_expected.json. A case where the run fails would also "match" a
recorded failure, so each must exit 0.

To record again from the originals (they are in the git history, tag legacy-oracle):

    git archive legacy-oracle legacy | tar -x -C SOMEWHERE
    python3 tests/test_differential.py --record SOMEWHERE/legacy

Inputs are the author's own phenacetin spectrum and the JCAMP-DX files made
from it (tests/make_fixtures.py); nothing third-party.

    python3 -m unittest discover -s tests -v
"""
import hashlib
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
LEGACY = ROOT / "legacy"      # only for --record
SPA = "PHENACETIN_CRUDE_LR1-2.SPA"


def run(kind, module, argv, cwd):
    """kind 'legacy': python legacy/<module>.py ; kind 'pkg': python -m irspec.<module>."""
    if kind == "legacy":
        cmd = [sys.executable, str(LEGACY / f"{module}.py"), *argv]
        env = os.environ.copy()
    else:
        cmd = [sys.executable, "-m", f"irspec.{module}", *argv]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}


EXPECTED = DATA / "differential_expected.json"


def outcome(kind, module, setup, argv):
    """Run one case in a fresh folder: exit code, stdout, stderr, and the sha256 of every file
    left behind (folder names in the text replaced by <TMP>)."""
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t).resolve()
        setup(tmp)
        r = run(kind, module, argv, tmp)
        clean = lambda text: text.replace(str(tmp), "<TMP>")
        files = {k: hashlib.sha256(v).hexdigest() for k, v in snapshot(tmp).items()}
        return {"returncode": r.returncode, "stdout": clean(r.stdout), "stderr": clean(r.stderr),
                "files": files}


def put(folder, *names, rename=None):
    for n in names:
        shutil.copy(DATA / n, folder / (rename or n))


def setup_none(d):
    pass


def setup_spa(d):
    put(d, SPA)


def setup_jdx(d):
    put(d, "phenacetin_T.jdx", "phenacetin_A.jdx")


def setup_peaks_inputs(d):
    put(d, SPA, "phenacetin_T.jdx", "phenacetin_A.jdx")
    put(d, "golden_plain.csv")


def setup_batch_jdx(d):
    (d / "jdx").mkdir()
    shutil.copy(DATA / "phenacetin_T.jdx", d / "jdx" / "62-44-2-IR.jdx")
    shutil.copy(DATA / "phenacetin_A.jdx", d / "jdx" / "50-00-0-IR.jdx")
    (d / "cas_names.json").write_text(json.dumps(
        {"62-44-2": "PHENACETIN_T", "50-00-0": "PHENACETIN_A"}))


def setup_a2t(d):
    # an Absorbance plain CSV, made by the package's own writer
    put(d, "phenacetin_A.jdx")
    r = run("pkg", "jdx_tool", ["convert", "phenacetin_A.jdx", "--out", "a.csv",
                                   "--plain-out", "a_plain.csv"], d)
    assert r.returncode == 0, r.stderr
    (d / "a.csv").unlink()
    (d / "phenacetin_A.jdx").unlink()


def setup_corr(d):
    put(d, "golden_plain.csv", "phenacetin_T.jdx")
    r = run("pkg", "jdx_tool", ["convert", "phenacetin_T.jdx", "--out", "t.csv",
                                   "--plain-out", "t_plain.csv"], d)
    assert r.returncode == 0, r.stderr
    (d / "t.csv").unlink()


def setup_session(d):
    (d / "session_29-09").mkdir()
    put(d / "session_29-09", SPA)
    shutil.copy(DATA / "phenacetin_T.jdx", d / "session_29-09" / "62-44-2-IR.jdx")


# (case name, module, setup, argv)
CASES = [
    ("spa_convert_auto", "spa_tool", setup_spa, ["convert", SPA]),
    ("spa_convert_manual", "spa_tool", setup_spa,
     ["convert", SPA, "--mode", "manual", "--peaks", "1241.9,1511,2980"]),
    ("spa_batch_md", "spa_tool", setup_spa,
     ["batch", "--spa", SPA, "--titles", "Phenacetin (crude)", "--out-dir", "out",
      "--md", "out.md"]),
    ("peaks_spa", "spa_peaks", setup_peaks_inputs, [SPA]),
    ("peaks_plain_csv", "spa_peaks", setup_peaks_inputs, ["golden_plain.csv"]),
    ("peaks_jdx_transmittance", "spa_peaks", setup_peaks_inputs, ["phenacetin_T.jdx"]),
    ("peaks_jdx_absorbance", "spa_peaks", setup_peaks_inputs, ["phenacetin_A.jdx"]),
    ("jdx_convert_transmittance", "jdx_tool", setup_jdx,
     ["convert", "phenacetin_T.jdx", "--out", "csv/T.csv", "--plain-out", "plain/T.csv"]),
    ("jdx_convert_absorbance", "jdx_tool", setup_jdx,
     ["convert", "phenacetin_A.jdx", "--name", "PHENACETIN_A", "--out", "csv/A.csv",
      "--plain-out", "plain/A.csv"]),
    ("jdx_batch", "jdx_tool", setup_batch_jdx,
     ["batch", "jdx", "--out-dir", "csv", "--plain-dir", "plain",
      "--name-map", "cas_names.json"]),
    ("absorbance_to_transmittance", "absorbance_to_transmittance", setup_a2t,
     ["a_plain.csv", "--out", "t_from_a.csv"]),
    ("transmittance_to_absorbance", "absorbance_to_transmittance", setup_corr,
     ["golden_plain.csv", "--out", "a_from_t.csv", "--to", "absorbance"]),
    ("absorptivity_to_absorbance", "absorptivity_to_absorbance",
     lambda d: put(d, "phenacetin_quantir.jdx"),
     ["phenacetin_quantir.jdx", "--name", "PHENACETIN_GAS", "--out", "csv/Q.csv",
      "--plain-out", "plain/Q.csv", "--peak-a", "1"]),
    ("ir_corr", "ir_corr", setup_corr, ["golden_plain.csv", "t_plain.csv"]),
    ("organize_dry_run", "ir_organize", setup_session,
     ["session_29-09", "--dry-run", "--no-pdf"]),
    ("organize_no_pdf", "ir_organize", setup_session, ["session_29-09", "--no-pdf"]),
]


class Differential(unittest.TestCase):
    def test_every_case_against_the_recorded_outcome(self):
        """The same sixteen commands, against what the original scripts did (EXPECTED, recorded
        by `python3 tests/test_differential.py --record DIR`)."""
        expected = json.loads(EXPECTED.read_text())
        self.assertEqual(sorted(expected), sorted(c[0] for c in CASES))
        for name, module, setup, argv in CASES:
            with self.subTest(case=name):
                got = outcome("pkg", module, setup, argv)
                self.assertEqual(got["returncode"], 0, got["stderr"])
                want = expected[name]
                self.assertEqual(got["stdout"], want["stdout"], f"{name}: stdout differs")
                self.assertEqual(got["stderr"], want["stderr"], f"{name}: stderr differs")
                self.assertEqual(sorted(got["files"]), sorted(want["files"]), f"{name}: files written")
                for rel in want["files"]:
                    self.assertEqual(got["files"][rel], want["files"][rel], f"{name}: {rel} differs")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--record"]:
        LEGACY = Path(sys.argv[2]).resolve()
        out = {c[0]: outcome("legacy", *c[1:]) for c in CASES}
        EXPECTED.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(f"recorded {len(out)} cases from {LEGACY} into {EXPECTED.relative_to(ROOT)}")
    else:
        unittest.main()
