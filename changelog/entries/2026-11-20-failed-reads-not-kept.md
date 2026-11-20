### A read that fails is said and asked for again, not kept as the answer; a game the editor can't tell is its own state

Review finding 31, the page's items. Several reads took a failure for an empty answer and kept it until a reload.

- **Look catalogues** ([looks.js](../../tools/viewer/web/looks.js)): a failed read was stored as an empty catalogue, so
  every wall made in a donor's look was drawn by the Bar's numbers, with nothing said. Now `loadLooks` keeps only a
  catalogue it read. A failure answers an empty one with `error`, and the next call asks again.
  - When the page starts ([app.js](../../tools/viewer/web/app.js)), a failure shows a banner with the reason and
    Try again.
  - The look picker and the eyedropper say why instead of opening empty.
- **Favourites** ([library.js](../../tools/viewer/web/library.js)): one failed read was kept, so every star and every
  "recently used" said the file could not be read until a reload. Now the next star or placed piece asks again, and
  the hint gives the reason.
- **A made piece's mesh** (`applyWall`): when the server failed the new mesh, the piece kept its new numbers but
  returned with nothing said. Now the drawing keeps the shape it had, under its old mesh key, and the hint says why.
  The numbers stay, and the Build makes them.
- **A rock's corner points** (`rockCornersOf`): one failure was cached as `{ failed: true }`, so the rock had no corner
  points until a reload. Now the hint says why once, and the corners are asked for again after four seconds.
- **Which game is set**: `lwrInstall()` was "anything but plain EW". A failed `landing-lines.json` read, or no game
  set, counted as Long War. Now an unknown game is a state of its own.
  - A failed read says why in a banner.
  - `lwrInstall()` is true only for Long War.
  - Clear map lists the bomb mission as "on Long War only".
  - The Missions panel leaves the council bomb tickable, with a note that the editor can't check the game. Only plain
    EW turns it off.
  - A project opens once the landing lines have been read, so its starting zones don't change under it.
- Checked:
  - [looks_test.mjs](../../tools/viewer/tests/looks_test.mjs) covers a failed read that isn't kept, its words, and a
    read catalogue that is kept.
  - The new browser check `failed-reads` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py), through
    `browser_smoke.py --only failed-reads`) runs on the Bar:
    - the slabs' catalogue fails once: the banner says so, and Try again reads it;
    - a rock's corners fail once: the hint says so, and the corners are asked for again and come;
    - the landing lines fail: the game is unknown, Clear map says "on Long War only", and the Missions panel's
      council bomb stays tickable with its note.
  - The node suite passes.
- Known gaps:
  - The applyWall and favourites failures are checked by reading only.
  - The server's two reads in this finding are not in this change: area lights at export and script defaults.
