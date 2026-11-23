### The rail's views are one Views button with a list, each view's switches under its row

The rail had grown to 16 buttons (661 pixels, taller than the view of a 768-high window), and each view's switches
showed only while hovering its own button. The user chose design A of the mock designs with design C's switches
(private/plans/todo/diagonal-cover-by-hand-and-views-plan.md, section 7; stage V1):

- One **Views** button on the rail shows the icon of the view that is on (marked on for any view but the normal
  one). Its list, shown while the pointer is over the button or kept open by a click on it, has a row for each view
  with its key, and the Map grid after a line ([index.html](../../tools/viewer/web/index.html),
  [style.css](../../tools/viewer/web/style.css)). The rail has 11 buttons now (about 460 pixels).
- The switches of the view that is on stand indented under its row: the Normal view's four "also show and select",
  the Effects view's three kinds, the Spawns view's families and its drop-in rule, and the Lights view's Area lights
  and Outline the pieces a light reaches, which moved there from View options.
- [views.js](../../tools/viewer/web/views.js) holds `VIEWS`, the one table of the views: the list's on marks, the
  button's icon and tooltip and the views' keys (Shift+N, B, L, Z, X, U, as before) come from it, and
  [navigation.js](../../tools/viewer/web/navigation.js) asks it for a Shift key instead of a branch per view. A new
  view is a row of it and of the list. The rows keep the old buttons' ids.
- [UI-GUIDELINES.md](../../UI-GUIDELINES.md) (section 2) and [ARCHITECTURE.md](../../ARCHITECTURE.md) say the new
  place; the help panel's words follow.

Checked: in a browser on a test server (the list opens on hover, a row turns its view on, Shift+U turns the Spawns
view on and the button takes its icon); the browser checks floor-boxes, clear-map and grid-panel (the grid panel
apart from every view's panel and from the rail at 1280, 1024 and 800 wide), with their steps that used the old
buttons opening the list first ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py),
[browser_editing.py](../../tools/viewer/tests/browser_editing.py)); web_names.

Known gaps: the guide's pictures of the rail and of the views' flyouts (take_shots.py) are retaken at the next guide
update.
