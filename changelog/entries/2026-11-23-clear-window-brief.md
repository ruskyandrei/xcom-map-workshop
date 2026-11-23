### The Clear map window gives a short count, and its buttons stay in view

A user clearing a site recon map at 150% zoom found the Clear map window's text running over its buttons: its last
paragraph listed every piece the mission's script named, with each script action. The user: "Can we just cut back on
that text (by a lot)? Make it just give a very brief count of removed pieces, no need for a detailed breakdown."

- **The window says four short things** ([clear_map.js](../../tools/viewer/web/clear_map.js) `clearWords`,
  [index.html](../../tools/viewer/web/index.html)): the warning (everything goes but one landing zone and the sun,
  moon and sky light; Ctrl+Z brings it back), one count line ("Removes 1311 pieces, 123 lights, 7 spawn points and 83
  effects."), that it then asks what the cleared map is for, and the two ticks. What stays, the triggers, Long War's
  patch levels, the spawn point the script names, the missions it will offer and the grid note are no longer spelled
  out; the list of pieces the script names is gone (the Build takes them out of the script now: kismet_cut.py). The
  count follows the scenery tick.
- **A window taller than the screen scrolls under its buttons** ([style.css](../../tools/viewer/web/style.css)):
  every dialog window scrolls when it does not fit, and a window's button bar (`buildoptionsfoot`: Clear map, Build,
  Map settings and the like) stays at its foot. At sizes that fit, nothing changes (every dialog measured at 1440 x 900).
- The [guide](../../tools/release/guide/guide.html)'s Clear map section says the window gives a short count.

Checked: the browser checks `clear-map` on URB_Bar and on EWI_ChryssalidHive (the one line and its counts, with and
without the scenery tick; the triggers tick; the buttons in view and clickable at the top and foot of the window
scrolled in a window 60% of its height), `modals` and `failed-reads`
([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py),
[browser_editing.py](../../tools/viewer/tests/browser_editing.py): the window's missions list is no longer read there;
the Missions panel's own check of an unknown game stays); the repo, node and viewer suites. Not done: the guide's
picture of the window (shots/clear-map.webp) still shows the longer text until the pictures are retaken.
