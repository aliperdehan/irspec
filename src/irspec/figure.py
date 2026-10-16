"""The renderer-neutral description of one spectrum figure.

Every output backend (TeX, later matplotlib and R) takes a list of Figure and
knows nothing about OMNIC, JCAMP-DX or digitised pictures: a figure is a plain
CSV of the house shape ("wavenumber,intensity", comma, dot decimal, clipped
at 650 cm-1), a y-axis label, peaks, a title and a few size knobs.

The on-disk form is a manifest entry (the JSON that `ir_organize` already keeps
beside a session): {"file"|"csv", "title", "peaks", "axis", "ymin", "width",
"height"}. `Figure.from_entry` / `to_entry` are the two directions.

`figures.json` (write_figures / read_figures) is the same list written beside a
session's manifest, after the run, with every `csv` relative to that file's own
folder: the one file a backend (matplotlib, R, anything else) needs. Text in it
(`title`, `axis`) is plain, never LaTeX-escaped; the TeX writer escapes at
render time. `width` and `height` are TeX lengths and mean nothing outside TeX:
other backends take their own size.
"""
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

SPEC_VERSION = 1
FIGURES_NAME = "figures.json"   # what `session` writes and every backend reads


@dataclass
class Figure:
    csv: str                       # the plain CSV, relative to the document that uses it
    title: str
    axis: str = "Transmittance %"  # y-axis label; Transmittance % or Absorbance
    peaks: List[Tuple[float, float]] = field(default_factory=list)  # (wavenumber, label_y)
    ymin: Optional[float] = None   # None: let the plotting backend choose
    width: str = r"\linewidth"
    height: str = "6.8in"

    def peaklist(self) -> str:
        """The `\\irspectrum` peak argument: wavenumber/label_y pairs, one
        decimal each (identical to spa_peaks.format_peaklist)."""
        return ",".join(f"{x:.1f}/{ly:.1f}" for x, ly in self.peaks)

    @classmethod
    def from_entry(cls, entry: dict) -> "Figure":
        """A manifest entry that names its plain CSV (`csv`), carries its axis
        label and peaks as [wavenumber, label_y] pairs."""
        try:
            csv = entry["csv"]
        except KeyError:
            raise ValueError("manifest entry has no 'csv' (the plain CSV to plot)")
        peaks = [(float(p[0]), float(p[1])) for p in entry.get("peaks", [])]
        kw = {k: entry[k] for k in ("axis", "ymin", "width", "height") if k in entry}
        return cls(csv=csv, title=entry.get("title", ""), peaks=peaks, **kw)

    def to_entry(self) -> dict:
        d = {"spec": SPEC_VERSION, "csv": self.csv, "title": self.title,
             "axis": self.axis, "peaks": [[x, ly] for x, ly in self.peaks]}
        if self.ymin is not None:
            d["ymin"] = self.ymin
        if self.width != r"\linewidth":
            d["width"] = self.width
        if self.height != "6.8in":
            d["height"] = self.height
        return d

    @classmethod
    def from_organize_result(cls, r: dict, folder: str) -> "Figure":
        """From one `ir_organize` result dict (keys plain_path, axis_md,
        peaklist, title, ymin), so a session folder's figures can be rendered
        by any backend."""
        import os
        peaks = []
        for item in r["peaklist"].split(","):
            if item.strip():
                x, ly = item.split("/")
                peaks.append((float(x), float(ly)))
        return cls(csv=os.path.relpath(r["plain_path"], folder), title=r["title"],
                   axis=r["axis_md"], peaks=peaks, ymin=r["ymin"])


def write_figures(figures, path) -> str:
    """Write `figures` as a JSON list of entries (spec SPEC_VERSION)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump([fig.to_entry() for fig in figures], f, indent=2, ensure_ascii=False)
        f.write("\n")
    return str(path)


def read_figures(path):
    """(figures, folder): the Figures in a figures.json, and the folder their
    `csv` paths are relative to (the JSON's own)."""
    path = os.fspath(path)
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected a JSON list of figures")
    for e in entries:
        if e.get("spec", SPEC_VERSION) != SPEC_VERSION:
            raise ValueError(f"{path}: figure spec {e.get('spec')} is not the one this irspec "
                             f"reads ({SPEC_VERSION})")
    return [Figure.from_entry(e) for e in entries], os.path.dirname(os.path.abspath(path))
