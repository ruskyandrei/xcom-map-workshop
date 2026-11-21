### The user's groups and Align in modules of their own (groups.js, align.js)

Editor refactor, stage P8, third part: the groups' editing and Align leave app.js, in two modules, since they share no
state (Align only names a group and keeps what moves as one together). Nothing the editor does changes.

- **[groups.js](../../tools/viewer/web/groups.js)** is new. `createGroups` is made once by app.js, with what it needs
  of app.js in one argument object: the gizmo, the groups' basics (a group's chain and leaves, a piece's member key
  and record, the groups cloned), what can be grouped, the selection's highlight and the group chip, the selection
  and the hints. It holds, moved verbatim, the run of app.js that was the groups': a group's pieces on the map now
  (`liveMembers`, `liveKeys`, `ownKeys`, `liveGroup`) and those that can break together (`breakableCount`,
  `breakBlockCount`, `breakWallCount`); what the selection is to the groups (`selectionUnits`, `selectionGroup`) and
  the piece panel's group section with the chip (`groupPanel`); the groups changed, each change one undo step
  (`changeGroups`): Lock as group (`lockAsGroup`), Add to group (`groupToAddTo`, `addToGroup`), Ungroup (`ungroup`) and
  the keys' Ctrl+G and Ctrl+Shift+G (`groupShortcut`). It keeps no state of its own (the groups, their index and their
  pieces now are editor_state.js's) and gives app.js back the ten functions the selection, the edit hub, the keys,
  Align, the scene to and from a document, prefabs saved and placed, the made pieces' looks, drawing and panel, and
  the test hooks call.
- **[align.js](../../tools/viewer/web/align.js)** is new. `createAlign` is made once by app.js, with the gizmo, the
  scene, the pieces that can be copied, a piece's member key and its group, the recipe snap's move (`keepRecipe`) and
  the hints. It holds, moved verbatim, the run of app.js that was Align: the choices remembered in the browser
  (`alignPrefs`, `saveAlignPrefs`), the units moved and their names (`alignUnits`, `unitBox`, `unitName`, `unitLabel`),
  the piece panel's Align section with the white box on the target (`alignPanel`, `targetHelper`) and the move
  (`align`). Its own state is the white box; it gives back the four the edit hub and the panel's handlers use.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns the target chosen in the Align section
  (`alignTarget`, `setAlignTarget`), which app.js's handler of the target list sets. The comment of the groups' pieces
  now (`liveCache`) names the module.
- **[app.js](../../tools/viewer/web/app.js)** makes each module where its run was, the groups' and then Align's: what
  their runs did as the page loaded (the Break together row's title read, the white box added to the scene) happens
  where it did, so three.js draws the box in the same order as before. Each assignment to the target is its setter's
  call, with the same value (2 writes). app.js: 5,097 lines to 4,853; its `let` statements 35 to 34 (49 names to 48);
  its top-level functions 286 to 262. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the two modules, their rows in
  where new code goes and the state added to editor_state.js.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 16 functions moved into
  groups.js are the same, and the 8 moved into align.js are the same with the 2 substitutions of a write by its
  setter's call (without them, `alignPanel` differs). app.js against itself, with them: its 262 functions are the
  same, and the 24 moved are only in the old file. The whole moved text of each module (183 and 73 lines) is the old
  text line for line, the factory's indent aside, with those substitutions and the `let` statement whose name went to
  editor_state.js (now a comment naming it). No code that runs as the page loads, before any of the page's factories
  is made, reaches what they return.
- `web_names` is clean (71 files, in two halves), and the node suite passes (31 files).
- **Browser checks** on a test server: the same 26 as for the cover blocks, `groups` (Ctrl+G and Ctrl+Shift+G,
  nested groups, Add to group, Break together and the panel, a copied group pasted as a new one, each one undo step)
  and `align` (two axes by low edges, the other piece chosen as the target, a group lined up as one, undo) among them.
  All passed, none skipped.
