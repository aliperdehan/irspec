# irspec: the files and the `--json` output

This is the description a script, an AI agent or a GUI reads instead of guessing. The README
explains each command for a person; this file lists keys. `tests/test_json.py` fails when a key
that irspec writes or prints is missing here.

Two numbers version it:

- **`SPEC_VERSION`** (`figure.py`, now 1): the on-disk files, `manifest.json` and `figures.json`.
  It changes only when one of them breaks, not when an optional key is added.
- **The `--json` objects** follow the package version. From 0.2.0 a key is added, never renamed
  or removed, within a minor line (0.2.x); a reader ignores keys it does not know. A rename or a
  removal opens the next minor version and is listed in `CHANGELOG.md`.

## Conventions

- **`kind` is the plot kind**: `"ir"` (a spectrum of wavenumber against %T or absorbance) or
  `"uvvis"` (absorbance against wavelength, `uv/`). Roadmap item 6 adds others (chromatograms,
  ...). Every `--json` object says it
  (`kind` on the object, and on each spectrum inside it), so a reader never has to assume. In a
  file (`manifest.json` entry, `figures.json` entry) `kind` is optional and **absent means
  `"ir"`**; irspec writes it there only for a kind other than `ir` (`src/irspec/kinds.py`; a
  kind owns folders, and `session` fills in the kind of a file in another kind's folder, and
  refuses an entry whose stated kind does not own its folder). A reader that finds a value it does not know must refuse rather than
  draw it as IR: `Figure.from_entry`, `session`, `preview` and `edit peak` do (`edit set`, `unset`,
  `move` and `remove` work on any entry, and their `--json` `kind` is the entry's as stored).
- **`format` is the file's own format**: `"spa"`, `"jdx"`, `"csv"`, `"vspd"` (and, for a
  picture, the extension). Not to be confused with `kind`.
- **Paths** are relative to the session folder and use `/`. The one exception is the top-level
  `folder` of a `session` object (absolute) and the `file` of `peaks`/`preview` run on a loose
  file (as given).
- **Standard output** carries exactly one JSON object (or, for `edit show` without a FILE, one
  list) and nothing else. Progress lines, notes and errors go to standard error.
- **Errors.** A command that cannot do what was asked prints the reason on stderr and exits
  non-zero, printing no object. The one exception is a build that fails after the work was done
  (`session`, `edit --build`): the object is printed with `"build": {"ok": false, "error": ...}`
  and the exit status is non-zero (`session`: 1; `edit`: 3).
- **Peaks** are `[x, label_y]` pairs (for IR, the wavenumber in cm⁻¹), `label_y` in the y units
  of the figure: one decimal for IR, four for a kind whose labels stand above the band. Always
  this shape, under the key `peaks`; such a kind's apex heights are a separate list, `apex`.
- Text (`title`, `axis`) is plain, never LaTeX-escaped.

## `manifest.json`

A JSON list, one object per spectrum, in figure order. The first `session` run writes it; every
later run keeps it. All keys except `file` are optional.

| Key | Type | Meaning |
|---|---|---|
| `file` | string | the spectrum, relative to the folder: `SPA/…`, `jdx/…`, `img/…` |
| `title` | string | the caption under the figure |
| `peaks` | list of `[wavenumber, label_y]` | the labelled bands; `[]` is none, an absent key means "pick them" |
| `axis` | string | y-axis label, default `Transmittance %` |
| `ymin` | number | bottom of the y axis |
| `ymax` | number | top of the y axis (the frame goes a hair above); default the data's own maximum |
| `xmin`, `xmax` | number | crop the x axis, in cm⁻¹ (`xmax` is the left edge); default 650 and 4000. `set` refuses a lower limit that is not below its upper (an x limit alone: its default), and `session` stops on one |
| `threshold` | number | peak picking: % of the dynamic range (default 5) |
| `prominence` | number | peak picking: scipy prominence in y units (default 3) |
| `distance` | number | peak picking: least gap between peaks in cm⁻¹ (default 8) |
| `name` | string | the name of a reference spectrum (written back by the first run); a single filename component, with no path separators or drive prefix |
| `peak_a`, `cl` | number | QUANT-IR files only: the scale (never invented) |
| `check` | string | pictures only: the printed peak table, `"3490:84,2977:6"` |
| `args` | list of string | pictures only: extra flags for `irspec digitize convert` |
| `kind` | string | the plot kind; absent means `"ir"` |

## `figures.json`

What `session` writes beside the manifest, after the run: the list every drawing backend reads.
A list of objects, in figure order.

| Key | Type | Meaning |
|---|---|---|
| `spec` | integer | `SPEC_VERSION` |
| `csv` | string | the plain CSV to plot, relative to `figures.json` |
| `title` | string | caption |
| `axis` | string | y-axis label |
| `peaks` | list of `[wavenumber, label_y]` | as above |
| `ymin`, `ymax`, `xmin`, `xmax` | number | present when set, as in the manifest |
| `width`, `height` | string | TeX lengths; mean nothing outside TeX; present when not the default |
| `kind` | string | optional; absent means `"ir"` |
| `apex` | list of number | a kind whose labels stand above the band: the trace's height at each peak, same order as `peaks`; absent for IR |

## `irspec session DIR --json`

A real run, `--dry-run`, or (with `--preview`) the preview below. The progress lines go to stderr.

| Key | Type | Meaning |
|---|---|---|
| `kind` | string | the one kind of the folder's spectra (`"ir"`), or `"mixed"` |
| `folder` | string | the folder, absolute |
| `dry_run` | boolean | true under `--dry-run`: then only `kind`, `folder`, `dry_run` and `moves` exist |
| `moves` | list of objects with `from` and `to` | loose files filed into `SPA/`, `jdx/`, … (made, or planned) |
| `spectra` | list | one per figure, in order (below) |
| `outputs` | object | what was written (below) |
| `build` | object | `mode` and `ok` and, when `ok` is false, `error`; `mode` is the resolved one: `pdfmd`, `latex` or `none` |

A `spectra` item:

| Key | Type | Meaning |
|---|---|---|
| `file` | string | the manifest `file` |
| `kind` | string | `"ir"` |
| `title`, `name`, `axis` | string | caption, the name the CSVs carry, y-axis label |
| `peaks` | list of `[wavenumber, label_y]` | as drawn |
| `n_peaks` | integer | how many |
| `ymin` | number or null | |
| `csv`, `plain` | string | the archival and the plain CSV |

`outputs`: `manifest`, `figures`, `markdown` (strings), `tex` and `pdf` (string, or null when not
made), `pictures` (list of strings, from `--formats`).

## `irspec session DIR --preview --json`

Writes nothing. `{kind, moves, spectra, images}`: `kind` as in a real run; `moves` as above; `spectra` one object per `.SPA` or
`.jdx`, each the `irspec preview` object (below) plus `will_be_filed_as`, `title`, `csv`, `plain`
(or `error`, with the exit status 1, for one that could not be read); `images` one object per
picture (`file`, `kind`, `name`, `csv`, `plain`, `note`): pictures are digitized by a real run,
not drawn here.

## `irspec preview FILE --json`

| Key | Type | Meaning |
|---|---|---|
| `file` | string | as given |
| `kind` | string | `"ir"` |
| `format` | string | `spa`, `jdx` or `csv` |
| `axis` | string | what the figure's y axis is called |
| `converted_from` | string or null | `"Absorbance"` when it was converted to %T |
| `points` | integer | points in the file |
| `range` | object with `x` and `y` | each `[min, max]`; `y` is the figure's window |
| `ymin` | number or null | |
| `xlim`, `ylim` | `[left, right]`, `[bottom, top]` | the frame the figure would have: the crop or 4000 to 650, and the y axis with its padding |
| `peaks` | list of `[wavenumber, label_y]` | |
| `peaks_from` | string | `"automatic"` or `"manifest.json"` |

## `irspec peaks FILE --json`

Instead of the review table. A `.SPA` input still writes its two CSVs, as it does without
`--json`; they are listed in `written`.

| Key | Type | Meaning |
|---|---|---|
| `kind`, `file`, `format`, `axis` | | as in `preview` |
| `mode` | string | `auto` or `manual` |
| `peaks` | list of `[wavenumber, label_y]` | the figure's pairs |
| `bands` | list of number | the intensity at each peak, same order, kept apart so `peaks` has one shape |
| `peaklist` | string | the `x/label_y,…` argument of `\irspectrum` |
| `ymin_suggestion` | integer or null | %T spectra with peaks |
| `ymax_suggestion` | integer or null | absorbance spectra with peaks |
| `settings` | object | `threshold`, `prominence`, `distance`, `gap`, `collision_cm`, `step` |
| `written` | list of string | CSVs written (a `.SPA` input only) |

## `irspec edit DIR FILE … --json`

For `set`, `unset`, `peak` and `move`: an object with `kind`, `file` and `changes`, where `changes`
is a list of objects with `key`, `old` and `new` (`old` null for a key that was not there, `new` null after `unset`; a peak has
`key` `"peak"` and the pair as `old`/`new`; `move` has key `"position"`). `remove` gives
`kind`, `file`, `removed` and `moved_to`, `removed` being the whole manifest entry that was taken out
and `moved_to` `"removed/NAME"` or null. With `--build` the object gains `build`, with `mode` and `ok`
(and `error`); a failed rebuild exits 3 with the object still printed.

`irspec edit DIR show [FILE] --json` prints the entry as stored (an object), or all entries as a
list; the entries are the manifest's, with no key added.
