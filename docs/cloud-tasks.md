# Handing a roadmap slice to a cloud session

How the first slice of `docs/roadmap.md` (item 1a, `irspec edit set/unset/show`) was done by a
cloud agent, what to copy from it, and the prompt for the next slice. Written 2026-10-23.

## What worked

- **A slice that fits one pull request**: one new module, its tests, README and CHANGELOG lines.
  The first one took about 15 minutes and 107k agent tokens; 33 mutations of `edit.py`, 40 new
  tests, CI green on Linux and macOS, Python 3.9 and 3.13.
- **Everything the agent needs is in the pushed repo**: the prompt says "read `CLAUDE.md` and
  `docs/roadmap.md` first", so push the roadmap before launching. A cloud session clones from
  GitHub and cannot see unpushed work or the private `nulabreport` repository.
- **The agent never merges, tags or releases** (the prompt says so). Review is local: check the
  branch out and run the whole suite, because the cloud box may lack `lualatex`, R and poppler
  (this one had `lualatex`; tests that need a missing tool skip themselves, so green CI does not
  cover the TeX/R paths).
- **Merge as a rebase** (`gh pr merge N --rebase`): `main` stays linear, the commit keeps its
  message.

## What is not known

Whether a cloud run counts against the plan's usage or the bonus credits. One trial (2026-10-23):
the credit counter did not move, the usage bar went 16% to 18% while another session was running
in parallel, so the 2 points cannot be attributed. Weak evidence for "plan usage, not bonus
credits". A clean test needs everything else idle.

## Template: a prompt that works

```
Repository: github.com/aliperdehan/irspec (Python package `irspec`, MIT, public). Read
`CLAUDE.md` and `docs/roadmap.md` (the section named below and the Principles) first, then do
ONE small slice of that section: <the slice, with the exact commands and the keys>.
Do NOT implement <the neighbouring items>.

Requirements:
- <behaviour: exit codes, --json, stdout vs stderr, idempotence, atomic writes>
- Register the command in `cli.py` like the others; add a README section (`tests/test_docs.py`
  requires every command to be mentioned as `irspec <cmd>`); add a line under `## Unreleased`
  in CHANGELOG.md; update the roadmap to say what is done. Do NOT bump `__version__`, tag or
  release.
- Code in a new module (or the module named); tests in `tests/` (unittest,
  `PYTHONPATH=src python3 -m unittest discover -s tests`). Mutation-check each new test (break
  the code, see the test fail, restore). Tests that need lualatex/R/poppler skip themselves.
- Rules from CLAUDE.md apply: never `rm` with a wildcard, never type /Users/<name> paths, do not
  pip install into a system python (use a venv).

Work on a new branch `claude/<slice-name>`, commit there (end commit messages with:
Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>), push it, and open a pull request
against main (end the description with: 🤖 Generated with [Claude Code](https://claude.com/claude-code)).
Do not merge it. Report the PR URL and the test result in your final message.
```

Keep to one slice per run, name what to leave alone, and say what the agent must not touch
(`session.py`, `ir_organize.py`, `irspec-ir.sty`, which is generated).

## Next slice: peak editing (roadmap 1a, second part)

Paste into a cloud session on `aliperdehan/irspec` (or launch it from Claude Code with a remote
agent). It builds on `src/irspec/edit.py` as merged.

```
Repository: github.com/aliperdehan/irspec (Python package `irspec`, MIT, public). Read `CLAUDE.md`,
`docs/roadmap.md` (section "1a. Editing: irspec edit" and the Principles) and `src/irspec/edit.py`
with `tests/test_edit.py` (already merged: `set`, `unset`, `show`) first, then do ONE small slice:
add peak editing to `irspec edit`, working on `DIR/manifest.json` only:

  irspec edit DIR FILE peak add X [X ...]      # each X snapped to the nearest local band
  irspec edit DIR FILE peak remove X [X ...]   # removes the stored peak nearest X within a tolerance
  irspec edit DIR FILE peak clear
  irspec edit DIR FILE peak auto               # (re)pick with the file's threshold/prominence/distance

Do NOT implement rename/remove/move, per-figure xmin/xmax/ymax in the drawing code, re-running the
session (`--no-build`), preview, or any other roadmap item.

Requirements:
- Reuse existing code, write no new picking code: `find_peaks_manual` for snapping, `find_peaks_auto`
  and `assign_label_y` for `auto`, both in `src/irspec/spa_tool.py`. Read the README's manifest table
  for the format of the `peaks` key and keep exactly that format and the label placement `session`
  would produce, so `irspec session` on the edited manifest draws the same peaks. A hand-edited
  `peaks` always wins over automatic picking (see CLAUDE.md), so `add`/`remove`/`clear` write an
  explicit list.
- Needs the spectrum itself to snap: read it from the file's `plain/` or `csv/` copy next to the
  manifest, as `session` does. If it is missing, exit 2 with a clear message on stderr.
- Same conventions as the merged commands: atomic write, entry and key order kept, idempotent
  (a peak already present, or absent on `remove`, changes nothing and is not an error), prints each
  change as old -> new, `--json` prints exactly one object on stdout, errors on stderr, exit 2 for
  a command that cannot be carried out and 1 for a missing or broken manifest. `peak auto` says
  that it replaces hand edits and lists what it dropped.
- Register in `cli.py` as for the merged ones, extend the README section "Editing the manifest:
  `irspec edit`", add a line under `## Unreleased` in CHANGELOG.md, and update the roadmap's 1a
  "Done/Not done" paragraph. Do NOT bump `__version__`, tag or release.
- Tests in `tests/test_edit.py` or a new `tests/test_edit_peaks.py`, using only the sample
  `tests/data/PHENACETIN_CRUDE_LR1-2.SPA` (copy it into a temp dir and build a manifest, or run
  `irspec session --build none` on it). Mutation-check each new test. One test must run
  `irspec session --build none` after an edit and check the edit survives and reaches `figures.json`.
- Rules from CLAUDE.md apply: never `rm` with a wildcard, never type /Users/<name> paths, no pip
  install into a system python (use a venv).

Work on a new branch `claude/edit-peaks`, commit there (end commit messages with:
Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>), push it, and open a pull request
against main (end the description with: 🤖 Generated with [Claude Code](https://claude.com/claude-code)).
Do not merge it. Report the PR URL and the test result in your final message.
```

## The first prompt, as it was sent

For the record: the template above filled in for `set`/`unset`/`show`. Its result is merged
(`4960b41`, PR #1). Allowed keys were `title`, `axis`, `ymin`, `ymax`, `xmin`, `xmax`,
`threshold`, `prominence`, `distance`, `name`; numeric keys stored as JSON numbers (non-numeric
refused with exit 2); FILE matched by exact path, then file name, then stem.

## Candidates for later slices

Each is one pull request and independent of the others, in the order the roadmap gives:

1. Per-figure `xmin`/`xmax`/`ymax` read by the Python, matplotlib and R drawing code
   (`layout.XLIM` becomes per-figure). Needs R and a TeX build to check, so review locally.
2. `rename`/`remove`/`move` and `--no-build` (re-run the session for that figure).
3. `--json` on `session`, `peaks` and `show`, and the written schema (roadmap 1b).
4. `irspec preview` (roadmap 1c): stdlib only, the width from `shutil.get_terminal_size()`.

Items 2a/2b (the trace macro, the Lua reader) touch the private `nulabreport`, which a cloud
session cannot reach: do those locally.
