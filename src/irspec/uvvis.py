"""The UV-Vis kind (kinds.UVVIS): a Shimadzu LabSolutions `.vspd` scan in a session folder's `uv/`.

What session does with one, the same steps vspd_tool.py's commands are, written for a report
figure: `csv/STEM.csv` is `irspec vspd convert` (wavelength,absorbance, ascending, %.7g), and
`plain/STEM.csv`, what the figure reads, is the same file. The figure stays Absorbance (no %T:
that is IR's rule). Its peaks are the peak picks stored in the file (`irspec vspd peaks`): the
ones inside the figure's x frame, labelled 6 % of the frame's span above the band, with the
`ymax` that leaves room for the labels (without it the labels push the plot onto a page of its
own: measured, docs/roadmap.md item 6). No pick, no label: irspec does not pick UV-Vis bands
itself. The first run writes the picks into manifest.json as `peaks` ([x, label_y] pairs, edited
there like IR's), and every run takes the apex heights off the trace at those x.
"""
import math
import os
import shutil

import numpy as np

from . import kinds, layout, spa_tool, vspd_tool

LABEL_OFFSET = 0.06     # label above the apex, as a fraction of the frame's y span (vspd_tool peaks)
YMAX_ROOM = 0.08        # ymax = top + this x (top - bottom), top including the labels (vspd_tool)


def read(path):
    """(x, y) ascending, of the one spectrum a .vspd holds."""
    import olefile
    try:
        with olefile.OleFileIO(path) as ole:
            specs = vspd_tool.spectra(ole)
    except SystemExit as e:          # vspd_tool's own complaint about a layout it does not know
        raise ValueError(str(e.code))
    if len(specs) != 1:
        raise ValueError(f"{len(specs)} spectra in one file; irspec draws a file of one")
    _, xs, ys = specs[0]
    order = np.argsort(xs)
    return np.asarray(xs, float)[order], np.asarray(ys, float)[order]


def stored_picks(path):
    """[(x, y)] of the peak picks stored in the file (valleys left out: their label would hang
    over the trace), by x."""
    import olefile
    with olefile.OleFileIO(path) as ole:
        return sorted((x, y) for label, x, y in vspd_tool.picks(ole) if label.startswith("Peak"))


def peaks_and_limits(entry, x, y, path=None):
    """{"peaks": [[x, label_y]], "apex": [...], "ymin", "ymax"} for the figure of `entry`: its
    own `peaks` if it has them, else the file's stored picks; only those inside the x frame;
    apex heights off the trace; the entry's `ymax`, else the one that leaves room for labels."""
    kind = kinds.UVVIS
    xlim = layout.xlimits(entry.get("xmin"), entry.get("xmax"), kind, x)
    lo, hi = min(xlim), max(xlim)
    inside = (x >= lo) & (x <= hi)
    win = y[inside]
    if not win.size:
        raise ValueError(f"no data between {lo:g} and {hi:g} nm")
    bottom = float(win.min())
    if "peaks" in entry:
        pairs = [(float(p[0]), float(p[1])) for p in entry["peaks"]]
    else:
        off = LABEL_OFFSET * float(win.max() - win.min())
        pairs = [(px, round(py + off, 4)) for px, py in (stored_picks(path) if path else [])]
    pairs = [(px, ly) for px, ly in pairs if lo <= px <= hi]
    apex = [round(float(np.interp(px, x, y)), 4) for px, _ in pairs]
    ymax = entry.get("ymax")
    if ymax is None and pairs:
        top = max([float(win.max())] + [ly for _, ly in pairs])
        step = layout.y_step(bottom, top)
        ymax = math.ceil((top + YMAX_ROOM * (top - bottom)) / step) * step
        ymax = max(ymax, float(np.nextafter(top, np.inf)))
    return {"peaks": [[px, ly] for px, ly in pairs], "apex": apex,
            "ymin": entry.get("ymin"), "ymax": ymax}


def process(folder, e, csv_dir, plain_dir):
    """One `uv/` entry -> csv/STEM.csv and plain/STEM.csv, and session's result dict."""
    from .session import SessionError
    path = os.path.join(folder, e["file"])
    stem = spa_tool.clean_stem(e["file"])
    archival = os.path.join(csv_dir, f"{stem}.csv")
    plain = os.path.join(plain_dir, f"{stem}.csv")
    try:
        x, y = read(path)
        vspd_tool.cmd_convert(path, archival, None, False)
        shutil.copyfile(archival, plain)
        got = peaks_and_limits(e, x, y, path)
    except (ValueError, OSError) as err:   # a file it cannot read, limits outside the scan
        raise SessionError(f"{e['file']}: {err}")
    if "peaks" not in e:            # the first run writes the picks, to be edited there
        e["peaks"] = got["peaks"]
    axis = e.get("axis") or kinds.UVVIS.y_label
    return {"title": e.get("title") or stem, "stem": stem, "axis_label": axis, "axis_md": axis,
            "peaklist": ",".join(f"{px:g}/{ly:g}" for px, ly in got["peaks"]),
            "ymin": got["ymin"], "ymax": got["ymax"], "xmin": e.get("xmin"), "xmax": e.get("xmax"),
            "n_peaks": len(got["peaks"]), "apex": got["apex"],
            "archival_path": archival, "plain_path": plain}


def load(path, entry):
    """(x, y, axis, absorbance, format, converted_from) for irspec preview."""
    x, y = read(path)
    return x, y, (entry or {}).get("axis") or kinds.UVVIS.y_label, True, "vspd", None


def pick(entry, x, y, axis, absorbance, path=None):
    """irspec preview's peaks: what session would draw."""
    got = peaks_and_limits(entry or {}, np.asarray(x, float), np.asarray(y, float), path)
    return {"peaks": got["peaks"], "ymin": got["ymin"], "ymax": got["ymax"]}


def load_saved(folder, entry):
    """(x, y, axis, absorbance) of a session's entry, from its plain/ CSV (irspec edit)."""
    from .edit import EditError
    from .session import read_plain
    stem = spa_tool.clean_stem(entry["file"])
    plain = os.path.join(folder, "plain", f"{stem}.csv")
    if not os.path.exists(plain):
        raise EditError(f"no spectrum for {entry['file']}: plain/{stem}.csv does not exist "
                           f"(run `irspec session` on the folder first)")
    x, y = read_plain(plain)
    return x, y, entry.get("axis") or kinds.UVVIS.y_label, True
