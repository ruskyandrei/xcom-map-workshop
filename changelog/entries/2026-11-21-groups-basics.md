### The groups' basics with the groups (groups.js)

Editor refactor, stage P9, third part: what a group is and its basic helpers leave app.js for the groups' module.
Nothing the editor does changes.

- **[groups.js](../../tools/viewer/web/groups.js)**: at its top, before `createGroups`, the comment saying what a group
  is and the groups' basics, moved verbatim from app.js and exported: `parentGroup`, `groupChain` (a group and the
  groups it is in), `topLocked` (the outermost locked one: what the gizmo moves together), `leafKeys` (a group's
  pieces, those of the groups inside too), `memberRecord` and `memberOf` (a piece's member record and key),
  `cloneGroup` and `cloneGroups`. They read only the groups and their index (editor_state.js's), so they are plain
  exports: `createGroups` reads them there and is no longer given them, and app.js imports those it gives the gizmo,
  the clipboard, the scene to and from a document, Clear map, Delete and Reset, Align, prefabs and the looks.
  `keyWords` (a group's members in words, which reads the group's pieces now) moved verbatim into `createGroups`.
- **[app.js](../../tools/viewer/web/app.js)**: 1,815 lines to 1,774; top-level functions 81 to 72; two imports of
  project.js only the moved code used went with it. [editor_state.js](../../tools/viewer/web/editor_state.js): its
  pointer to what a group is names groups.js. [ARCHITECTURE.md](../../ARCHITECTURE.md): the groups' basics in how the
  page fits and in the groups' row.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the nine functions the same as app.js's at the commit before
(`export` aside), app.js's other 72 and groups.js's other functions the same (`createGroups` differs by its arguments
and the function moved into it); every name the moved code reads resolves as before (by eslint-scope); `web_names`
clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`,
`groups`, `copy-drag`, `align`, `typed-pose`, `builder`, `paste-buildings`, `reset-all`, `small-defects` and
`made-prefab` pass.
