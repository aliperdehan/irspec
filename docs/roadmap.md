# Roadmap and decisions (recorded 2026-10-17, nothing here is implemented)

This is the author's working list, not a promise to users: the README's "Roadmap" is the public one.
Each item says what was **decided**, why, and what to **check first** before building. A future
session should start from this file instead of re-deriving it. If a decision turns out wrong,
change it here in the same commit as the code.

Origin: a chat comparing irspec with other FTIR tools (an "FTIR Analysis Pipeline" CLI, "FTIR Peak
Analyzer", `orca_ir`). **Those three were described by a chatbot and nobody here has opened their
repositories**: check what they really do and, above all, their licences before relying on any of it.

## Principles (apply to every item below)

1. **The command line is the one capability surface.** The terminal preview, the Mac app and any
   AI agent are clients of the same commands. If the app can do something, a command does it
   headlessly; the app invents nothing the CLI cannot do. Consequences: every command that reads
   or changes something works without a terminal and without prompting (a question is a flag),
   prints machine-readable output with `--json`, and exits non-zero on failure with the reason
   on stderr. A change a user makes by clicking must be a change an agent can make by typing.
2. **Raw data is never overwritten.** Anything derived (cache, processed spectrum) lives in a
   separate file and is regenerable from the manifest.
3. **One implementation per algorithm, unless TeX forces a second.** Where two exist (Python and
   Lua), a differential test pins them to each other on every fixture, and it is
   mutation-checked.

## Order of work

| # | What | Release | Why this order |
|---|------|---------|----------------|
| 1 | CLI foundation: `irspec edit` (manifest editing), `--json`, the manifest schema, `irspec preview` | 0.2.0 | Everything else (TUI, app, agents) is a client of it |
| 2a | Tidy first: one trace macro in `nulabreport.sty` replaces the four copies, output pixel-identical | nulabreport patch; irspec patch (regenerated excerpt) | A refactor with no new behaviour, so any pixel difference is a bug |
| 2b | `\irspectrum` reads `.SPA`/`.jdx` itself, `peaks=auto`, x/y ranges | 0.3.0 (+ nulabreport minor) | Measured feasible; a change in one place, thanks to 2a |
| 3 | Optional processing: smoothing, band area, baseline | 0.4.0 | Opt-in, never touches raw files |
| 4 | Mac app (SwiftUI), in this repository under `app/` | not on PyPI | Go/no-go after a prototype on top of 1 |
| 5 | Export for publishing a spectra collection (JCAMP-DX writer, per-spectrum metadata, dataset README) | not scheduled; after the author's course ends | The author plans a Zenodo/GitHub collection of their own SPA spectra; see item 5 |
| - | Deconvolution, calculated spectra | not scheduled | See "Not now" |

Everything here is a minor bump (new feature), per the README's versioning rule. `SPEC_VERSION`
moves only if the manifest or `figures.json` format breaks; adding optional keys does not.

## 1. CLI foundation: editing, JSON, preview

### 1a. Editing: `irspec edit`

**Decided.** Today the manifest is edited by hand in a text editor, which is the only "edit"
there is. It becomes commands (names provisional; `irspec peaks` is already the peak picker for a
file, so editing is a new `edit` command, not an overload):

```
irspec edit DIR FILE peak add 1720 [3253 ...]       # snapped to the nearest local band
irspec edit DIR FILE peak remove 3253
irspec edit DIR FILE peak auto [--prominence ...]   # (re)pick; clears hand edits, says so
irspec edit DIR FILE peak clear
irspec edit DIR FILE set title="Phenacetin (crude)" ymin=-5 xmin=650 xmax=4000 ymax=100
irspec edit DIR FILE unset ymin
irspec edit DIR FILE rename NAME | remove | move --to POSITION
irspec edit DIR show [FILE] [--json]
```

- It changes `manifest.json` only (atomic write: temp file, then rename), then, unless
  `--no-build`, re-runs the session for that figure so the PDF follows. Idempotent: the same
  command twice leaves the same manifest.
- Peak snapping reuses `find_peaks_manual`; automatic peaks reuse `find_peaks_auto` and
  `assign_label_y`. No new picking code.
- New optional manifest keys `xmin`, `xmax`, `ymax` (with the existing `ymin`). Optional keys do
  not bump `SPEC_VERSION`, but `layout.XLIM` is a constant today (and repeated in `irspec.R`):
  it becomes a per-figure value in the Python, matplotlib and R drawing code, with tests.
- Every edit prints what it changed (`--json`: the old and new value), so an agent can verify.

### 1b. `--json` and the schema

`--json` on `session`, `edit`, `peaks`, `show` and `preview`: items, detected axis, peaks, ymin,
output paths, warnings. A written, versioned description of `manifest.json` and `figures.json`
(the README table is the start) so that no client guesses.

### 1c. Terminal preview

**Decided.** Read-only preview, not an editor: editing is 1a (commands) and, for humans who like
clicking, item 4. A curses editor would be a third way to do the same thing.

- `irspec preview FILE...` draws one spectrum (or `--stack`) in the terminal: wavenumber axis
  4000 to 650 left to right as in the figures, the %T convention, picked peaks marked and
  numbered, and a text block with what the pipeline will do: detected axis (and the conversion if
  absorbance), point count, the file name and folder it will get, the peaks.
- `irspec session --preview` (and `--dry-run`, which already prints the file moves) shows the same
  for every file before anything is filed. This is the "know what is going out through the
  pipeline" part, and the more useful half.
- **Nothing interactive, so no TUI to depend on** (decided 2026-10-17). The preview is a plain
  dump to stdout, sized to the terminal: width from `shutil.get_terminal_size()`, or 80 columns
  when stdout is not a terminal (a pipe, a log, an agent), `--width N` / `--height N` to override.
  The same text either way; what a terminal adds is optional polish only (Braille dots, colour),
  never required. Braille (2x4 dots per cell) when stdout is a UTF-8 terminal, `--ascii` for
  `. : * |` otherwise. Standard library only; no `rich`/`textual`/`curses`.
- Optional `--image`: when the terminal speaks the kitty or iTerm2 image protocol, show the real
  exported PNG. Detect, never assume (Terminal.app has neither). Last.
- **Draw from the same objects the figure uses** (`Figure`, the limits in `layout.py`, the peaks as
  written to `figures.json`), never from a second computation, or the preview can lie.
- **Honest limit, printed in `--help`:** shape, ranges, peak positions and which are labelled.
  Not fonts, exact label placement or tick spacing.
- Test with golden strings on the sample `.SPA`; mutation-check.

**Check first:** how `session` builds its figure list, so `--preview` hooks in before filing.

## 2. `\irspectrum` reads the instrument file itself

**Decided (the author, 2026-10-17):** the existing `\irspectrum` is the interface: no
`\irspectrumspa`. It dispatches on the file extension (`.spa`, `.jdx`, `.dx`; anything else is CSV as
today), so old documents render as before. Also decided: peaks can be `auto`, and the x and y
ranges are chosen inside the same call.

**Feasibility, measured 2026-10-17:** a 20-line `texlua` script using `string.unpack` read
`tests/data/PHENACETIN_CRUDE_LR1-2.SPA` (3734 points) in 0.02 s and matched `read_spa` to 5e-7
(that was only the `%.10g` output formatting; use `%.9g` for float32). LuaTeX 1.24 (TeX Live 2026)
has Lua 5.3, which provides `string.unpack`. The SPA layout is a few fixed offsets.

**Where it plugs in, and the tidy that comes first (2a).** The trace is added by the same line
`\addplot[color=\Lab@tc, line join=round] table[nulab kind K table, col sep=comma] {csv}` followed
by `\csname Lab@kind@K@peaks\endcsname{peaks}`, copied at four places in the excerpt
(`\Lab@plotbody`, `\Lab@insetaxis`, `\Lab@stackpanel`, `\Lab@ovpanel`); two of the copies use
`\expanded` for `\Lab@tc` because pgfplots builds a panel's plot late (the comments there explain
the colour swap that taught this). `\irspectrumstack`, `\irspectrumoverlay` and
`\irspectrumcompare` have their own bodies but end in these.

**Decided (the author, 2026-10-17): change it once, not four times.** First a pure refactor in
`nulabreport.sty` (2a): one macro, `\Lab@addtrace{kind}{csv}`, using the `\expanded` form (safe
where the plain form was safe), called from the four sites. The peaks call stays separate: in
`\Lab@plotbody` `\Lab@inintegrals` sits between the trace and the peaks. 2a changes no output:
verify with the pixel diff nulabreport already uses for this (`CHANGELOG` v1.19.0 and v1.25.0 did
the same), on every figure kind, single, inset, stack, overlay, compare. Only then does 2b add
behaviour, in that one macro plus a resolver:

- `\Lab@tracefile{csv}` runs **before the axis opens** (ymin and the crop are axis options, so
  the data must be known first), and sets the path to read (the cache for `.SPA`/`.jdx`, the same
  path for a CSV) and the data's range;
- `\Lab@addtrace` reads that path; `\Lab@peaksfor{csv}{peaks}` turns `auto` into the explicit list
  before the existing peaks macro runs.
Then everything built on the four sites gets direct reading, `auto` and the ranges together.

### What the call does

- **Reading.** Lua parses the file, converts Absorbance to %T (`100 * 10^-A`), clips to the
  figure's window as `write_plain_csv` does (>= 650 cm-1), and writes a cache CSV
  (`.irspec-cache/NAME.csv`) that the existing pgfplots path reads. One drawing path; Lua draws
  nothing. JCAMP: plain AFFN `##XYDATA`/`##XYPOINTS` only; ASDF/SQZ/DIF is refused with the
  same message as `jdx_tool`. QUANT-IR absorptivity stays Python-only (needs `peak_a`/`cl`;
  irspec never invents a path length).
- **The `plain/` CSV becomes redundant for TeX, not for irspec.** `irspec session` keeps writing
  it, because `figures.json`, the R script (standalone, no OMNIC reader), `corr`, `peaks` and other
  programs read it. It is documented as derived and regenerable; a nulabreport project needs only
  the `.SPA`. `csv/` (archival) is unchanged.
- **Default window 4000 to 650.** The `ir` kind already sets `xmin=650, xmax=4000`; the Lua clip
  matches it, so a CSV is no longer needed to be pre-clipped.
- **Ranges inside the call.** `[xmin=2000, xmax=1000, ymin=30, ymax=100]` in the existing option
  list. `xmin`/`xmax` crop the data and the peak scan (not only the frame); `ymin`/`ymax` set the
  frame. With direct reading the macro knows the data, so when `ymin` is not given and peaks are
  labelled it computes the headroom itself (a port of `suggest_bounds`) instead of making the
  author guess; an explicit key always wins. Today's rule "always give `ymin` once peaks are
  labelled" goes away for file input.
- **`peaks=auto`: defaults only in the first version** (the author: the defaults are what 99% of
  cases need; tuning is added gradually, later). The peaks argument is a list `x/label_y,...`
  (explicit, as now), empty (none), or `auto`. `auto` ports `find_peaks_auto` (the scipy
  local-maxima, prominence and distance rules, plus the depth gate) and `assign_label_y` to Lua.
  **This reverses the earlier "no peak picking in Lua" decision**: the alternative is shelling out
  to `irspec`, which needs `--shell-escape`, and the author wants it to work in plain `lualatex`.
  The price is a second implementation; Principle 3 pays it: the test runs the Lua picker and
  `find_peaks_auto` on every fixture, plus ~200 random synthetic spectra, and requires identical
  peaks and label positions. The picked list is **written to the log** as the explicit
  `x/label_y,...` string, so an auto result can be reviewed and frozen by pasting it back.

### Boundaries

- Needs `lualatex` (nulabreport already does). Others keep using `irspec session`; the macro's error
  says so.
- Source of truth for the Lua is here (`src/irspec/data/irspec-read.lua`), because the tests are:
  they run `texlua` and compare with `read_spa`/`find_peaks_auto` (skipped when `texlua` is
  absent). nulabreport vendors a copy and its smoke test fails on drift: the arrangement of
  `irspec-ir.sty`, in the other direction. `write_excerpt` copies it beside the `.tex` as it does
  `irspec-fonts/`. The macro change itself is made in `nulabreport.sty` inside an
  `irspec-excerpt` region and the excerpt regenerated (patch bump here, version bump there).

**Check first:** `io.open` of a document-relative path and writing the cache under the default
`shell_escape` / `openout_any`; how `\Lab@labplot` passes the option list (the new keys need a
small key family that reads them and still hands everything to pgfplots unchanged); what
`suggest_bounds` computes, to port it exactly.

## 3. Optional processing

**Decided: implement it ourselves in `numpy`/`scipy` (already dependencies); do not depend on
the other tools and do not copy their code.** The algorithms are published: asymmetric least
squares baseline (Eilers and Boelens 2005), Savitzky-Golay smoothing (`scipy.signal.savgol_filter`),
min-max / area normalisation, trapezoid band area. Their licences then do not matter.

**What baseline correction is, for the record.** A real spectrum sits on a slowly varying
background: scattering from the sample, a sloping or curved offset, drift, the ATR crystal's
response. Bands should rise from a flat zero, but they ride on that curve, so their apparent heights
and areas include it. Baseline correction estimates the smooth background (a polynomial through
the points that are clearly "no band", or a smooth curve that stays under the data, which is what
ALS does) and subtracts it. It matters when you compare band intensities or integrate areas; it
does not matter for quoting band positions, which is what the lab reports ask. It is done on
absorbance (subtraction is meaningful there), so a %T spectrum is converted, corrected, and
converted back. The risk is a wrong baseline: too flexible and it eats a broad band (an O-H
stretch), too stiff and it leaves the slope in. Hence the rules below.

- **Off by default.** A report figure is the raw %T spectrum with labelled peaks unless asked.
- **Raw is never overwritten.** Processed data goes to its own file; the manifest records the
  step and parameters (`process`: method, parameters, irspec version), so the figure regenerates.
- **A processed figure says so**, in a note irspec adds to the caption ("baseline-corrected, ALS,
  lambda=..., p=..."), not left to memory.
- Peaks are picked on the data the figure shows, and the manifest says which.
- `irspec process FILE --baseline als --smooth 9 --normalise max`, `irspec area FILE
  --range 1700-1650`; as `edit set` keys in a session. Names provisional.
- **Show the baseline.** The preview and the figure option draw the estimated baseline under
  the trace, because the only way to trust one is to look at it.

The author's courses do not ask for baselines, so this ships small first: smoothing and band area,
then ALS with the visible-baseline check, as a "would be nice" and a learning exercise.

## 4. Mac app

**Decided (the author, 2026-10-17): in this repository, under `app/`, so whoever needs it finds it
next to the CLI and builds it; and thin. Go/no-go still after item 1**, from a prototype on the
JSON and `edit` commands. The app invents nothing (Principle 1): it calls `irspec edit`,
`irspec preview --json`, `irspec session` and shows the PDF those produced. Its only own code is
drawing the spectrum interactively and turning a click into an `edit` command.

- In the repo, but not in the package: `app/` is not under `src/`, so the wheel does not carry it,
  and the sdist excludes it explicitly (`MANIFEST.in`: `prune app`), with a test that the
  built sdist has no `app/`. No Swift in the Python tests; `app/` has its own README with the
  build command. It is built from the same checkout as the CLI it calls, and refuses an
  `irspec` whose `--version` or `SPEC_VERSION` it was not written for.
- Build in CI only if cheap (a macOS runner and `xcodebuild`, no signing); never a gate for the
  PyPI release.
- Display: SwiftUI + Swift Charts (macOS 13+), data from the CLI's JSON; the final figure from the
  CLI's PDF (PDFKit), so what you see is what the report gets.
- v1 fence: open a folder; zoom and pan; click to add a peak, drag or delete one; title and range
  fields; the real figure; export. **Out:** baseline editing, deconvolution, library search,
  arithmetic between spectra. A lite SpectraGryph for the Mac, not a clone.
- How hard? The SwiftUI part is modest (a chart with click handling, a list, a PDF view: guess
  1-2 thousand lines) once the CLI gives JSON and edit commands. The hard parts are elsewhere:
  needing `irspec` (Python, numpy, scipy) and optionally TeX on the machine, and distribution.
  Bundling Python with numpy and scipy is hundreds of MB.
- **Distribution and the App Store.** Not free: the Apple Developer Program is 99 USD a year (check
  the current price). More important, the **App Store is a poor fit**: App Store apps must be
  sandboxed, and a sandboxed app cannot freely run `irspec`, `lualatex` and `pdftoppm` from
  elsewhere on the disk, so it would have to carry all of them. Realistic options, cheapest first:
  (1) source build in Xcode from `app/`, free with a personal Apple ID, for the author and anyone
  technical (this is the plan);
  (2) a signed and notarised download outside the App Store (same 99 USD) so it opens without
  Gatekeeper warnings; (3) the App Store only if it ever bundles everything. Decide when someone
  besides the author wants it.

## 5. Publishing a collection of the author's own spectra

**Origin (2026-10-19).** The LR8 work found no public IR of phencyclone, and the author plans to
collect their own undergraduate organic-lab `.SPA` files after the course ends into a spectra
database: a compiled PDF on Zenodo (and ResearchGate as a mirror), the source files on GitHub.
Nothing here is implemented, and the publishing itself is the author's task, not irspec's. irspec
only has to make the export cheap and correct.

**Decided (plan, not built).**

- **Zenodo is the canonical home** (data, PDF, DOI, versioned); GitHub holds the source, linked
  through Zenodo's GitHub integration so each tagged release is archived. ResearchGate only
  mirrors the PDF with the Zenodo DOI. Licences: CC0 for the spectra, CC-BY for the PDF, the
  code's own licence for the code.
- **Own measurements only.** Nothing digitised from the manual or taken from NIST or SDBS goes in
  (copyright and terms); cite those instead. The Palleros-derived CSVs stay out.
- **SPA is proprietary, so ship JCAMP-DX or CSV beside it.** Needs an irspec **JCAMP-DX writer**
  (the reader exists). **Check first:** whether one is already there, which JCAMP-DX dialect and
  which `##` labels suit SpectraBase/NIST-style readers, and a round-trip test (write, read, same
  data).
- **Per-spectrum metadata, recorded when measuring:** compound, CAS, InChIKey, technique (ATR or
  mull), instrument, resolution, scans, background, date, sample provenance (how made, m.p.,
  appearance) and a plain purity status (crude, recrystallised, unverified). A student sample is
  often crude; label it, do not hide it. Candidate home: optional manifest keys (adding optional
  keys does not bump `SPEC_VERSION`) rather than a second file.
- **A dataset command** (name provisional, e.g. `irspec dataset DIR`) that builds the release
  folder: `raw/` (SPA), `jdx/`, `csv/`, a metadata table and a README. Headless with `--json`,
  like every command (principle 1).
- **Ship small, then grow:** v0.1 with a handful of the best spectra, phencyclone and its adduct
  among them, then add per semester.

**Before publishing (not code):** ask the department or instructor (the instrument and the lab
are the university's); do it after the course ends.

**Maybe later:** a short data-descriptor paper. Which journals take a collection this size is
unchecked.

## Not now

- **Deconvolution / Lorentzian band fitting.** Reports are %T with band positions; fitted components
  are model estimates, not proof of separate vibrations. Revisit if a course asks. Then: a separate
  command on absorbance, fit statistics printed.
- **Calculated spectra (`orca_ir`-like).** Parses quantum-chemistry output, a different input
  family. If ever needed: an overlay of a two-column frequency/intensity file, not an ORCA parser.
- **Functional-group assignment and compound identification.** `ir_corr` is a correlation lookup;
  identifying an unknown is a different product.
- Still out of scope as in the README: MS, NMR, GC, TLC, UV-Vis, and extracting figures from books.

## Later, in nulabreport (not irspec work, recorded because it touches this)

The author wants nulabreport usable as a kit without the lab rules: `\usepackage[nolab]{nulabreport}`
(or simply no lab option) loads the building blocks (ir, mass, gc, ...) and does not force the
house layout. Not now. Notes for when it is: item 2a's single trace macro is the kind of
consolidation that split needs; `irspec-ir.sty` stays as the excerpt for people without
nulabreport (it is private), so keep `% >>> irspec-excerpt:NAME` regions working through the split,
and the smoke test that compares the excerpt page with the full package's.

## Open

- Mac app: go or no-go after item 1 (a prototype answers "how hard").
- Collection export (item 5): does irspec already write JCAMP-DX, and where do the per-spectrum
  metadata live (manifest keys or a separate table)?
