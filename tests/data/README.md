# Test data

Every file here is the author's own measurement, or made from one.

| File | What | Made how |
|---|---|---|
| `PHENACETIN_CRUDE_LR1-2.SPA` | the author's crude phenacetin, Nicolet iS5 FTIR, diamond ATR | as measured |
| `golden_archival.csv`, `golden_plain.csv` | its two CSVs, made by the original scripts | `tests/test_golden.py` compares |
| `phenacetin_T.jdx`, `phenacetin_A.jdx`, `phenacetin_quantir.jdx` | JCAMP-DX in three shapes | `tests/make_fixtures.py`, from `golden_plain.csv` |
| `differential_expected.json` | what the original scripts did, for `tests/test_differential.py` | recorded from the tag `legacy-oracle` |
| `uvvis.vspd` | a UV-Vis scan, Shimadzu UV-2600, 200-700 nm, 101 points | anonymised (below) |
| `uvvis_golden.csv` | its CSV, made by nulabreport's `vspd_tool.py convert` | |
| `quant_510nm.vqud` | a quantitation file at 510 nm: 6 standards and one unknown | anonymised (below) |
| `quant_540nm_blocks.vqud` | an older quantitation file at 540 nm (`WL540.0 Modified` column, several calibration blocks) | anonymised (below) |

## The UV-Vis files: what was changed

The three instrument files are OLE2 containers. They were anonymised with
`tests/anonymise_ole.py`, which changes bytes in place so that every stream keeps its size, and
then zeroes every free sector, free mini sector and the slack after each stream, so no stale copy
of anything removed is left. Approved by the author, 2026-11-11.

- **`uvvis.vspd`**: the author's own scan (its original name was a placeholder; the data-set
  name in its history now reads `UV-Vis 1`). The institution and the instrument's serial number
  are blanked (`(institution)`, `A00000000000`). The spectrum and the peak picks are untouched:
  `irspec vspd convert` gives the same CSV as the original file.
- **`quant_510nm.vqud`**: a shared lab file. Kept: the 6 standards (the class's common
  calibration) and the author's pair's unknown (group 2, its name now `Unknown 1`). The other
  five groups' unknowns are removed: their names and readings are stars (`*****`, the
  instrument's own "no reading") with the "no value" double, and their Column Data cache values
  are stars too. Institution and serial number blanked as above. What stays of the other rows:
  their row numbers, Sample IDs (`Un 2`, ...), types, dates and times.
- **`quant_540nm_blocks.vqud`**: a shared file several groups appended their curves to. Kept: the
  author's calibration block (groups 41-47: blank and 1-10 mg) and the author's unknown (group
  6). The other blocks and unknowns are removed as above, except that a reading of six
  characters (`-0.000`) became `******`, six stars, because the stream keeps its size; irspec
  takes any value made only of stars as no reading. The nominal concentrations of the removed
  standards stay (the protocol's 1-10 mg), and so does the fit the file stores (K1 0.0625624,
  K0 -0.0054158), which is not a fit of the author's block. Institution and serial number
  blanked.

Each kept row is identical to the original file's, text and full-precision value: checked
by reading both with the same code.
