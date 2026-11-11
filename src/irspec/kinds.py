"""The registry of plot kinds (docs/roadmap.md, item 6).

A kind is what a figure shows: an IR spectrum today; later a UV-Vis spectrum, a chromatogram,
a mass or NMR spectrum. Everything irspec used to hard-wire for IR is a field of one Kind, and
`session`, `preview`, `edit`, the figure writers and the matplotlib backend read it from here,
so the next kind is a new entry and its functions, not a copy of those modules.

The fields follow nulabreport's own plot kinds, `\\labdefineplotkind{name}{x column}{y column}
{trough|apex|fan}{axis keys}` (nulabreport.sty, v1.19.0: ir, gc, titration, ms, nmr, uvvis), so
the two describe a kind the same way. The TeX axis keys are not here yet: they arrive with the
handover, when the kinds' TeX moves into irspec (roadmap item 6), copied as they are, because
they are TeX's inputs and the numbers below are measurements of TeX's output; neither is
worked out from the other.

A manifest or figures.json entry names its kind in `kind`; absent means "ir" (docs/schema.md).
A kind's four functions are named by "module:function" and imported when first used, so this module
imports nothing of irspec's and every other module can import it; tests/test_kinds.py checks
that each name resolves.
"""
import importlib
from dataclasses import dataclass
from typing import Optional, Tuple

SPA_EXT = (".spa", ".spg")
JDX_EXT = (".jdx", ".dx", ".jcm")
IMG_EXT = (".gif", ".jpg", ".jpeg", ".png", ".bmp")

ROLES = ("process", "load", "load_saved", "pick")


@dataclass(frozen=True)
class Kind:
    name: str                       # the `kind` of manifest.json, figures.json and --json
    x_column: str                   # the plain CSV's columns (nulabreport's x and y column)
    y_column: str
    labels: str                     # how peak labels hang (nulabreport): trough, apex or fan
    x_label: str                    # the x-axis title, plain text
    x_unit: str                     # in messages: "no data between 650 and 4000 cm-1"
    y_label: str                    # the y-axis title a figure gets unless its entry says another
    xlim: Optional[Tuple[float, float]]   # the default frame (low, high); None: the data's own ends
    x_descending: bool              # drawn high to low, left to right (IR)
    x_ticks: Optional[Tuple[float, ...]]  # the labelled x ticks; None: layout.x_ticks's rule
    x_minor: Optional[float]        # minor x tick step; None: a fifth of the labelled step
    pad: Tuple[float, float]        # frame below / above the y limits, as a fraction of their span
    y_scope: str                    # the data the y axis scales on: "all" (what the default frame
    #                                 shows, whatever the crop: IR) or "frame" (inside the x frame)
    macro: str                      # the TeX command a figure is written as
    folders: Tuple[Tuple[str, Tuple[str, ...]], ...]   # session's subfolders and their extensions
    process: str                    # one manifest entry -> its CSVs and result (irspec session)
    load: str                       # a file -> what the preview draws (irspec preview)
    load_saved: str                 # a session's entry -> its spectrum, from what session wrote (edit)
    pick: str                       # (entry, x, y, axis, absorbance, path) -> session's peaks, ymin, ymax

    def function(self, role):
        """The function a role names, imported now."""
        module, _, attr = getattr(self, role).partition(":")
        return getattr(importlib.import_module(module), attr)


IR = Kind(
    name="ir",
    x_column="wavenumber", y_column="intensity", labels="trough",
    x_label="Wavenumber / cm⁻¹", x_unit="cm-1", y_label="Transmittance %",
    # Measured on the TeX figure (layout.py says how): the frame, the ticks, the padding.
    xlim=(650.0, 4000.0), x_descending=True,
    x_ticks=(4000.0, 3500.0, 3000.0, 2500.0, 2000.0, 1500.0, 1000.0), x_minor=100.0,
    pad=(0.0985, 0.0017), y_scope="all",
    macro="irspectrum",
    folders=(("SPA", SPA_EXT), ("jdx", JDX_EXT), ("img", IMG_EXT)),
    process="irspec.session:process_ir",
    load="irspec.preview:load_ir",
    load_saved="irspec.edit:load_saved_ir",
    pick="irspec.preview:pick_ir",
)

UVVIS = Kind(
    name="uvvis",
    x_column="wavelength", y_column="absorbance", labels="apex",
    x_label="Wavelength / nm", x_unit="nm", y_label="Absorbance",
    # nulabreport's uvvis kind, measured on the TeX figure (2026-11-11, docs/roadmap.md item 6):
    # the frame is the scan's own ends, IR's y padding, y on the data inside the x frame
    xlim=None, x_descending=False, x_ticks=None, x_minor=None,
    pad=(0.0985, 0.0017), y_scope="frame",
    macro="labplot",
    folders=(("uv", (".vspd",)),),
    process="irspec.uvvis:process",
    load="irspec.uvvis:load",
    load_saved="irspec.uvvis:load_saved",
    pick="irspec.uvvis:pick",
)

REGISTRY = {IR.name: IR, UVVIS.name: UVVIS}
DEFAULT = IR


def for_path(rel):
    """The kind whose folder and extensions `rel` ("SPA/x.SPA") is in, or None."""
    sub, _, name = rel.replace("\\", "/").rpartition("/")
    sub = sub.rsplit("/", 1)[-1]
    for k in REGISTRY.values():
        for folder, exts in k.folders:
            if sub == folder and name.lower().endswith(exts):
                return k
    return None


def for_extension(path):
    """The kind whose files have `path`'s extension (a loose file, no manifest entry), or None."""
    name = str(path).lower()
    for k in REGISTRY.values():
        if any(name.endswith(exts) for _, exts in k.folders):
            return k
    return None


def for_entry(path, entry):
    """The kind of a file being read: its manifest entry's `kind`, else (no entry, or one without
    `kind`) the kind its folder or extension belongs to, else the default."""
    if entry and "kind" in entry:
        return of(entry)
    rel = (entry or {}).get("file") or ""
    return for_path(rel) or for_extension(path) or DEFAULT


def get(name):
    """The Kind called `name`; ValueError for one this irspec does not know."""
    if isinstance(name, str) and name in REGISTRY:
        return REGISTRY[name]
    known = ", ".join(repr(k) for k in REGISTRY)
    raise ValueError(f"figure of kind {name!r}: this irspec draws only {known} figures")


def of(entry):
    """The Kind of a manifest or figures.json entry (no `kind`: the default, "ir")."""
    return get((entry or {}).get("kind", DEFAULT.name))


def all_kinds():
    return list(REGISTRY.values())
