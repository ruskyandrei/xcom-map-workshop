### The Flags group and Select all of a kind in modules of their own (flags_panel.js, select_kind.js)

Editor refactor, stage P8, second part: the piece panel's Flags group and Select all of a kind leave app.js, in two
modules, since Select all of a kind selects effects, sounds and lens flares as well as pieces and shares no state with
the flags. Nothing the editor does changes.

- **[flags_panel.js](../../tools/viewer/web/flags_panel.js)** is new. `createFlagsPanel` is made once by app.js, with
  what it needs of app.js in one argument object: the gizmo, the pieces' boxes and source keys, the tile grid's
  corner, the selection and the panel's helpers. It holds, moved verbatim, the run of app.js that was the Flags group:
  why a piece takes no flags (`flagBlock`), the actors the group edits (`flagTargets`, `flagKey`), what a piece's
  flags are planned on (`flagSource`, `flagContract`) and one actor's flags as the project has them (`flagView`); the
  Flags chip (`flagChip`) and the group's rows (`flagsPanel`); a row clicked (`flagClick`), the change made as one
  undo step (`applyFlags`, `commitFlags`, `flagsChanged`) after asking where a prop's pathing gate would change a
  half-on role (`askFlags`, `closeFlagAsk`), and Reset (`resetFlags`). Its own state is the question open. It gives
  app.js back the six functions the selection, the edit hub, the ladders' chip, the keys and Select all of a kind
  call. [piece_flags.js](../../tools/viewer/web/piece_flags.js), the flags' rules, is unchanged and imports nothing of
  the page.
- **[select_kind.js](../../tools/viewer/web/select_kind.js)** is new. `createSelectKind` is made once by app.js, with
  the gizmo, the pieces' boxes, the Effects view's switch and what of an effect can change, box select's slack
  (`PICK_SLACK`) and its stop, the flags' key of an actor, the selection and the hints. It holds, moved verbatim, the
  run of app.js that was Select all of a kind: what counts as a piece's or an effect's kind (`kindPiece`,
  `effectKind`, `kindMesh`, `kindSeeds`), what matches (`kindMatches`), the button and its words (`kindButton`,
  `kindCount`) and the selection made (`selectKind`). It keeps no state and gives back the two functions the edit hub,
  the keys and the Buildings view's box select call.
- **[app.js](../../tools/viewer/web/app.js)** makes the Flags group's module where its run was, and is given the
  pieces' source keys (`sourceKey`, made further down) as a function that calls it. Select all of a kind reads box
  select's `PICK_SLACK`, a constant the Buildings view's factory returns, so its module is made just after the
  Buildings view (its run made nothing as the page loaded, so nothing else happens later), and the Buildings view is
  given `kindButton` as a function that calls it. app.js: 5,389 lines to 5,097; its `let` statements 36 to 35 (50 names
  to 49); its top-level functions 311 to 286. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the two modules and
  their rows in where new code goes.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 17 functions moved into
  flags_panel.js and the 8 moved into select_kind.js are the same, with no substitution. app.js against itself: its
  286 functions are the same, and the 25 moved are only in the old file. The whole moved text of each module (212 and
  94 lines) is the old text line for line, the factory's indent aside. No code that runs as the page loads, before
  any of the page's factories is made, reaches what they return.
- `web_names` is clean (69 files, in two halves: all of them at once, by their paths in a worktree, made a command line
  longer than cmd.exe takes), and the node suite passes (31 files, the flags' `piece_flags_test.mjs` and
  `project_flags_test.mjs` among them).
- **Browser checks** on a test server: the same 26 as for the cover blocks (on the Bar `small-defects` and
  `ladder-floor`, whose Flags group row turns a floor off, among them; on the police station `walls` and `looks`),
  then `api-names`, `effects` and `flares` (Select all of a kind on effects and lens flares, in a box and not) and
  `lights`. All passed, none skipped.
- No browser check presses Select all on pieces: a scratch script on the Bar, on the stage's first commit and on this
  change, picked one of the six dumpsters, pressed Select all (six picked), turned Blocks sight off for them (six
  records, the chip and the count saying so), undid, redid and reset it, turned Blocks walking on for a dumpster and a
  keg, and Shift+clicked Select all with both picked (eleven): every panel's words, the picks and the project's flag
  records were the same, with no page error.
