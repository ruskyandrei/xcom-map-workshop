### The drawn-only copy of pieces and the Add panel's recipes with the clipboard (clipboard.js)

Editor refactor, stage P9, third part (follow-up 3.15's `previewGroup`): two helpers app.js kept for the clipboard go to
it. Nothing the editor does changes.

- **[clipboard.js](../../tools/viewer/web/clipboard.js)**: `previewGroup` (a drawn-only copy of some pieces: the placing
  preview, the Add panel's thumbnails, the look picker's samples) and `pieceRecipes` (the Add panel's recipes of the
  lights, cover blocks, landing zones and spawn points), moved verbatim into `createClipboard`, before its placing.
  `previewGroup` stayed in app.js only because it falls back on the clipboard's ghost material, which the clipboard
  makes; inside the clipboard it reads that material directly, so the clipboard no longer gives the material back. The
  factory gives back `previewGroup` and `pieceRecipes`, and is given what they read (the scene's pieces' loads, material
  keys, `madeShape` and `unscaled`, the Effects view's `ghostLikeness`, and the four areas' entries, all made before
  it) instead of the two functions.
- **[app.js](../../tools/viewer/web/app.js)**: prefabs saved and placed, made before the clipboard, are given
  `previewGroup` as a function that calls it; the Add panel's browsers, made after, are given it as before. The imports
  only `previewGroup` used went with it (`makeEffectMarker`, `makeMarker`, `paintMarker`, `valuesOf`, `cloneSkeleton`,
  `geometryCache`). 1,555 lines to 1,514; top-level functions 46 to 44.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the clipboard's part in how the page fits, and the placement rule's example
  of a function app.js kept for a value made further down (`grabView` alone now).

Checked: [moved_code.py](../../tools/repo/moved_code.py): both functions the same as app.js's at the commit before,
app.js's other 44 and the clipboard's other functions the same (`createClipboard` differs by its arguments, its
returns and what moved into it); every name the moved code reads resolves as before (by eslint-scope; the ghost
material, which app.js took from the clipboard, is now the clipboard's own); `web_names` clean; the twenty-edit
recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`, `typed-pose`,
`copy-drag`, `adding`, `library`, `cover`, `floor-placing`, `lights`, `effects`, `likeness`, `flares`, `builder`,
`paste-buildings`, `look-undo`, `walls`, `made-prefab` and `looks` pass.
