# Changelog

irspec follows the rules in the README's "Versioning" section. Newest first.

## 0.2.30 (2026-11-12)

- The bundled excerpt `irspec-ir.sty` is regenerated from nulabreport v1.31.30, whose review fixes reach the figure
  macros: an empty `overlay colors` palette is a LaTeX error that names the setting and goes on with the default palette
  (it divided by zero), the plot cache key includes the inherited font, and a dedicated spectrum page keeps a bare
  caption.

## 0.2.29 (2026-11-12)

- Preserve percent signs in CSV filenames in generated TeX (I2.5).

## 0.2.28 (2026-11-12)

- Clip preview line segments to the frame before rasterising tight crops (I4.3).

## 0.2.27 (2026-11-12)

- Report truncated VSPD headers and VQUD configuration fields as input errors (I4.4).

## 0.2.26 (2026-11-12)

- Resolve SPA batch CSV references from the Markdown location (I3.5), a deliberate
  departure from the legacy scripts recorded in the spa_batch_md oracle case.

## 0.2.25 (2026-11-12)

- Report unreadable figure descriptions and CSV files as matplotlib export errors (I5.4).

## 0.2.24 (2026-11-12)

- Preserve an explicit empty peak selection when clearing an empty automatic list (I4.5).

## 0.2.23 (2026-11-12)

- The standalone R backend qualifies colliding stems by the differing input path
  before drawing (I5.2), and preflights all requested format filenames. Its names
  agree with Python, remain stable on reordering, and leave other names intact.

## 0.2.22 (2026-11-12)

- PDF export and matplotlib allocate filenames across all figures and requested
  formats before writing (I5.1), including SVG suffix collisions. Qualifiers come
  from input paths, never processing order; non-colliding names stay unchanged.

## 0.2.21 (2026-11-12)

- Allocate session and organiser CSV names before processing any spectrum (I2.2).
  Qualify colliding names with their source path, leave other names intact, and
  report both inputs and their new names. Saved names survive reordering and
  re-runs; duplicate inputs are refused. Preview and peak editing use these names.

## 0.2.20 (2026-11-12)

- Widen equal automatic y bounds by one existing layout tick step on each
  automatic side (I5.3). The zero-span tick rule uses exponent zero and its first
  1–2–5 multiplier, hence a step of 1; the kind's measured padding then applies.
  Equal or reversed fully explicit limits still fail. No new margin constant.

## 0.2.19 (2026-11-12)

- Round automatic UV-Vis upper limits upwards on the existing layout tick step,
  derived from the trace and label range, so weak signals and labels fit (I4.2).
  Keep the existing 8% label headroom; explicit limits are unchanged.

## 0.2.18 (2026-11-12)

- Preview and session share QUANT-IR scale selection: `peak_a` takes precedence
  over `cl` when both are present (I4.1).

## 0.2.17 (2026-11-12)

- Manual `peaks` requests reuse the nearest-local-extremum picker, avoiding a
  neighbouring band's slope (I3.3). Retain its existing 15 cm⁻¹ window and
  three-sample extremum order so all manual picking follows the same rule.

## 0.2.16 (2026-11-12)

- SPA convert and batch use the detected axis for automatic band picking and label
  placement (I3.2). Existing prominence and label gaps retain their native units.

## 0.2.15 (2026-11-12)

- Convert absorbance SPA traces and peaks to %T in sessions and previews; retain
  the original absorbance in archival CSVs (I2.3).

## 0.2.14 (2026-11-11)

- Escape free-text captions and labels in one pass, including carets and tildes.

## 0.2.13 (2026-11-11)

- Resolve relative pdfmd paths before changing to the session folder.

## 0.2.12 (2026-11-11)

- Reject malformed manifest structures with a useful error before merging.

## 0.2.11 (2026-11-11)

- Session JSON reports expected pdfmd and picture export failures.

## 0.2.10 (2026-11-11)

- Empty image traces stop with a digitisation failure and retain their session check log.

## 0.2.9 (2026-11-11)

- `jdx batch` and default `jdx convert` filenames escape path and reserved characters in
  titles, name maps and overrides. CSV display names stay intact. Derived destinations are
  checked for symlink escapes before writing either batch CSV.

## 0.2.8 (2026-11-11)

- Sessions reject reference names that are paths, including names from `cas_names.json`.
  Reference CSVs, image overlays and logs must resolve inside their destination directories;
  an existing symlink pointing outside is refused before conversion starts.

## 0.2.7 (2026-11-11)

- Sessions classify QUANT-IR absorptivity from the full parsed JCAMP header, including units
  after long headers or with spaces before `=`. Such spectra always require `peak_a` or `cl`.
  The absorptivity converter also checks the parsed units, rather than matching comment text.

## 0.2.6 (2026-11-11)

- `a2t` rejects negative decimal precision before opening its output. CSV writes replace the
  destination atomically, so a formatting failure preserves an existing or in-place input file.

## 0.2.5 (2026-11-11)

UV-Vis figures in a session: the second plot kind (roadmap item 6).

- A Shimadzu `.vspd` scan in a session folder is filed into `uv/` and drawn as a UV-Vis figure
  (absorbance against wavelength, the scan's own range, nulabreport's `\labplot[kind=uvvis]`),
  beside any IR spectra in the same folder. Its CSVs are what `irspec vspd convert` writes; its
  peaks are the picks stored in the file, written into the manifest on the first run and labelled
  above their bands; the figure gets the `ymax` that leaves room for the labels (without it they
  push the plot onto a page of its own). `xmin`/`xmax` crop it and leave out the picks outside.
  The figure's peak list is, character for character, what `irspec vspd peaks` prints for the same
  range, and the frame of the TeX figure is the measured one (one page; with the full package
  and with the bundled excerpt).
- `irspec preview` and `session --preview` draw a `.vspd` (left to right, bands up); a loose file
  with no manifest entry takes the kind of its extension. `irspec edit` sets and unsets keys on a
  UV-Vis entry; `peak` is refused with a message (edit `peaks` in the manifest), as matplotlib
  and R refuse to draw one: use the PDF.
- `session` stops with the file and the reason, not a traceback, when a UV-Vis crop leaves no
  data or the file cannot be read.

## 0.2.4 (2026-11-11)

The registry of plot kinds learns what UV-Vis needs, before UV-Vis is registered; IR, still the
one kind, draws byte for byte what 0.2.3 drew (every output of a test session folder compared).

- A kind may have no fixed frame (the data's own ends), its own direction, no fixed tick list
  (then the smallest 1-2-5 step with at most 25 intervals), y scaled on the data inside the x
  frame instead of on all of it, and peak labels above the band: `figures.json` gains `apex`,
  the trace's height at each peak, beside `peaks`, and the TeX writer writes such a kind as
  nulabreport's `\labplot[kind=...]` with `x/apex/label/{}` peaks. One function works the frame
  out for `session`, `preview`, `edit` and matplotlib. The UV-Vis numbers were measured on the
  TeX figure first (docs/roadmap.md, item 6).
- A kind owns its folders: a loose file of its type is filed there, `session` writes the kind
  into a manifest entry in such a folder and refuses an entry whose `kind` is another kind's,
  and `session --json` says the folder's kind (`"mixed"` for several).
- `irspec plot` refuses a figure it cannot draw yet, with a message: the R backend (and
  `irspec.R` run on its own) draws IR figures only, matplotlib only IR's hanging labels.
- Tests: the mutation checks of 0.2.1-0.2.3 had run under an interpreter without numpy, so they
  showed nothing; re-run properly, they found three gaps, now covered (and CLAUDE.md says how a
  harness must run).

## 0.2.3 (2026-11-11)

The first UV-Vis tools (roadmap item 6), moved from the author's lab-report package with their
output unchanged:

- New `irspec vspd`: a Shimadzu LabSolutions UV-Vis spectrum (`.vspd`) to a `wavelength,absorbance`
  CSV (`convert`), what the file says (`info`), the peak picks stored in it as a
  `\labplot[kind=uvvis]` peak list with a `ymax` suggestion (`peaks`), and a check against the
  instrument's own text export (`verify`).
- New `irspec vqud`: a quantitation file (`.vqud`) to CSVs of the standards, the unknowns and the
  calibration line (refitted from each block of standards and compared with the fit the file
  stores); `info` reads a `.vqud`, `.vqut` or `.vqum` without writing anything. A reading cell
  made only of stars (any number) counts as no reading.
- New dependency: `olefile` (BSD, pure Python, 115 kB), which reads the OLE2 container both
  formats are.
- Test files: the author's own UV-Vis scan and two quantitation files, anonymised (other groups'
  rows, names, the instrument serial number and the institution removed; `tests/data/README.md`).
  The output of both commands on them, and on the original files, is byte for byte what the
  original scripts wrote.

## 0.2.2 (2026-11-11)

The registry of plot kinds (roadmap item 6), with IR as its one kind: what irspec had hard-wired
for IR (the frame, the ticks, the x title, the padding, the TeX macro, the folders and the code
that reads and processes a file) is now one entry in `src/irspec/kinds.py`, shaped like
nulabreport's own plot kinds, and `session`, `preview`, `edit`, the TeX writer and the
matplotlib backend read it from there. Nothing an IR folder makes changes: every output of a test
session folder (the `--json` objects, the text previews, `.md`, `.tex`, CSVs, `figures.json`, the
matplotlib SVG and every exit status) is byte for byte what 0.2.1 made.

- A manifest entry whose `kind` this irspec does not know is refused, with the file and the
  reason, by `irspec session` (exit 1; 0.2.1 drew it as an IR spectrum), `session --preview`,
  `irspec preview` and `irspec edit … peak` (exit 2). `edit set`, `unset`, `move` and `remove`
  still work on it, and their `--json` reports the entry's `kind` as stored. A broken
  `manifest.json` now stops `session` with a message instead of a Python traceback.
- `irspec preview` takes its x tick labels from the same list as the figures (4,000 to 1,000 every
  500), so a crop below 1,000 cm⁻¹ no longer shows a 500 tick that the figure does not have.

## 0.2.1 (2026-11-11)

Fixes, found by comparing every output of one session folder byte for byte before a refactor.

- A second `irspec session` run no longer files what `--build latex` wrote (`ir_<dd-mm>.tex`,
  the bundled `irspec-ir.sty`, and a failed run's `.aux` and `.log`) into `other/`; they stay
  beside the report, as the `.md` and `.pdf` always did.
- `irspec edit set xmin=4000` (or `xmax=650`) with the other x limit unset is refused (exit 2,
  nothing written): the unset one is the default, 4000 or 650, and the figure would have no width.
  0.2.0 wrote it, and `irspec plot` then stopped with a Python traceback.
- Limits edited by hand into `manifest.json` that make no frame (`ymin` above `ymax` or above
  the whole spectrum, an `xmin` not below `xmax`) stop `irspec session` with the file and the
  reason, before `figures.json` is written, instead of inside lualatex. `irspec plot`
  (matplotlib) names the figure instead of printing a traceback; the R backend already did.

## 0.2.0 (2026-11-11), the command-line foundation

Roadmap item 1: a folder can be edited, previewed and read by a script without opening
`manifest.json`. From this release every landed change gets its own patch version (0.2.1,
0.2.2, ...) and its own entry here; a new minor version only for a break (README
"Versioning"). The `--json` objects are now frozen within 0.2.x: keys are added, never renamed
or removed.

- The manifest keys `xmin`, `xmax` and `ymax` now do what they say, in every drawing. `xmin` and
  `xmax` crop the x axis (cm⁻¹; `xmax` is the left edge), `ymax` is the top of the y axis, as
  `ymin` is the bottom; the TeX figure (as pgfplots keys in the `\irspectrum` call), `irspec plot`
  (matplotlib and R) and `irspec preview` / `session --preview` take them, and so does
  `figures.json` (optional keys, `SPEC_VERSION` stays 1). The padding of the frame is the same
  fraction of the span from the bottom to the top whatever sets them, and the y axis still
  scales to all of the data when a crop is set: both measured on the TeX figure (`ymax` 100 and
  110, `ymin` 20 with `ymax` 105, crops 950-2930 and 1000-3000). The preview's JSON gains `xlim`
  and `ylim`. `irspec edit set` refuses a lower limit that is not below its upper one (exit 2,
  nothing written). Without these keys nothing changes. Roadmap item 1a, last open part.
- New `--json` on `irspec session DIR` (a real run) and on `irspec peaks`. `session --json` prints
  one object on stdout, `{kind, folder, dry_run, moves, spectra, outputs, build}` (each spectrum:
  file, title, name, axis, peaks, n_peaks, ymin, csv, plain; `outputs` the files written, `build`
  the resolved mode and whether it worked), and the usual progress lines go to stderr;
  `--dry-run --json` gives the moves only. A build that fails after the work was done (for
  instance `--formats` without a PDF) still prints the object, with `"build": {"ok": false,
  "error"}`, and exits 1; a stop before the build (a QUANT-IR file with no `peak_a`) prints no
  object. `peaks --json` prints `{kind, file, format, axis, mode, peaks, bands, peaklist,
  ymin_suggestion, ymax_suggestion, settings, written}` instead of the review table (without the
  flag the output is byte for byte what it was); `peaks` are the `[wavenumber, label_y]` pairs
  everywhere, and the intensity at each is `bands`. Second part of roadmap item 1b.
- **Changed (unreleased output):** in `irspec preview --json` and `session --preview --json` the
  key `kind` (`spa`, `jdx`, `csv`) is now called `format`, and `kind` means the plot kind, `"ir"`,
  which every `--json` object now carries, `irspec edit`'s and the top level of
  `session --preview --json` too. The plot kind is how later kinds
  (UV-Vis, chromatograms; roadmap item 6) will be told apart. In `manifest.json` and
  `figures.json` an optional `kind` is read (absent means `ir`; any other value is refused, not
  drawn as IR) but not yet written, and `SPEC_VERSION` stays 1.
- New [`docs/schema.md`](docs/schema.md): every key of `manifest.json`, `figures.json` and the
  `--json` output of `session`, `peaks`, `preview` and `edit`, with the rules for stdout, errors
  and the two versions. `tests/test_json.py` fails when a key irspec writes or prints is missing
  from it.
- New `--build auto|pdfmd|latex|none` on `irspec edit` (with `--md-name` and `--pdfmd`): after the
  edit, re-run `irspec session` on the folder with that build mode, so the markdown,
  `figures.json` and PDF follow it. Off by default (as before: the manifest only); `none` rebuilds
  the markdown and `figures.json` without a PDF. An edit that changes nothing still rebuilds. When
  the rebuild fails the edit stays written, the reason goes to stderr and the exit status is 3.
  With `--json` the one object gets `"build": {"mode", "ok"[, "error"]}` and the session's progress
  goes to stderr. `show` refuses `--build`. Fourth part of roadmap item 1a.
- New `irspec edit DIR FILE move --to POSITION` and `irspec edit DIR FILE remove`. `move` puts the
  entry at POSITION in `manifest.json` (1 first, `last`, a number past the end means last, below
  1 is exit 2) and keeps the order of the others, so the figures move in the report; already
  there changes nothing. `remove` takes the entry out of the manifest and moves its spectrum
  file to `DIR/removed/` (never deleted, never overwritten: a name already there is exit 2 and
  changes nothing; the manifest is put back if the move fails), which `session` does not scan,
  so the next run does not list the spectrum again. `csv/` and `plain/` copies stay. `--json`
  prints the position change, or the whole removed entry and its new path. Third part of roadmap
  item 1a; `rename` is `set name=`, and re-running the session (`--no-build`) is not in it.
- New `irspec session DIR --preview [--width N] [--height N] [--ascii] [--json]`: the planned file
  moves exactly as `--dry-run` prints them, then every spectrum in the folder (loose, or already in
  `SPA/` and `jdx/`) drawn as `irspec preview` draws it, headed by the title, `csv/` and `plain/`
  names the file will get; pictures in `img/` are listed, not drawn. It writes nothing (no folder,
  manifest, figure list, report or moved file). An existing `manifest.json` and `--title` are
  honoured. `--json` prints one object `{"moves", "spectra", "images"}`; exit 1 when a spectrum
  could not be read (it is listed with its error, the others are shown), 2 for a folder that is
  not one or has no spectra. Second part of roadmap item 1c; `--stack` and `--image` are not in it.
- New `irspec preview FILE [--width N] [--height N] [--ascii] [--json]`: one spectrum (`.SPA`,
  `.jdx` or CSV) printed as plain text, with the wavenumber axis from 4000 to 650 left to right,
  the figure's y limits, the picked peaks marked and numbered, and a block with the detected axis
  (and the absorbance to %T conversion of a `.jdx`), the points, the ranges and the peaks with
  their label heights. Braille dots on a UTF-8 stdout, else (or with `--ascii`) `. : * |`; the
  terminal's width on a terminal, 80 columns otherwise. The peaks and `ymin` come from
  `irspec session`'s own code, and from the folder's `manifest.json` when the file is listed in
  it, so the preview shows the edits of `irspec edit`. `--json` prints one object and no plot;
  exit 2 with the reason on stderr for a file that cannot be read. First part of roadmap item 1c
  (`--stack` and `--image` are not in 0.2.0). Nothing is written.
- New `irspec edit`: `irspec edit DIR FILE set KEY=VALUE ...`, `irspec edit DIR FILE unset KEY ...`
  and `irspec edit DIR show [FILE] [--json]` change or show `manifest.json` without a text
  editor (keys: `title`, `axis`, `name`, `ymin`, `ymax`, `xmin`, `xmax`, `threshold`,
  `prominence`, `distance`). Atomic write, order and layout kept, idempotent, prints the old and
  new value (`--json`: one object), errors on stderr with exit 2 (1 for a missing manifest).
  First slice of roadmap item 1a (the figures read `xmin`, `xmax` and `ymax`: see above).
- `irspec edit DIR FILE peak add X ...`, `peak remove X ...`, `peak clear` and `peak auto`:
  second slice of roadmap item 1a. `add` snaps each wavenumber to the nearest local band
  (`find_peaks_manual`, through the code `session` itself uses, so the label heights are
  session's), `remove` takes out the stored peak nearest X within 15 cm-1, `clear` leaves none,
  `auto` picks again with the entry's `threshold`/`prominence`/`distance` and replaces hand
  edits, saying what it dropped. Same conventions as `set`/`unset` (atomic, idempotent, old ->
  new, `--json`, exit 2/1); the spectrum is read as `session` reads it, exit 2 when there is none.
- `"peaks": []` in the manifest now means "no peaks" (it used to be picked again by `session`,
  as if the key were missing), so a cleared or emptied list survives a re-run. Delete the key to
  pick again, as before.

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
