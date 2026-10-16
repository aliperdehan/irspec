# Changelog

irspec follows the rules in the README's "Versioning" section. Newest first.

## Unreleased (will become 0.1.0, the first release)

Everything below is already in the repository; 0.1.0 is the tag that says it is
ready to be used by someone else, and it is cut when the author says so.

- `irspec session DIR`: a folder of `.SPA`, `.jdx` and SDBS-style pictures in;
  archival and plain CSVs, peak lists, a manifest, a figure PDF out.
- `irspec export PDF` and `session --formats`: PNG, TIFF and SVG (outlined or
  with editable text) from the figure PDF, one file per spectrum.
- The figure PDF is built by nulabreport's `pdfmd` when it is installed, else by
  plain `lualatex` from a generated `.tex` that uses the bundled excerpt
  `irspec-ir.sty`.
- The older tools as sub-commands: `spa`, `jdx`, `peaks`, `digitize`, `a2t`,
  `absorptivity`, `corr`.
- Manifest and figure format: `SPEC_VERSION = 1`.

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
