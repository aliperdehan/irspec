"""The registry of plot kinds (kinds.py): IR is its one entry, and session, preview, edit, the
TeX writer and matplotlib go through it. The proof that moving IR into it changed nothing is the
rest of the suite (differential, oracle, every IR test) plus a byte comparison of one session
folder's outputs made before and after; this file checks the registry itself, and that a kind's
own functions and geometry are the ones used, with a made-up second kind.
"""
import contextlib
import dataclasses
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from irspec import cli, edit, ir_organize, kinds, layout, preview, session, texout  # noqa: E402
from irspec.figure import Figure  # noqa: E402

DATA = ROOT / "tests" / "data"
SAMPLE = "PHENACETIN_CRUDE_LR1-2.SPA"
CALLS = []


def fake_process(folder, e, csv_dir, plain_dir):
    """An entry with "fail" stops; else a 200-700 nm band written as session's CSVs."""
    CALLS.append(("process", e["file"]))
    if e.get("fail"):
        raise session.SessionError("fake process called")
    stem = Path(e["file"]).stem
    x = np.linspace(200.0, 700.0, 101)
    for p in (Path(csv_dir) / f"{stem}.csv", Path(plain_dir) / f"{stem}.csv"):
        np.savetxt(p, np.column_stack([x, np.exp(-((x - 450) / 40) ** 2)]), delimiter=",",
                   header="wavelength,absorbance", comments="")
    return {"title": e.get("title") or stem, "stem": stem, "axis_label": "Absorbance",
            "axis_md": "Absorbance", "peaklist": "450.0/1.1", "ymin": None, "n_peaks": 1,
            "ymax": e.get("ymax"), "xmin": e.get("xmin"), "xmax": e.get("xmax"),
            "archival_path": str(Path(csv_dir) / f"{stem}.csv"),
            "plain_path": str(Path(plain_dir) / f"{stem}.csv")}


def fake_load(path, entry):
    CALLS.append(("load", path))
    x = np.linspace(200.0, 700.0, 101)
    return x, np.exp(-((x - 450.0) / 40.0) ** 2), "Absorbance", True, "fake", None


def fake_load_saved(folder, entry):
    CALLS.append(("load_saved", entry["file"]))
    raise edit.EditError("fake load_saved called")


# A second kind, ascending x like a UV-Vis spectrum, with its own functions.
FAKE = dataclasses.replace(
    kinds.IR, name="fake", x_column="wavelength", x_label="Wavelength / nm", x_unit="nm",
    xlim=(200.0, 700.0), x_ticks=(200.0, 300.0, 400.0, 500.0, 600.0, 700.0), x_minor=50.0,
    pad=(0.04, 0.08), macro="fakespectrum", folders=(("fake", (".fake",)),),
    process=f"{__name__}:fake_process", load=f"{__name__}:fake_load",
    load_saved=f"{__name__}:fake_load_saved")


@contextlib.contextmanager
def registered(kind):
    kinds.REGISTRY[kind.name] = kind
    CALLS.clear()
    try:
        yield
    finally:
        del kinds.REGISTRY[kind.name]


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cli.main([str(a) for a in argv])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
            if isinstance(e.code, str):
                err.write(e.code + "\n")
    return code, out.getvalue(), err.getvalue()


def ir_session(d, **entry_keys):
    f = Path(d) / "lab_29-09"
    (f / "SPA").mkdir(parents=True)
    shutil.copy(DATA / SAMPLE, f / "SPA")
    with contextlib.redirect_stdout(io.StringIO()):
        session.run(str(f), build="none")
    if entry_keys:
        mp = f / "manifest.json"
        entries = json.loads(mp.read_text(encoding="utf-8"))
        entries[0].update(entry_keys)
        mp.write_text(json.dumps(entries), encoding="utf-8")
    return f


class Registry(unittest.TestCase):
    def test_every_function_of_every_kind_resolves(self):
        for k in kinds.all_kinds():
            for role in kinds.ROLES:
                with self.subTest(kind=k.name, role=role):
                    self.assertTrue(callable(k.function(role)))

    def test_ir_is_the_default_and_absent_means_ir(self):
        self.assertIs(kinds.DEFAULT, kinds.IR)
        self.assertIs(kinds.of({}), kinds.IR)
        self.assertIs(kinds.of(None), kinds.IR)
        self.assertIs(kinds.of({"kind": "ir"}), kinds.IR)

    def test_an_unknown_kind_is_refused(self):
        for bad in ("uvvis", "", None, ["ir"], 3):
            with self.subTest(kind=bad), self.assertRaises(ValueError) as cm:
                kinds.of({"kind": bad})
            self.assertIn("this irspec draws only 'ir' figures", str(cm.exception))

    def test_the_old_names_are_irs_numbers(self):
        # layout's constants (the R script's test reads them), ir_organize's and session's
        # file types: aliases of the IR kind, so there is one place to change them
        self.assertEqual(layout.XLIM, kinds.IR.xlim)
        self.assertEqual((layout.LOWER_PAD, layout.UPPER_PAD), kinds.IR.pad)
        self.assertEqual(layout.X_MINOR, kinds.IR.x_minor)
        self.assertEqual(tuple(np.arange(4000, 999, -layout.X_MAJOR)), kinds.IR.x_ticks)
        self.assertEqual(session.KIND_DIRS, kinds.IR.folders)
        self.assertEqual((ir_organize.SPA_EXT, ir_organize.JDX_EXT, session.IMG_EXT),
                         tuple(exts for _, exts in kinds.IR.folders))


class FigureAndTex(unittest.TestCase):
    def test_kind_is_written_only_when_not_ir(self):
        fig = Figure.from_entry({"csv": "plain/a.csv", "title": "t"})
        self.assertEqual(fig.kind, "ir")
        self.assertNotIn("kind", fig.to_entry())
        with registered(FAKE):
            fig = Figure.from_entry({"csv": "plain/a.csv", "title": "t", "kind": "fake"})
            self.assertEqual(fig.to_entry()["kind"], "fake")
            self.assertTrue(texout._block(fig).startswith("\\fakespectrum\n"))
        self.assertTrue(texout._block(Figure(csv="a.csv", title="t")).startswith("\\irspectrum\n"))
        with self.assertRaises(ValueError):
            Figure.from_entry({"csv": "plain/a.csv", "kind": "fake"})   # not registered now

    def test_layout_takes_the_kinds_frame(self):
        self.assertEqual(layout.xlimits(kind=FAKE), (200.0, 700.0))
        lo, hi = layout.ylimits(np.array([0.0, 1.0]), kind=FAKE)
        self.assertAlmostEqual(lo, -0.04)
        self.assertAlmostEqual(hi, 1.08)
        xw, _ = layout.window(np.array([100.0, 300.0, 800.0]), np.ones(3), FAKE)
        self.assertEqual(list(xw), [300.0])


class Dispatch(unittest.TestCase):
    """Each module calls the entry's kind's own function, not IR's."""

    def test_session_process(self):
        with registered(FAKE), tempfile.TemporaryDirectory() as d:
            with self.assertRaises(session.SessionError):
                session.process(d, {"file": "fake/x.fake", "kind": "fake", "fail": True}, d, d)
            self.assertEqual(CALLS, [("process", "fake/x.fake")])

    def test_a_whole_session_of_the_kind(self):
        # its folder is scanned, its process runs, its figure keeps its kind, and the frame is
        # checked in its own geometry (IR's 650-4000 window holds none of 200-700 nm)
        with registered(FAKE), tempfile.TemporaryDirectory() as d:
            f = Path(d) / "uv_11-11"
            (f / "fake").mkdir(parents=True)
            (f / "fake" / "band.fake").write_text("x")
            (f / "manifest.json").write_text(json.dumps(
                [{"file": "fake/band.fake", "kind": "fake", "xmin": 300, "xmax": 650}]))
            with contextlib.redirect_stdout(io.StringIO()):
                figs = session.run(str(f), build="none")
            self.assertEqual(CALLS, [("process", "fake/band.fake")])
            self.assertEqual([g.kind for g in figs], ["fake"])
            written = json.loads((f / "figures.json").read_text(encoding="utf-8"))
            self.assertEqual((written[0]["kind"], written[0]["xmin"]), ("fake", 300))
            md = next(f.glob("*.md"))   # named ir_<dd-mm> for every kind so far (roadmap item 6)
            self.assertIn("\\fakespectrum\n", md.read_text(encoding="utf-8"))
            entries = json.loads((f / "manifest.json").read_text(encoding="utf-8"))
            entries[0]["xmin"] = 700   # beyond the kind's default right edge: no frame
            (f / "manifest.json").write_text(json.dumps(entries))
            with contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaises(session.SessionError) as cm:
                session.run(str(f), build="none")
            self.assertIn("xmin (700) must be below xmax (650)", str(cm.exception.code))

    def test_preview_load_and_geometry(self):
        with registered(FAKE), tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.fake"
            p.write_text("anything")
            info = preview.work_out_entry(str(p), {"file": "x.fake", "kind": "fake", "peaks": []},
                                          None)
            self.assertEqual(CALLS, [("load", str(p))])
            self.assertEqual((info["kind"], info["format"]), ("fake", "fake"))
            self.assertEqual(info["xlim"], [200.0, 700.0])
            text = preview.render(info, 80, 8, False)
            self.assertIn("against wavelength (nm)", text)
            self.assertIn("between 200 and 700 nm", text)
            self.assertIn("range:   200 to 700 nm;", text)
            lines = text.splitlines()
            axis = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("++"))
            self.assertEqual(lines[axis + 1].split(), ["200", "300", "400", "500", "600", "700"])

    def test_edit_load_spectrum(self):
        with registered(FAKE):
            with self.assertRaises(edit.EditError):
                edit.load_spectrum("anywhere", {"file": "fake/x.fake", "kind": "fake"})
            self.assertEqual(CALLS, [("load_saved", "fake/x.fake")])

    def test_matplotlib_draws_the_kinds_axis(self):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            self.skipTest("matplotlib not installed")
        from irspec import mpl
        with registered(FAKE), tempfile.TemporaryDirectory() as d:
            x = np.linspace(200.0, 700.0, 101)
            np.savetxt(Path(d) / "a.csv", np.column_stack([x, np.exp(-((x - 450) / 40) ** 2)]),
                       delimiter=",", header="wavelength,absorbance", comments="")
            fig = mpl.draw(Figure(csv="a.csv", title="t", axis="Absorbance", kind="fake"), d)
            ax = fig.axes[0]
            self.assertEqual(ax.get_xlim(), (200.0, 700.0))
            self.assertEqual(list(ax.xaxis.get_majorticklocs()), list(FAKE.x_ticks))
            self.assertEqual(ax.get_xlabel(), "Wavelength / nm")


class UnknownKindInAFolder(unittest.TestCase):
    """A manifest entry of a kind this irspec does not know is refused, never drawn as IR (0.2.0
    drew it as IR in `session`). Editing it without drawing still works."""

    def test_session_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            f = ir_session(d, kind="uvvis")
            code, out, err = run("session", f, "--build", "none")
            self.assertEqual((code, out), (1, ""))
            self.assertIn(f"manifest.json cannot be used (SPA/{SAMPLE}: figure of kind 'uvvis'", err)
            self.assertNotIn("Traceback", err)
            code, out, err = run("session", f, "--preview", "--json")
            self.assertEqual(code, 2)
            self.assertIn("figure of kind 'uvvis'", err)

    def test_preview_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            f = ir_session(d, kind="uvvis")
            code, out, err = run("preview", f / "SPA" / SAMPLE)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("figure of kind 'uvvis'", err)

    def test_edit_peak_refuses_and_set_reports_the_stored_kind(self):
        with tempfile.TemporaryDirectory() as d:
            f = ir_session(d, kind="uvvis")
            code, out, err = run("edit", f, SAMPLE, "peak", "add", "1650")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("figure of kind 'uvvis'", err)
            code, out, err = run("edit", f, SAMPLE, "set", "title=New", "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["kind"], "uvvis")
            code, out, err = run("edit", f, SAMPLE, "set", "xmin=4000")   # not checked: not drawn
            self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
