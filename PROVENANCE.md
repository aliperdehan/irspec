# Provenance of `legacy/`

The eight scripts in `legacy/` are **byte-for-byte copies** of the IR tools in
the private `nulabreport` package (`tools/`), taken at nulabreport commit
`f27951b` (2026-10-15):

`spa_tool.py`, `spa_peaks.py`, `jdx_tool.py`, `ir_digitize.py`,
`ir_organize.py`, `ir_corr.py`, `absorbance_to_transmittance.py`,
`absorptivity_to_absorbance.py`.

They are kept unchanged on purpose: `tests/test_golden.py` proves they still
reproduce the author's own phenacetin CSVs, and the next steps move their code
into the `irspec` package one piece at a time, re-running that test after each
move. Once everything lives in `src/irspec/`, this folder and this note go.

Not copied (out of scope for v0): `palleros_figs.py` (extracts figures from a
copyrighted book), `spectrum_digitize.py` (MS/NMR), `gc_tool.py`,
`tlc_contour.py`, `scan_clean.py`, `parse_vqud.py`.

The sample file `tests/data/PHENACETIN_CRUDE_LR1-2.SPA` is the author's own
spectrum; nothing else from a lab folder is published here.
