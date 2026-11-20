### The page's help lists every view and key, and its stale comments are put right

Review finding 64, the page's part.

- **The help panel** ([index.html](../../tools/viewer/web/index.html)), checked against the key handler in
  [app.js](../../tools/viewer/web/app.js):
  - the six views (Shift+N, B, L, Z, U and X) under View, where it said "the three views" under Lights;
  - M (the map browser), and B as it is: the play area only with nothing breakable picked;
  - under Pieces, B (Break, on a picked wall, floor or roof that breaks) and I (the eyedropper while drawing), and
    Ctrl+Shift+Z beside Ctrl+Y;
  - Shift+Z with what a picked landing zone takes (G, R, `[ ]`, Ctrl+D, Delete, Esc), and Delete, Ctrl+D and `[ ]` on a
    picked pod, Meld point or drop-in point (the section is now "Landing zones, spawn points and objectives").
- **Stale comments:**
  - "nothing is saved or built" and "trial edits" in [gizmo.js](../../tools/viewer/web/gizmo.js)'s header and two of
    app.js's; "Lights never join a group" (an editable light joins one as a piece does);
  - the shortcut list above the key handler, now naming every key it takes;
  - a made piece's record saying the view draws its template's mesh (it draws the mesh made from its numbers).
- **Comments above the wrong code:** app.js's storage note (over `sectionText`) and `copyable`'s (glued to
  `snapButton`'s brace); [walls.js](../../tools/viewer/web/walls.js)'s docs of `storeysInLook` and `wallWords`;
  [pieces.js](../../tools/viewer/web/pieces.js)'s orphan "An assembly builds when all its parts do";
  [library.js](../../tools/viewer/web/library.js)'s browser doc (over `pictureKey`);
  [style.css](../../tools/viewer/web/style.css)'s prefab-progress note. (pieces.js's three icon comments went with the
  icons in finding 63.)
- **Plan headers** in [spawns_view.js](../../tools/viewer/web/spawns_view.js),
  [spawn_rules.js](../../tools/viewer/web/spawn_rules.js) and [look_picker.js](../../tools/viewer/web/look_picker.js)
  name `private/plans/done/`, where those plans are now.

Checked: the help's markup balances, and a picture of the open panel was looked at (each key reads on its line); the
browser smoke's `text-select`, `pan`, `modals` and `small-defects` on a scratch server; `node --check` on each module.
