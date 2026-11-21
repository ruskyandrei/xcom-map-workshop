### The made pieces' looks and the look picker's wiring in a module of their own (made_looks_wiring.js)

Editor refactor, stage P7, first part: the made pieces' looks leave app.js for one module. Nothing the editor does
changes.

- **[made_looks_wiring.js](../../tools/viewer/web/made_looks_wiring.js)** is new. `createMadeLooksWiring` is made
  once by app.js, with what it needs of app.js in one argument object (as the views' modules are): the gizmo, the
  renderer, the made pieces' tests, state and donor template, the drawing tools, the paste, the groups' changes, and
  the meshes' and materials' loading for a sample. It holds, moved verbatim, the three runs of app.js that were the
  looks':
  - the look each tool draws in, remembered in the browser (`storedLook`, `rememberLook`), and the looks the
    project's made pieces are in (`usedLookKeys`, `madeLookKey`);
  - the look picker's samples (`sampleRequest`, `prepareSample`), the picker opened and a look chosen
    (`openLookPicker`, `closeLookPicker`, `lookChosen`);
  - the eyedropper (`startLookPick`, `stopLookPick`, `pieceLook`, `lookPickAt`);
  - a made piece made again in another look with the pieces the change takes, in one undo step (`lookTargets`,
    `setMadeLook`);
  - the piece panel's Look row (`lookRow`) and its Choose… and Plain buttons.

  It has no state of its own. It gives app.js back the nine functions app.js, its hooks, the look picker and the made
  pieces' panels call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what other areas read or set of it, each with
  its setter: the look picker (`lookPicker`, `setLookPicker`: app.js still makes it with the Add panel's piece
  browser, since it paints) and the eyedropper (`lookPicking`, `setLookPicking`).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the first run was. What the third run did as the
  page loaded (the Look row's six buttons' handlers) now happens there, earlier: no other code sets a handler on those
  buttons, and the run makes nothing three.js draws. `wallState`, which app.js makes further down, is given as a
  function that calls it. Each assignment to a moved name is now its setter's call, with the same value (3 writes).
  app.js: 7,219 lines to 6,982; its `let` statements 50 to 48 (70 names to 68); its top-level functions 440 to 424.
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in where new code goes and the state it added to
  editor_state.js.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 16 moved functions are
  the same with the 3 substitutions of a write by its setter's call (without them, 2 differ). app.js against itself:
  its 424 functions are the same, and the 16 moved are only in the old file. The whole moved text, statements as well
  as functions (248 lines), is the old text line for line, the factory's indent aside, with those substitutions and
  the two `let` statements whose names went to editor_state.js (now comments naming them). No code that runs as the
  page loads, before any of the page's view and made pieces' modules is made, reaches what it returns (a scan of
  app.js's top level).
- `web_names` is clean (62 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the stage's first commit and on this change, the same 20 checks: on the Bar
  `api-names` (240 names on each of its three pages), `typed-pose`, `recipe`, `destruction`, `adding`, `groups`,
  `copy-drag`, `library`, `cover`, `floor-placing`, `made-prefab`, `modals`, `reset-all`, `draw-errors`, `look-undo`,
  `failed-reads`, `let-go` and `small-defects`; on the police station `walls` and `looks`. All passed, none skipped.
