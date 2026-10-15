# Provenance of `legacy/`

The eight scripts in `legacy/` are **byte-for-byte copies** of the IR tools in
the private `nulabreport` package (`tools/`), taken at nulabreport commit
`f27951b` (2026-10-15):

`spa_tool.py`, `spa_peaks.py`, `jdx_tool.py`, `ir_digitize.py`,
`ir_organize.py`, `ir_corr.py`, `absorbance_to_transmittance.py`,
`absorptivity_to_absorbance.py`.

They are kept unchanged on purpose, as the oracle for the package.

`src/irspec/` holds the same eight modules (0.0.2). The only differences from
`legacy/` are nine lines: the four `sys.path.insert` hacks and `HERE` are gone
and `import jdx_tool` / `spa_peaks` / `spa_tool` became `from . import ...`
(run `diff -r legacy src/irspec` to see exactly that). `tests/test_golden.py`
checks the author's own phenacetin CSVs byte for byte, and
`tests/test_differential.py` runs 16 commands from `legacy/` and from the
package on identical inputs and compares exit code, stdout, stderr and every
file written. The next steps rename and split the modules into a real API and
one `irspec` command, re-running both tests after each move. When everything
lives in `src/irspec/` and the tests no longer need the oracle, `legacy/` goes.

Not copied (out of scope for v0): `palleros_figs.py` (extracts figures from a
copyrighted book), `spectrum_digitize.py` (MS/NMR), `gc_tool.py`,
`tlc_contour.py`, `scan_clean.py`, `parse_vqud.py`.

The sample file `tests/data/PHENACETIN_CRUDE_LR1-2.SPA` is the author's own
spectrum, and the three `.jdx` files beside it are generated from it by
`tests/make_fixtures.py`; nothing else from a lab folder is published here.
