### The edit hub checks that every run's refresh is registered

Editor refactor, stage P9, third part (stage P9's first part found it): a run of the edit hub passes over a name that
has no refresh registered without a word, so a registration lost in a move (an `onHub` call left out, or one inside a
branch that did not run) went unseen. Now it fails where it can be seen.

- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)**: `checkHub()` throws, naming every `run/name` of `RUNS` that
  has no refresh registered.
- **[app.js](../../tools/viewer/web/app.js)**: `startScene` ends with `checkHub()`, once every area's module is made
  and the test hooks are set: with a registration missing, the page's status says "Open failed", the loading line names
  the missing ones, and the error reaches the console, which the browser checks read. No hook is added
  (`window.viewer`'s 240 names unchanged).
- **[edit_hub_test.mjs](../../tools/viewer/tests/edit_hub_test.mjs)**: `checkHub` names the missing ones and passes
  once all are registered; and the page's modules, read as text, hold one `onHub('<run>', '<name>'` for each name of
  each run and none other (34), so a lost registration also fails the node suite, without a browser.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the hub's rule and its row say so.

Checked: the node suite; with `made_handles.js`'s `scene`/`joins` registration taken out of the page as served (a
scratch script of the stage), the Bar's page fails to open with "The edit hub has no refresh registered for
scene/joins" in its status line and console; with nothing taken out, the twenty-edit recording is the same as on the
stage's start commit (all 52 steps), and browser checks `api-names` (the Bar, the blank map and the builder),
`typed-pose`, `builder`, `draw-errors`, `failed-reads` and `walls` pass; `web_names` clean.
