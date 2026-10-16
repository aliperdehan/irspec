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

Not copied (out of scope): `palleros_figs.py` (extracts figures from a copyrighted book),
`spectrum_digitize.py` (MS/NMR), `gc_tool.py`, `tlc_contour.py`, `scan_clean.py`,
`parse_vqud.py`.

The sample file `tests/data/PHENACETIN_CRUDE_LR1-2.SPA` is the author's own spectrum, and
the three `.jdx` files beside it are generated from it by `tests/make_fixtures.py`; nothing
else from a lab folder is published here.
