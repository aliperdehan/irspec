"""Differential test: moving the scripts into the package must change nothing.

Every case runs the same command twice on identical copies of the inputs --
once as the copied script in legacy/ (the nulabreport originals, byte for
byte), once as `python -m irspec.<module>` from src/ -- and compares the exit
code, stdout, stderr and every file either run left behind, byte for byte.
A case where both runs fail would also "match", so each must exit 0.

Inputs are the author's own phenacetin spectrum and the JCAMP-DX files made
from it (tests/make_fixtures.py); nothing third-party.

    python3 -m unittest discover -s tests -v

Optional (skipped when unset): IRSPEC_SDBS_IMAGE=path/to/an SDBS plot image,
to run ir_digitize on a real picture; it is not published here.
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
SPA = "PHENACETIN_CRUDE_LR1-2.SPA"


def run(kind, module, argv, cwd):
    """kind 'legacy': python legacy/<module>.py ; kind 'pkg': python -m irspec.<module>."""
    if kind == "legacy":
        cmd = [sys.executable, str(ROOT / "legacy" / f"{module}.py"), *argv]
        env = os.environ.copy()
    else:
        cmd = [sys.executable, "-m", f"irspec.{module}", *argv]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}


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
    # an Absorbance plain CSV, made the same way for both runs (legacy writer)
    put(d, "phenacetin_A.jdx")
    r = run("legacy", "jdx_tool", ["convert", "phenacetin_A.jdx", "--out", "a.csv",
                                   "--plain-out", "a_plain.csv"], d)
    assert r.returncode == 0, r.stderr
    (d / "a.csv").unlink()
    (d / "phenacetin_A.jdx").unlink()


def setup_corr(d):
    put(d, "golden_plain.csv", "phenacetin_T.jdx")
    r = run("legacy", "jdx_tool", ["convert", "phenacetin_T.jdx", "--out", "t.csv",
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
    def check(self, name, module, setup, argv):
        results = {}
        with tempfile.TemporaryDirectory() as tl, tempfile.TemporaryDirectory() as tp:
            for kind, tmp in (("legacy", Path(tl).resolve()), ("pkg", Path(tp).resolve())):
                setup(tmp)
                r = run(kind, module, argv, tmp)
                self.assertEqual(r.returncode, 0, f"{name} [{kind}] failed:\n{r.stderr}")
                clean = lambda s: s.replace(str(tmp), "<TMP>")
                results[kind] = (clean(r.stdout), clean(r.stderr), snapshot(tmp))
        lo, po = results["legacy"], results["pkg"]
        self.assertEqual(lo[0], po[0], f"{name}: stdout differs")
        self.assertEqual(lo[1], po[1], f"{name}: stderr differs")
        self.assertEqual(sorted(lo[2]), sorted(po[2]), f"{name}: different files written")
        for rel in lo[2]:
            self.assertEqual(lo[2][rel], po[2][rel], f"{name}: {rel} differs")
        self.assertTrue(lo[2], f"{name}: nothing to compare")

    def test_every_case(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                self.check(*case)

    @unittest.skipUnless(os.environ.get("IRSPEC_SDBS_IMAGE"), "set IRSPEC_SDBS_IMAGE to run")
    def test_ir_digitize_on_a_real_sdbs_image(self):
        img = Path(os.environ["IRSPEC_SDBS_IMAGE"])

        def setup(d):
            (d / "img").mkdir()
            shutil.copy(img, d / "img" / img.name)
        self.check("ir_digitize", "ir_digitize", setup,
                   ["convert", f"img/{img.name}", "--name", "X", "--out", "csv/X.csv",
                    "--plain-out", "plain/X.csv", "--overlay", "check/X.png"])


if __name__ == "__main__":
    unittest.main()
