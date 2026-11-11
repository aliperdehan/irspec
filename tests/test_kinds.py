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
import subprocess
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
    x = np.linspace(200.0, e.get("upto", 700.0), 101)
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
    x = np.linspace(200.0, (entry or {}).get("upto", 700.0), 101)
    return x, np.exp(-((x - 450.0) / 40.0) ** 2), "Absorbance", True, "fake", None


def fake_load_saved(folder, entry):
    CALLS.append(("load_saved", entry["file"]))
    raise edit.EditError("fake load_saved called")


def fake_pick(entry, x, y, axis, absorbance, path=None):
    CALLS.append(("pick", None))
    return {"peaks": [[450.0, 1.1]], "ymin": None, "ymax": entry.get("ymax")}


# A second kind, ascending x like a UV-Vis spectrum, with its own functions.
FAKE = dataclasses.replace(
    kinds.IR, name="fake", x_column="wavelength", x_label="Wavelength / nm", x_unit="nm",
    xlim=(200.0, 700.0), x_descending=False,
    x_ticks=(200.0, 300.0, 400.0, 500.0, 600.0, 700.0), x_minor=50.0,
    pad=(0.04, 0.08), macro="fakespectrum", folders=(("fake", (".fake",)),),
    process=f"{__name__}:fake_process", load=f"{__name__}:fake_load",
    load_saved=f"{__name__}:fake_load_saved", pick=f"{__name__}:fake_pick")
# A third, shaped like UV-Vis: no fixed frame (the data's own ends), no tick list, y scaled on
# what is inside the x frame, labels above the band, drawn with \labplot.
ENDS = dataclasses.replace(
    FAKE, name="ends", xlim=None, x_ticks=None, x_minor=None, y_scope="frame", labels="apex",
    pad=kinds.IR.pad,
    macro="labplot", y_label="Absorbance", folders=(("ends", (".ends",)),))


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
        for bad in ("chromatogram", "", None, ["ir"], 3):
            with self.subTest(kind=bad), self.assertRaises(ValueError) as cm:
                kinds.of({"kind": bad})
            self.assertIn("this irspec draws only 'ir', 'uvvis' figures", str(cm.exception))

    def test_the_old_names_are_irs_numbers(self):
        # layout's constants (the R script's test reads them), ir_organize's and session's
        # file types: aliases of the IR kind, so there is one place to change them
        self.assertEqual(layout.XLIM, kinds.IR.xlim[::-1])   # (left, right): descending
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
            code, out, err = run("session", f, "--build", "none", "--json")   # the folder's kind
            self.assertEqual(code, 0, err)
            obj = json.loads(out)
            self.assertEqual((obj["kind"], obj["spectra"][0]["kind"]), ("fake", "fake"))
            CALLS.clear()
            entries = json.loads((f / "manifest.json").read_text(encoding="utf-8"))
            entries[0]["xmin"] = 700   # beyond the kind's default right edge: no frame
            (f / "manifest.json").write_text(json.dumps(entries))
            with contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaises(session.SessionError) as cm:
                session.run(str(f), build="none")
            self.assertIn("xmin (700) must be below xmax (650)", str(cm.exception.code))

    def test_a_kind_whose_data_is_all_below_irs_window(self):
        # 200-600 nm: nothing of it is inside IR's 650-4000, so any IR geometry left on the way
        # (the window, the frame, session's frame check) would find no data
        with registered(ENDS), tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.ends"
            p.write_text("anything")
            info = preview.work_out_entry(str(p), {"file": "x.ends", "kind": "ends", "upto": 600.0},
                                          None)
            self.assertEqual(info["xlim"], [200.0, 600.0])
            f = Path(d) / "uv_11-11"
            (f / "ends").mkdir(parents=True)
            (f / "ends" / "band.ends").write_text("x")
            (f / "manifest.json").write_text(json.dumps([{"file": "ends/band.ends", "upto": 600.0}]))
            with contextlib.redirect_stdout(io.StringIO()):
                figs = session.run(str(f), build="none")
            self.assertEqual((figs[0].kind, figs[0].csv), ("ends", "plain/band.csv"))

    def test_preview_load_and_geometry(self):
        with registered(FAKE), tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.fake"
            p.write_text("anything")
            info = preview.work_out_entry(str(p), {"file": "x.fake", "kind": "fake", "peaks": []},
                                          None)
            self.assertEqual(CALLS, [("load", str(p)), ("pick", None)])
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


def ends_csv(d, name="a.csv"):
    x = np.linspace(200.0, 700.0, 101)
    y = 0.2 + np.exp(-((x - 450.0) / 40.0) ** 2) + 3.0 * np.exp(-((x - 230.0) / 15.0) ** 2)
    np.savetxt(Path(d) / name, np.column_stack([x, y]), delimiter=",",
               header="wavelength,absorbance", comments="")
    return x, y


class DataEndedFrame(unittest.TestCase):
    """A kind with no fixed frame (UV-Vis: the scan's own ends), y scaled on the x frame."""

    def test_the_frame_is_the_datas_ends_and_y_follows_the_crop(self):
        x = np.linspace(200.0, 700.0, 101)
        y = np.where(x < 300, 4.0, 1.0) + x * 0.0
        xlim, ylim, _, _ = layout.frame(x, y, ENDS)
        self.assertEqual(xlim, (200.0, 700.0))
        self.assertAlmostEqual(ylim[1], 4.0 + 0.0017 * 3.0)
        y2 = np.where(x < 300, 4.0, 1.0 + (x - 350) / 350)     # 1 to 2 inside 350-700
        xlim, ylim, _, _ = layout.frame(x, y2, ENDS, xmin=350)
        self.assertEqual(xlim, (350.0, 700.0))
        self.assertAlmostEqual(ylim[1], 2.0 + 0.0017 * 1.0)  # the 4.0 below 300 nm is not in it
        # IR's y scope is all it shows: a crop does not change y
        xi = np.linspace(650.0, 4000.0, 400)
        yi = np.where(xi > 3000, 10.0, 90.0)
        self.assertEqual(layout.frame(xi, yi)[1], layout.frame(xi, yi, xmin=1000, xmax=2000)[1])

    def test_measured_uvvis_frames(self):
        # the frames pgfplots drew for nulabreport's uvvis kind (pdfplumber, 2026-11-11), on the
        # author's scan: the same padding as IR, y from the data inside the x frame
        a = np.genfromtxt(DATA / "uvvis_golden.csv", delimiter=",", skip_header=1)
        x, y = a[:, 0], a[:, 1]
        for limits, want in (({}, (-0.5491, 4.8742)), ({"ymax": 5.58}, (-0.6191, 5.5887)),
                             ({"xmin": 300, "xmax": 650}, (-0.4161, 4.3756)),
                             ({"xmin": 350, "xmax": 700, "ymin": 0, "ymax": 1}, (-0.0984, 1.0017)),
                             ({"ymin": -1, "ymax": 6}, (-1.6887, 6.0110))):
            with self.subTest(**limits):
                _, ylim, _, _ = layout.frame(x, y, ENDS, **limits)
                self.assertAlmostEqual(ylim[0], want[0], delta=0.002)
                self.assertAlmostEqual(ylim[1], want[1], delta=0.002)

    def test_ends_and_direction(self):
        x = np.linspace(250.0, 650.0, 81)              # not 200-700: the data's own ends
        self.assertEqual(layout.frame(x, 1 + x / 1000, ENDS)[0], (250.0, 650.0))
        xi = np.linspace(500.0, 4500.0, 400)           # IR: its fixed frame, high wavenumber first
        self.assertEqual(layout.frame(xi, 50 + xi / 100)[0], (4000.0, 650.0))
        self.assertEqual(layout.xlimits(1000, 3000), (3000.0, 1000.0))

    def test_ticks_without_a_list(self):
        # what pgfplots labelled: every 20 nm, minor every 4, for 200-700 and 350-700
        ticks, minor = layout.x_ticks((200.0, 700.0), ENDS)
        self.assertEqual((ticks[0], ticks[1], ticks[-1], len(ticks), minor), (200, 220, 700, 26, 4))
        self.assertEqual(layout.x_ticks((350.0, 700.0), ENDS)[0][0], 360)
        self.assertEqual(layout.x_ticks((650.0, 4000.0)), (list(kinds.IR.x_ticks), 100.0))
        self.assertEqual(layout.x_ticks((1000.0, 2930.0))[0], [2500.0, 2000.0, 1500.0, 1000.0])

    def test_no_data_is_a_message(self):
        with self.assertRaises(ValueError):
            layout.xlimits(kind=ENDS)


class ApexLabels(unittest.TestCase):
    def test_peak_list_and_labplot_block(self):
        with registered(ENDS):
            fig = Figure(csv="plain/a.csv", title="Scan", axis="Absorbance", kind="ends",
                         peaks=[(255.0, 5.16158), (510.0, 0.67571)], apex=[4.86591, 0.37988],
                         ymax=5.58)
            self.assertEqual(fig.peaklist(), "255/4.8659/5.1616/{},510/0.3799/0.6757/{}")
            self.assertEqual(texout._block(fig),
                             "\\labplot\n  [kind=ends,width=\\linewidth,height=6.8in,ymax=5.58]\n"
                             "  {plain/a.csv}\n  {255/4.8659/5.1616/{},510/0.3799/0.6757/{}}\n"
                             "  {Scan}\n\\clearpage\n")
            fig.axis = "A (a.u.)"
            self.assertIn(",ymax=5.58,ylabel={A (a.u.)}]", texout._block(fig))
            entry = fig.to_entry()
            self.assertEqual(entry["apex"], [4.86591, 0.37988])
            self.assertEqual(Figure.from_entry(entry).apex, [4.86591, 0.37988])
        self.assertNotIn("apex", Figure(csv="a.csv", title="t").to_entry())

    def test_backends_that_cannot_draw_it_say_so(self):
        from irspec import export, mpl, plot
        with registered(ENDS), tempfile.TemporaryDirectory() as d:
            ends_csv(d)
            fig = Figure(csv="a.csv", title="t", axis="Absorbance", kind="ends",
                         peaks=[(450.0, 1.4)], apex=[1.2])
            try:
                import matplotlib  # noqa: F401
                with self.assertRaises(export.ExportError) as cm:
                    mpl.draw(fig, d)
                self.assertIn("a ends figure's labels (apex) are not in yet", str(cm.exception.code))
            except ImportError:
                pass
            (Path(d) / "figures.json").write_text(json.dumps([fig.to_entry()]))
            with self.assertRaises(export.ExportError) as cm:
                plot.refuse_other_kinds(["--formats", "png", d])
            self.assertIn("a.csv is a ends figure; the R backend draws IR figures only", str(cm.exception.code))
            self.assertEqual(plot.r_target(["--out", "x", "--dpi", "300", d, "--formats", "png"]), d)
            rscript = shutil.which("Rscript")
            if rscript:   # the R script refuses on its own too (it can be run without irspec)
                r = subprocess.run([rscript, plot.r_script_path(), d, "--formats", "png"],
                                   capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("a.csv is a ends figure; this script draws IR figures only", r.stderr)


class Ownership(unittest.TestCase):
    """Which kind a file is: its folder says, a stated kind must agree, loose files are filed."""

    def test_folder_names_the_kind(self):
        with registered(ENDS):
            self.assertIs(kinds.for_path("ends/a.ends"), ENDS)
            self.assertIs(kinds.for_path("SPA/a.SPA"), kinds.IR)
            self.assertIsNone(kinds.for_path("other/a.txt"))
            self.assertIsNone(kinds.for_path("ends/a.SPA"))
            self.assertEqual(session.filing_folder("scan.ENDS"), "ends")
            self.assertEqual(session.filing_folder("run.SPA"), "SPA")
            self.assertEqual(session.folder_kind(["ends/a.ends", "other/x.txt"]), "ends")
            self.assertEqual(session.folder_kind(["ends/a.ends", "SPA/a.SPA"]), "mixed")
            self.assertEqual(session.folder_kind([]), "ir")
            self.assertEqual(session.planned_names("/nowhere", {"file": "ends/scan_2.ends",
                                                                "kind": "ends"}),
                             ("scan_2", "csv/scan_2.csv", "plain/scan_2.csv"))

    def test_manifest_gets_the_kind_and_a_mismatch_is_refused(self):
        with registered(ENDS), tempfile.TemporaryDirectory() as d:
            f = Path(d)
            (f / "ends").mkdir()
            (f / "ends" / "a.ends").write_text("x")
            (f / "manifest.json").write_text(json.dumps([{"file": "ends/a.ends"}]))
            entries = session.build_manifest(str(f), {}, "name")
            self.assertEqual(entries[0]["kind"], "ends")
            (f / "manifest.json").write_text(json.dumps([{"file": "ends/a.ends", "kind": "ir"}]))
            with self.assertRaises(ValueError) as cm:
                session.build_manifest(str(f), {}, "name")
            self.assertIn("its kind is 'ir', but it is in ends/, the folder of 'ends' files",
                          str(cm.exception))

    def test_loose_files_are_filed_and_previewed(self):
        with registered(FAKE), tempfile.TemporaryDirectory() as d:
            f = Path(d) / "uv_11-11"
            f.mkdir()
            (f / "band.FAKE").write_text("x")
            moves = session.organize(str(f), dry_run=True)
            self.assertEqual([session._rel(str(f), b) for _, b in moves], ["fake/band.FAKE"])
            code, out, err = run("session", f, "--preview", "--json")
            self.assertEqual(code, 0, err)
            obj = json.loads(out)
            self.assertEqual(obj["kind"], "fake")
            self.assertEqual([(s["kind"], s["will_be_filed_as"], s["plain"]) for s in obj["spectra"]],
                             [("fake", "fake/band.FAKE", "plain/band.csv")])
            code, out, err = run("session", f, "--dry-run", "--json")
            self.assertEqual(json.loads(out)["kind"], "fake")
            self.assertTrue((f / "band.FAKE").exists())   # nothing moved


class UnknownKindInAFolder(unittest.TestCase):
    """A manifest entry of a kind this irspec does not know is refused, never drawn as IR (0.2.0
    drew it as IR in `session`). Editing it without drawing still works."""

    def test_session_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            f = ir_session(d, kind="chromatogram")
            code, out, err = run("session", f, "--build", "none")
            self.assertEqual((code, out), (1, ""))
            self.assertIn(f"manifest.json cannot be used (SPA/{SAMPLE}: figure of kind 'chromatogram'", err)
            self.assertNotIn("Traceback", err)
            code, out, err = run("session", f, "--preview", "--json")
            self.assertEqual(code, 2)
            self.assertIn("figure of kind 'chromatogram'", err)

    def test_preview_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            f = ir_session(d, kind="chromatogram")
            code, out, err = run("preview", f / "SPA" / SAMPLE)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("figure of kind 'chromatogram'", err)

    def test_edit_peak_refuses_and_set_reports_the_stored_kind(self):
        with tempfile.TemporaryDirectory() as d:
            f = ir_session(d, kind="chromatogram")
            code, out, err = run("edit", f, SAMPLE, "peak", "add", "1650")
            self.assertEqual((code, out), (2, ""))
            self.assertIn("figure of kind 'chromatogram'", err)
            code, out, err = run("edit", f, SAMPLE, "set", "title=New", "--json")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["kind"], "chromatogram")
            code, out, err = run("edit", f, SAMPLE, "set", "xmin=4000")   # not checked: not drawn
            self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
