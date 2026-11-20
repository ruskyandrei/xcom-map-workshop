### The move checks: substitution pairs from a file, and a write to an imported name

Two gaps the refactor's first page stage met in its checks, closed for the stages after it:
- [moved_code.py](../../tools/repo/moved_code.py) takes `--subst-file <json>`, a list of `[OLD, NEW]` pairs applied
  after the `--subst` ones. `--subst OLD=NEW` ends OLD at its first `=`, so it could not state a write moved to its
  owner's setter (`selected = hit` to `setSelected(hit)`), which every page stage needs.
- [web_names.py](../../tools/viewer/tests/web_names.py) turns on ESLint's `no-import-assign`
  ([web_names.config.mjs](../../tools/viewer/tests/web_names.config.mjs)): an assignment to an imported name (which
  throws only when its line runs) is reported, so a write left behind by a move to `editor_state.js` needs no grep.
- [ARCHITECTURE.md](../../ARCHITECTURE.md)'s list of the move tools says both.

Checked: the repo suite (a `--subst-file` pair holding `=` makes a changed function the same, a malformed file exits
2); `web_names` is clean on the page's 51 modules and reports a planted write to an imported `data` as
`no-import-assign`.
