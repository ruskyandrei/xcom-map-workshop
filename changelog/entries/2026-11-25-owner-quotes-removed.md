### Chat quotes and who-asked notes taken out of the tracked files

The notes quoted the words typed in chat and recorded who asked for, chose or confirmed each thing ("at the ... ask",
"on the ... word", "chose design A", dated attributions in code comments). Every tracked file now records only the
substance: what was decided or found, with its date where that helps; checks played by hand say so without naming
anyone. "The user" meaning the editor's user, and process rules such as asking before a push, are unchanged.

- Where: the month file [2026-11.md](../2026-11.md) and the entry
  [2026-11-25-release-0-7-2-published.md](2026-11-25-release-0-7-2-published.md);
  [findings-register.md](../../research/findings-register.md), the other `research/` notes and the EXP notes in
  `research/experiments/`; comments and docstrings in `tools/` and `unrealscript/`; the patch examples' notes
  ([exp07wing.json](../../tools/patch/examples/exp07wing.json), [exp08blank.json](../../tools/patch/examples/exp08blank.json));
  [UI-GUIDELINES.md](../../UI-GUIDELINES.md) and the release and update-guide skills.
- The release skill's "Release <version> published" entry no longer asks for the go-ahead in quotes.
- Checked: every remaining "user" line in the tracked files read; Python files parse, JavaScript files pass
  `node --check`, the patch examples load as JSON; the `repo` suite passes.
- Known gap: earlier commits and their messages still hold the old wording; changing them would mean rewriting
  the pushed history.
