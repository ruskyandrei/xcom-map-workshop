### ARCHITECTURE.md read against the code and put into one voice

Editor refactor, stage G1, step 1. [ARCHITECTURE.md](../../ARCHITECTURE.md) was read whole against the code: every
module, function, constant, file and link it names was looked up where it says, and each row of "Where new code goes"
against the module it names. The parts the refactor's stages wrote in passing are now one text in the present tense,
with no stage names or placement history. 875 lines to 659; no rule or reason dropped. No code changes.

- **How the parts fit:** the page's paragraph (about 210 lines, one area after another) is now the page's shape: the
  pure and wiring modules of an area, the few shared homes (editor_state.js, the edit hub, the document session and
  state, piece_records.js, project.js, api.js, storage.js), and what app.js holds today (its imports, its world, the
  making of the modules, `open` and `startScene`, the event wiring, its few helpers, `toggleButton` and `$` among
  them). The areas themselves are section 2's rows, which take the details only section 1 had (the Buildings view's
  records, the cutaway's parts, the clipboard's drawn-only copies, Prepare's openings). The `Compiler` and
  `native_copy.build` are described as what joins their parts.
- **Where new code goes:** rows checked; the Map lighting mode (`lighting.js`, `light_grid.js`), the first run's dialog
  (`setup.js`) and the ladder ends (`ladders.js`) named; a new lane of the native edit also needs an input of
  `build_outputs.py` that holds it (its `record` fails otherwise).
- **The rules, the page:** state, factories, opening a scene, the edit hub, records and modules, each stated once. The
  shared state's long list of who reads what (stale where code had moved: the views' switches, the recipes and
  listings, the map families, the export's problem) gives way to editor_state.js's own groups, whose comments say it.
  The factories' placement notes become six rules and the order app.js makes them in, as one list. `startScene`'s
  parts are listed in the order it calls them (the old list was out of order). The setter rule names the area's own
  `set<Name>` (map_grid.js's `setStage`), not app.js's.
- **Sizes:** one line for each file and function over the guideline sizes today (`test_structure.py --sizes`), saying
  why it is as it is or which split waits; no ceilings and no exceptions in `structure.json`, as before.
- **Changing the structure:** `web_names` is run by hand (it needs node and npm; `run_tests.py` does not run it).

Checked: `python -B tools/run_tests.py repo` passes (42 tests: the structure test's sections and the public-repo checks
read the document); every relative link resolves (250); every backticked name was looked up in the code with
`git grep`. Known gaps: comments in the code that still name app.js for code that moved (editor_state.js among them)
are the code's, not this document's.
