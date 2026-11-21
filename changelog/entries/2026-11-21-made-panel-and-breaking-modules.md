### The made pieces' panel sections, rooms and openings, and Break and Repair in modules of their own (made_panel.js, made_breaking.js)

Editor refactor, stage P7, fourth part: the last of the made pieces' editing leaves app.js, in two modules, since
the piece panel's sections and Break share no state and Break works on the map's own pieces too. Nothing the editor
does changes.

- **[made_panel.js](../../tools/viewer/web/made_panel.js)** is new. `createMadePanel` is made once by app.js, with
  what it needs of app.js in one argument object: the made pieces' state, changes and handles, their looks and Break
  row, the groups and the selection's group, and the hints. It holds, moved verbatim, the six runs of app.js that were
  the piece panel's sections of a made piece:
  - the Wall section (`wallPanel`) with its openings and how each plays (`doorBoxes`, `openingWorldBox`, `boxesMeet`),
    Add gap (`addWallOpening`), Flip and Shuffle; Delete taking out the opening last touched (`deleteWallOpening`);
  - the Floor section (`slabPanel`) with its holes, Add hole and Shuffle; the Ground section (`groundPanel`) with
    Turn, Another rock and Reset points;
  - a room: the Room section of a drawn room picked whole (`roomOfSelection`, `roomPanel`, `madeLookName`), its walls'
    and roof's looks, and its walls a storey lower or taller (`storeyButtons`, `roomStoreys`).

  Its own state is the room shown. It gives app.js back the seven functions app.js, its keys, hooks and the made
  pieces' handles call, under the same names.
- **[made_breaking.js](../../tools/viewer/web/made_breaking.js)** is new. `createMadeBreaking` is made once by
  app.js, with the gizmo, the renderer and the scene, the picking, the made pieces' changes, the other tools it stops,
  the selection and the hints. It holds, moved verbatim, the run of app.js that was Break and Repair: the Break rows
  (`breakRow`) and their controls, the Break tool (`startBreak`, `stopBreak`, `blastAt`, `breakAt`, its marker and the
  pointer's listener), and the map's own fracturing pieces broken (`mapBreakable`, `changeBlasts`, `setBroken`) and
  drawn without their knocked-out fragments (`drawBroken`, `knockedOut`, `middlesOf`, `fragmentSpans`,
  `sectionParts`). Its own state is the blast's size (read from the browser's storage as the module is made, where the
  page read it), its marker and the fragments' middles by mesh. It gives back the six functions app.js, the panel's
  sections, the scene to and from a document and the keys call. Known bug KB-1 (a cover block grouped with a made wall
  keeps its cover when the wall is destroyed) is in what the Build makes of a blast, not here; the code moved as it is.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns whether Break is on (`breaking`, `setBreaking`),
  which app.js's keys and pointer handlers read. The opening last touched (`wallFocus`) is there since the handles'
  part.
- **[app.js](../../tools/viewer/web/app.js)** makes the panel's module where its first run was (the Wall section's)
  and Break's where its run was, just after: what the panel's later runs did as the page loaded (their buttons'
  handlers) now happens there, before Break's rows get theirs; no other code sets a handler on those buttons, and
  neither module makes anything three.js draws as the page loads but Break's marker, made where it was. The made
  pieces' handles, made before them, are given `wallPanel`, `slabPanel` and `groundPanel`, the panel `breakRow`, and
  the scene to and from a document `drawBroken` and `mapBreakable`, as functions that call them. Each assignment to a
  moved name is now its setter's call (2 writes). app.js: 6,202 lines to 5,757; its `let` statements 41 to 38 (57 names
  to 54); its top-level functions 369 to 343. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the two modules, their
  rows in where new code goes and the state added to editor_state.js, and how an area that is several modules is
  made. A comment of [browser_editing.py](../../tools/viewer/tests/browser_editing.py) that placed `mapBreakable` in
  app.js names the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 13 functions moved into
  made_panel.js are the same, and the 13 moved into made_breaking.js are the same with the 2 substitutions of a write
  by its setter's call (without them, 2 differ). app.js against itself, with them: its 343 functions are the same, and
  the 26 moved are only in the old file. The whole moved text of each module (259 and 199 lines) is the old text line
  for line, the factory's indent aside, with those substitutions and the `let` statement whose name went to
  editor_state.js (now a comment naming it). No code that runs as the page loads, before any of the page's view and
  made pieces' modules is made, reaches what it returns.
- `web_names` is clean (66 files), and the node suite passes (31 files).
- **Browser checks** on a test server, the same 20 as on the stage's first commit: on the Bar `api-names` (240 names on
  each of its three pages), `typed-pose`, `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `library`,
  `cover`, `floor-placing`, `made-prefab`, `modals`, `reset-all` (a map piece broken and mended), `draw-errors`,
  `look-undo`, `failed-reads`, `let-go` (the Break row's blast size) and `small-defects`; on the police station `walls`
  (the Wall, Floor and Ground sections' buttons) and `looks`. All passed, none skipped.
- No browser check walks Break on a made piece, Delete taking out an opening or a hole, or a rock's corner picked: a
  scratch script on the Bar walked them on the commit the stage started from and on this one, with the same results
  (a blast set off on a made wall by B and a click, and Repair mending it; an opening and a hole taken out by Delete
  once their rows were hovered, Ctrl+Z bringing the opening back; a rock's corner clicked taking the point gizmo, and
  Escape letting it go), and no page error. The Room section's buttons are walked by none.

The stage's end (its four parts together), checked after this entry's first commit:
- **The whole stage against the commit it started from:** the 97 functions moved into the five modules (16, 14, 41, 13
  and 13) are the old ones with the 19 substitutions of a write by its setter's call, and app.js's 343 functions are
  the same. The five modules' import statements, and one line of app.js's call of the drawing's module, are wrapped
  again to the repository's width (the move's wrapping left the closing words out of the count), nothing else:
  app.js is 5,758 lines.
- **`browser_smoke.py --all`** on fresh test servers, with a scratch cache and `--play-install <scratch game>`: the nine
  runs of the editor's checks pass, 70 checks ran and 6 skipped, each for its map or its run (TempleShip's two, the
  police station's light bar and Play run elsewhere; `streams`' edit and the patch previews have nothing on the Bar's
  export to work on), 14 min 33 s with other work on the computer. The Play run was refused before it played: the
  server's play status said "XCOM is running", since the game was open on the computer. Nothing of Play moved in this
  stage. Then, on the stage's last tree, the 20 checks above and the scratch script again: all as before.
