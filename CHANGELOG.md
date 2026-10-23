# Changelog

irspec follows the rules in the README's "Versioning" section. Newest first.

## Unreleased

- New `irspec edit`: `irspec edit DIR FILE set KEY=VALUE ...`, `irspec edit DIR FILE unset KEY ...`
  and `irspec edit DIR show [FILE] [--json]` change or show `manifest.json` without a text
  editor (keys: `title`, `axis`, `name`, `ymin`, `ymax`, `xmin`, `xmax`, `threshold`,
  `prominence`, `distance`). Atomic write, order and layout kept, idempotent, prints the old and
  new value (`--json`: one object), errors on stderr with exit 2 (1 for a missing manifest).
  First slice of roadmap item 1a; peak editing and re-running the session are not in it, and
  `xmin`, `xmax` and `ymax` are stored but not yet read by the figures.

## 0.1.0 (2026-10-16), the first release

The changes since the last development snapshot (0.0.5) come first; the list after
them is everything the release holds.

- `irspec session`: a book figure (`--palleros` in the manifest's `args`) with `check` set
  to the band positions printed in the book takes those positions as its peaks (it asks
  `digitize` for `--peaklist`); a hand-edited `peaks` still wins. Verified on the
  Palleros IR figure of the author's coursework: both CSVs byte-identical to the ones the
  recipe made by hand. (The figure is a textbook page and is not in this repository, so
  the test uses a stand-in for the digitiser.)
- A new reference entry starts with a readable title (compound name from
  `cas_names.json`, else the title inside the `.jdx`) instead of the file stem.
- Fixed: a second run moved `figures.json` (written by the first) into `other/`.
- Fixed: two figures with one name no longer write one picture over the other
  (`NAME`, `NAME-2`, ...).
- Fixed: `ResourceWarning` from reading a `.SPA` (file not closed).
- `pdfmd` is found as `--pdfmd`, `$PDFMD` or `pdfmd` on the PATH, in one place for both
  `session` and `ir_organize`; the path of the author's own checkout is no longer built in.
  An installed `pdfmd` command is run as it is, not through Python. `session` prints which
  build (pdfmd or lualatex alone) made the PDF.
- `python -m irspec` works.
- `legacy/` (the original scripts, the tests' oracle) is removed; it stays in the git history
  under the tag `legacy-oracle`. The sixteen commands are compared with what the
  original scripts did (recorded in `tests/data/differential_expected.json`) and the
  author's phenacetin CSVs.
  `ir_organize` stays as a module (nulabreport's `ir_organize.py` forwards to it) and
  `session` is its successor for new work; the two share one set of functions.
- Development status Alpha; PyPI keywords and classifiers.

Everything in 0.1.0:

- `irspec session DIR`: a folder of `.SPA`, `.jdx` and SDBS-style pictures in;
  archival and plain CSVs, peak lists, a manifest, a figure PDF out.
- `irspec export PDF` and `session --formats`: PNG, TIFF and SVG (outlined or
  with editable text) from the figure PDF, one file per spectrum.
- The figure PDF is built by nulabreport's `pdfmd` when it is installed, else by
  plain `lualatex` from a generated `.tex` that uses the bundled excerpt
  `irspec-ir.sty`.
- The older tools as sub-commands: `spa`, `jdx`, `peaks`, `digitize`, `a2t`,
  `absorptivity`, `corr`.
- `figures.json`, written by `session`: the renderer-neutral figure list
  (`SPEC_VERSION = 1`, plain text, csv paths relative to the file).
- `irspec plot DIR [--backend matplotlib|r]`: the figures drawn without TeX, into
  `figures/matplotlib/` or `figures/r/`. matplotlib: png, tiff, pdf, svg,
  svg-text; R (`data/irspec.R`, also runnable alone with `Rscript`): the same five
  (pdf and svg need an R with working cairo).
- STIX Two Text (Regular, Italic) and STIX Two Math bundled, unmodified, under the
  SIL OFL 1.1 (`data/fonts/`, with `OFL.txt`); matplotlib, R and the plain-lualatex
  fallback use them when STIX Two is not installed. One shared geometry, `layout.py`, measured on the
  TeX figure.

## Development history, unreleased

0.0.1 to 0.0.5 were private development snapshots: never tagged, never pushed,
never installed by anyone else, and numbered before the versioning rules were
written. They are kept in the git history as they were.

| Snapshot | What it added |
|---|---|
| 0.0.5 | PNG, TIFF, SVG export (`irspec export`, `session --formats`) |
| 0.0.4 | the `irspec` command and `irspec session` |
| 0.0.3 | `Figure` (the renderer-neutral description), `texout` (Markdown and plain-TeX writers), the bundled excerpt |
| 0.0.2 | the eight scripts as the `irspec` package, differential test against the originals |
| 0.0.1 | the eight scripts from nulabreport `tools/`, copied unchanged into `legacy/` |
