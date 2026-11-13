"""Record what nulabreport's gc_tool.py does on a .RAW, for tests/test_gc_tool.py.

    python3 tests/record_gc.py ~/dev/tex/nulabreport/tools/gc_tool.py tests/data/gc_lab4.RAW tests/data/gc_expected.json

Each case runs the tool in a fresh folder holding the .RAW as gc_lab4.RAW and keeps the exit
code, stdout, stderr (folder -> <TMP>, tool path -> <TOOL>) and the sha256 of every file it wrote.
Run it on the original and on the anonymised file: the two recordings must be identical.
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

TOOL, RAW, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
A = "2.5,4.5,6.6,8.0,8.5,8.97,9.6"
PEAKS = "2.84=Methanol,3.02=Ethanol,3.65=1-Propanol,5.31=1-Butanol,9.05=1-Pentanol"
KNOWN = "Methanol=6.67,Ethanol=13.33,1-Propanol=20.00,1-Butanol=26.67,1-Pentanol=33.33"
FULL = {"raw": "gc_lab4.RAW", "title": "Group 1", "peaks": PEAKS, "solvent": "3.30=Acetone", "baseline": A}
CROP = {"raw": "gc_lab4.RAW", "title": "Group 1 (trimmed, baseline-corrected, acetone removed)",
        "peaks": PEAKS, "baseline": A, "crop": {"xmin": 2.6, "xmax": 9.6, "correct": True, "exclude": "3.24-3.46"}}
# (name, argv, files written before the run: name -> json)
CASES = [
    ("info", ["info", "gc_lab4.RAW"], {}),
    ("info_brief", ["info", "gc_lab4.RAW", "--brief"], {}),
    ("convert", ["convert", "gc_lab4.RAW"], {}),
    ("convert_out", ["convert", "gc_lab4.RAW", "--out", "out/run"], {}),
    ("verify", ["verify", "gc_lab4.RAW", "ref.csv"], {}),
    ("crop_lr4", ["crop", "gc_lab4.RAW", "--out", "plain/gc_lab4_crop.csv", "--xmin", "2.6", "--xmax", "9.6",
                  "--correct", "--baseline", A, "--exclude", "3.24-3.46"], {}),
    ("crop_auto", ["crop", "gc_lab4.RAW", "--out", "c.csv", "--correct"], {}),
    ("crop_flat_trim", ["crop", "gc_lab4.RAW", "--out", "c.csv", "--correct", "--baseline", "flat:0.5",
                        "--xmin", "2", "--exclude", "3.2-3.5,11.6-12"], {}),
    ("integrate_lr4_full", ["integrate", "gc_lab4.RAW", "--peaks", PEAKS, "--solvent", "3.30=Acetone",
                            "--baseline", A, "--known", KNOWN], {}),
    ("integrate_lr4_axis", ["integrate", "gc_lab4.RAW", "--peaks", PEAKS, "--baseline", A,
                            "--xmin", "2.6", "--xmax", "9.6", "--ymax", "700000"], {}),
    ("integrate_auto", ["integrate", "gc_lab4.RAW"], {}),
    ("integrate_flat", ["integrate", "gc_lab4.RAW", "--baseline", "flat", "--min-prominence", "40", "--landscape"], {}),
    ("integrate_stackpanel", ["integrate", "gc_lab4.RAW", "--plot-size", "12.5,4", "--window", "0.05",
                              "--peaks", PEAKS], {}),
    ("batch_full", ["batch", "--manifest", "m.json", "--out-dir", "o", "--md", "o/gc.md"], {"m.json": [FULL]}),
    ("batch_crop", ["batch", "--manifest", "m.json", "--out-dir", "o", "--md", "o/gc.md"], {"m.json": [CROP]}),
    ("batch_raw", ["batch", "--raw", "gc_lab4.RAW", "--titles", "Run_1 & 50%", "--out-dir", ".", "--md", "b.md"], {}),
    ("batch_twice", ["batch", "--manifest", "m.json", "--out-dir", "o", "--md", "o/gc.md"], {"m.json": [FULL, CROP]}),
    ("not_raw", ["info", "m.json"], {"m.json": []}),
]


def snapshot(d):
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


def make_ref(d):   # the reference CSV for verify: convert's own archival CSV
    subprocess.run([sys.executable, TOOL, "convert", "gc_lab4.RAW", "--out", "ref"], cwd=d, check=True,
                   capture_output=True)
    os.remove(d / "ref_plain.csv")


out = {}
for name, argv, files in CASES:
    with tempfile.TemporaryDirectory() as t:
        d = Path(t).resolve()
        shutil.copy(RAW, d / "gc_lab4.RAW")
        if name == "verify":
            make_ref(d)
        for fn, obj in files.items():
            (d / fn).write_text(json.dumps(obj), encoding="utf-8")
        before = snapshot(d)
        r = subprocess.run([sys.executable, TOOL, *argv], cwd=d, capture_output=True, text=True,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        after = snapshot(d)
        err = r.stderr.replace(TOOL, "<TOOL>").replace(str(d), "<TMP>")
        out[name] = {"argv": argv, "files_before": files, "code": r.returncode, "stdout": r.stdout.replace(str(d), "<TMP>"),
                     "stderr": err, "files": {k: v for k, v in after.items() if before.get(k) != v}}
json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print({k: (v["code"], len(v["files"])) for k, v in out.items()})
