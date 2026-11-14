# Provenance

The eight IR tools in `src/irspec/` began as byte-for-byte copies of the scripts in the
private `nulabreport` package (`tools/`), taken at nulabreport commit `f27951b`
(2026-10-15):

`spa_tool.py`, `spa_peaks.py`, `jdx_tool.py`, `ir_digitize.py`, `ir_organize.py`,
`ir_corr.py`, `absorbance_to_transmittance.py`, `absorptivity_to_absorbance.py`.

The copies were kept unchanged in `legacy/` as the oracle while the code was turned into a
package (0.0.1 to 0.0.5): the only differences were nine lines (the four `sys.path.insert`
hacks and `HERE` removed, and `import jdx_tool` / `spa_peaks` / `spa_tool` turned into
`from . import ...`). Sixteen commands were run from `legacy/` and from the package on
identical inputs, comparing exit code, stdout, stderr and every file written.

`legacy/` is gone from the tree (0.1.0). It is in the git history under the tag
`legacy-oracle`, the last commit that has it (`git show legacy-oracle:legacy/spa_tool.py`;
`tests/test_differential.py --record DIR` records the outcomes again from a copy of it).
What the oracle did is kept in `tests/data/differential_expected.json`, which
`tests/test_differential.py` compares the package with; `tests/test_golden.py` checks the
author's own phenacetin CSVs byte for byte.

Not copied (out of scope): `palleros_figs.py` (extracts figures from a copyrighted book).
Not copied yet (roadmap item 6, one kind at a time): `tlc_contour.py`, `scan_clean.py`.

Moved 2026-11-11 (0.2.3): `vspd_tool.py` and `parse_vqud.py` as `irspec vspd` and
`irspec vqud` (`src/irspec/vspd_tool.py`, `src/irspec/vqud_tool.py`), output unchanged (checked
byte for byte with the original scripts on the author's original files and on the test files),
except that a reading made only of stars (any number of them) counts as no reading.

Moved 2026-11-13 (0.3.0): `gc_tool.py` as `irspec gc` (`src/irspec/gc_tool.py`),
output unchanged, checked on the author's run with 18 commands (recorded in
`tests/data/gc_expected.json`, replayed by `tests/test_gc_tool.py` on the anonymised
`tests/data/gc_lab4.RAW`), and identical on the original un-anonymised file.

Moved 2026-11-14 (0.3.6): `spectrum_digitize.py` as `irspec spectrum`
(`src/irspec/spectrum_digitize.py`), output unchanged on deterministic synthetic inputs;
`tests/record_spectrum_digitize.py` records the original twice, `tests/test_spectrum_digitize.py` replays
the command output and SHA-256 hashes in `tests/data/spectrum_digitize_expected.json`.

The sample file `tests/data/PHENACETIN_CRUDE_LR1-2.SPA` is the author's own spectrum, and
the three `.jdx` files beside it are generated from it by `tests/make_fixtures.py`. The UV-Vis
files are the author's own measurements, anonymised (`tests/data/README.md`); nothing else from a
lab folder is published here.
