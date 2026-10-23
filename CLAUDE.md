# Working on irspec: a guide for future Claude sessions

irspec turns IR spectra (OMNIC `.SPA`, NIST WebBook `.jdx`, SDBS/book pictures) into tidy CSVs,
peak lists and report-ready figures (PDF, PNG, TIFF, SVG). Public: github.com/aliperdehan/irspec,
PyPI `irspec`. The README is the user documentation; this file is how to work on it.
It began as eight scripts of the private `nulabreport` package (`~/dev/tex/nulabreport/tools/`),
which now forward to it. Read `PROVENANCE.md` for where the code came from.

## Rules that came from the author

- **Commit first.** `git status` clean before a change. Commit and push only when asked.
  Commit messages end with the attribution line the session's system reminder gives.
- **Paths in commands.** Never type `/Users/<name>/...` in a shell command or script (the author
  shares screenshots): `~/...`, `$HOME/...`, `Path.home()`. Do not type Claude Code's own scratchpad
  or `~/.claude/projects/-Users-...` folder names: reach them with a wildcard
  (`S=$(ls -d /private/tmp/claude-*/*<project>*/*/scratchpad | head -1)`) and pipe output through
  `sed "s#$HOME#~#g"`.
- **Never `rm` with a wildcard**; list, then delete by explicit name. The shell tool is `Bash`.
- **Do not `pip install` into the system python** (Homebrew's, externally managed) unasked. The
  author runs the checkout through a shell alias: `PYTHONPATH=src python3 -m irspec ...`. Use a
  throwaway venv in the scratchpad for anything that needs an install.
- **Data.** The only published sample is the author's own `tests/data/PHENACETIN_CRUDE_LR1-2.SPA`
  (the `.jdx` fixtures are generated from it by `tests/make_fixtures.py`). Never add a classmate's
  `.SPA`, an instructor's images, or a page of a textbook (that is why `palleros_figs`,
  `spectrum_digitize`, GC, TLC, UV-Vis tools are out of scope). The coursework folders (OneDrive,
  `LR6/...`) are read-only: copy to the scratchpad and run there. `IRSPEC_LR6_IR=<LR6/ir>` turns on
  three oracle tests that compare with the author's hand-made CSVs byte for byte.
- **Measure, never guess.** Constants in `layout.py` were measured on the TeX figure; say how
  when you change one. Mutation-check a new test (break the code, see the test fail) before
  trusting it.

## Layout

```
src/irspec/   cli.py (the `irspec` command), session.py (the one command most people use),
              ir_organize.py (filing + manifest + markdown; kept as a module because nulabreport's
              tools/ir_organize.py forwards to it; session reuses its functions),
              spa_tool, spa_peaks, jdx_tool, ir_digitize, ir_corr, absorbance_to_transmittance,
              absorptivity_to_absorbance (the original eight, long docstrings = their manuals),
              figure.py (Figure, figures.json, SPEC_VERSION), texout.py (markdown + plain TeX),
              export.py (PNG/TIFF/SVG from the PDF), plot.py + mpl.py + data/irspec.R (the
              TeX-free backends), layout.py (shared geometry), fonts.py,
              data/irspec-ir.sty (GENERATED), data/fonts/ (STIX Two, SIL OFL 1.1)
tests/        unittest; PYTHONPATH=src python3 -m unittest discover -s tests   (~1 min)
              test_differential.py compares 16 commands with tests/data/differential_expected.json
              (what the original scripts did; re-record with --record DIR from the git tag
              `legacy-oracle`)
```

## Things that bit before

- **`irspec-ir.sty` is generated, never edited.** It is cut out of nulabreport's `nulabreport.sty`
  at `% >>> irspec-excerpt:NAME` markers: `python3 ~/dev/tex/nulabreport/dependencies/make-irspec-excerpt.py
  --out src/irspec/data/irspec-ir.sty` (and `--check` to compare). Its header names nulabreport's
  version, so it must be regenerated after every nulabreport version bump; nulabreport's smoke test
  fails when it has drifted. Regenerate = commit here as a patch-level change.
- **One name, one pdfmd lookup**: `ir_organize.find_pdfmd` (`--pdfmd`, `$PDFMD`, `pdfmd` on PATH).
  No author-specific path belongs in this public code. `pdfmd` is only a shell alias on the author's
  Mac; `~/.local/bin/pdfmd` is a wrapper that makes it a command.
- **`session --build auto`** uses pdfmd only when pdfmd AND nulabreport are installed, else plain
  lualatex with the bundled excerpt; the run prints which one. Do not let tests depend on which.
- **A reference spectrum (jdx/, img/) is `plain/NAME.csv`; an instrument one is
  `plain/STEM_plain.csv`.** Deliberate, documented; do not unify.
- **`session.organize` keeps `manifest.json`, `cas_names.json` and `figures.json` in place**; a
  generated file filed into `other/` on the second run was a real bug.
- **Everything is %Transmittance on the figures.** Absorbance (jdx) and QUANT-IR absorptivity are
  converted on purpose; QUANT-IR needs `peak_a` or `cl` in the manifest and irspec must never invent
  a path length.
- **A failed calibration or redraw check in `digitize` stops the session** (names the log in
  `check/`). `--palleros` with `check` makes the book's printed bands the peak list; a
  hand-edited `peaks` in the manifest always wins.
- **matplotlib needs `text.hinting: none`** to match TeX label widths (21.76 pt vs 21.7). The y
  frame rule measured on the TeX figure: bottom = base - 0.0985 x range, top = max + 0.0017 x range
  (`layout.py`); tick spacing differs from pgfplots (documented: "same figure, not same pixels").
- **Fonts**: STIX Two is used when installed, else the bundled copy (matplotlib `addfont`, R
  `systemfonts::register_font` from `fonts/` beside the script, lualatex via `irspec-fonts/`).
  `IRSPEC_BUNDLED_FONTS=1` forces the bundled ones for tests. R's pdf/svg need a cairo build
  (macOS CRAN R: XQuartz).
- **`python -m irspec` works** (`__main__.py`), which is how the alias and the tests run it.

## Versioning and releasing (README "Versioning" is the rule)

`0.MINOR.PATCH` until 1.0. `SPEC_VERSION` (figure.py) is separate and changes only when the
figures.json/manifest format breaks. `__version__` lives in `src/irspec/__init__.py` only.

Release: bump + `CHANGELOG.md` entry (a `## X.Y.Z (date)` heading; `tests/test_docs.py` checks the
version is in the changelog) in one commit on `main`; tests green; then
`git tag -a vX.Y.Z -m "irspec X.Y.Z" && git push origin vX.Y.Z`. The tag starts
`.github/workflows/publish.yml` (tag must equal `__version__`; tests; build; upload by PyPI
trusted publishing: the pending/registered publisher is this repo, `publish.yml`, environment
`pypi`: do not rename either). **Never move or re-push a published tag**; a PyPI file cannot be
replaced, fix forward with the next patch. nulabreport pins `irspec>=0.1,<0.2`.

CI (`test.yml`): Linux and macOS, Python 3.9 and 3.13; tests that need lualatex, R, poppler or
MuPDF skip themselves, so a green CI does not cover the TeX/R paths: run the suite locally with the
tools installed before releasing.

## Where the plans are

`docs/roadmap.md`: decided-but-unbuilt work (terminal preview, a Lua reader so `\irspectrum` takes
`.SPA`/`.jdx`, optional processing, a Mac app) with the order, the rules, and what to check first.
Read it before starting any of those; update it in the same commit as the code.
`docs/cloud-tasks.md`: how a slice was handed to a cloud session, the prompt template, and the
ready prompt for the next slice (peak editing).

## Where the history is

`CHANGELOG.md` (user-facing), `PROVENANCE.md` (the oracle), git tags `legacy-oracle` (last commit
with `legacy/`) and `v0.1.0`. nulabreport's own notes about the move: its `tools/CLAUDE.md`
("The IR tools now live in irspec").
