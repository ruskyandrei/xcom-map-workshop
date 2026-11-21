### The selection in a module of its own (selection.js), its panels through the edit hub

Editor refactor, stage P9, first part: `select`, which picks what is selected and fills the piece panel for it, leaves
app.js with the selected piece's marks, and where it called another area's panel by name it now runs one of the edit
hub's select runs, with which that area registers it. Nothing the editor does changes.

- **[selection.js](../../tools/viewer/web/selection.js)** is new. `createSelection` is made once by app.js, with what
  it needs of app.js in one argument object (the gizmo, the highlight and the ladder's marks, the group chip, the
  panel's helpers, the pieces' boxes, poses and recipes, what can be copied and how a selection is named, the views'
  switches, a light's glowing piece, the effect picked, a piece's listed floors, the buildings, the map's size, the
  missions' names and the landing's pieces, a piece of another map's words, the flags' contract and the Lights view's
  storage key). It holds, moved verbatim, `select`, a cover piece's panel (`showCover`), a ladder's ends and its chip
  (`ladderNow`, `floorPlan`, `refreshLadder`, `LADDER_NOTE`), the grid chip (`gridNow`, `refreshGrid`,
  `OFF_GRID_NOTE`) and the highlight (`refreshHighlight`), with their state inside it (the map's floor tiles as a set,
  the piece panel's ladder and grid chips), and registers the edit hub's `selection` and `marks` refreshes (moved from
  app.js). It gives back the five functions others call (`select`, `gridNow`, `ladderNow`, `refreshGrid`,
  `refreshHighlight`).
- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)** has six more runs, each a place where `select` fills the piece
  panel: `select-sections` (each area's section shown or hidden for what is picked: the light, cover, made pieces' and
  Break sections), `select-none` (the Effects view's markers, panel and shape when nothing, a building's box or an
  effect is picked), `select-light` (a light's panel), `select-cover` (a cover piece's section, from `showCover`),
  `select-piece` (a made piece's sections, the Break row) and `select-chips` (the flags chip). The statements `select`
  ran there are moved verbatim into the areas that own them, registered in today's order:
  [lights_wiring.js](../../tools/viewer/web/lights_wiring.js), [cover_wiring.js](../../tools/viewer/web/cover_wiring.js),
  [made_panel.js](../../tools/viewer/web/made_panel.js) (now given `isMadeGround`),
  [made_breaking.js](../../tools/viewer/web/made_breaking.js),
  [effects_wiring.js](../../tools/viewer/web/effects_wiring.js) and
  [flags_panel.js](../../tools/viewer/web/flags_panel.js); what they gave app.js only for `select` is no longer returned
  (`flagChip`, `showLight`, `paintEffects`, `effectPanel`).
- **[app.js](../../tools/viewer/web/app.js)** makes the selection after the Buildings view, the last factory whose
  functions it calls (it makes nothing as the page loads: the group chip, which the groups are given too, stays where
  app.js made it), and gives the eight factories made before it that take `select` (the scene's pieces, the Flags
  group, the groups, the Lights, Spawns, Effects, Landing zones and Buildings views) and the two that take `gridNow`
  (the prefab builder's session and prefabs saved and placed) functions that call them. Its imports used only by the
  moved code went with it. app.js: 2,783 lines to 2,516; its top-level functions 114 to 106; its `let` statements 13
  to 12 (20 names to 17).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the selection's row in where new code goes and its factory among the
  page's; the hub's select runs in the rule that a panel registers with the hub; where the selection is made and the
  group chip as an object both it and the groups are given; editor_state.js's comments and the document name the
  selection's module where they said app.js's.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the hub's commit: the 8 functions moved into
  selection.js are the old ones with the 6 substitutions of a statement run by one of the hub's select runs (without
  them, `select` and `showCover` differ); app.js against itself: its 106 functions are the same, and the 8 moved are
  only in the old file; in the six areas' modules every function but the factory is the same. Each of the six
  substitutions was checked token for token: the statements `select` (or `showCover`) ran there are the bodies of the
  refreshes registered in that run, in its order. The whole moved text (278 lines) is the old text line for line, the
  factory's indent and the substitutions aside, with one comment line added. No code that runs as the page loads,
  before a factory is made, reaches what it returns (a scan of app.js's top level for the selection and the 16
  factories around it).
- **The twenty-edit recording** (the 52 steps of the hub's entry, selections of every kind among them: a piece, a
  ladder, a fracturing piece, a light, an effect, a building's box, a cover block, a made wall, a group, nothing): the
  same as on the stage's start commit, every panel's markup and controls, the state and the panel functions called and
  their order, all 52 steps.
- **The edit's time**, as in the hub's entry (other work on the computer): on the Bar 1.1 to 1.2 ms a move, 1.7 ms an
  undo, 1.6 ms a redo and 1.4 ms a selection; on TempleShip 2.7 to 2.8 ms a move, 3.6 to 3.75 ms an undo, 3.3 to 3.4
  ms a redo and 2.3 to 2.4 ms a selection: as on the stage's start commit.
- `web_names` is clean (83 files); the node suite passes (32 files) and the repo suite.
- **Browser checks** on a test server: the hub's 27 (`typed-pose`, `groups`, `copy-drag`, `box-select`,
  `small-defects`, `align`, `cover`, `lights`, `effects`, `walls` and `looks`, which select, among them), and
  `prefabs`, `made-prefab`, `builder`, `draw-errors` and `failed-reads`. All 32 passed, the same part of `spawns`
  skipped as on the start commit (the police station has no plain pod or Meld point to copy).
