### The Clear map window clears parts of the map

The user's design A of the clear-by-parts plan (24 November 2026: "A is good, but can we also include landing zones in
the clear options?"): the Map menu's Clear map… opens a window with a tick for each part of the map, so a clear can
take some parts and leave the rest, at any point.

- **Six parts, each a tick with a short count** ([index.html](../../tools/viewer/web/index.html),
  [clear_map.js](../../tools/viewer/web/clear_map.js) `partCounts`, `refreshClearRows`): Pieces and ground, Lights,
  Effects and sounds, Spawn points, Landing zones ("6 of 7, one kept"), Triggers and scripts (counted from the export).
  Each row's tooltip says what it takes and what stays. A part already cleared shows a Cleared chip and counts what
  stands since; a part with nothing to take is dimmed and says none (but the pieces, before they are cleared).
- **What it opens with**: every part ticked on a map with nothing cleared (the whole clear, the same two clicks as
  before); otherwise the parts not yet cleared. The button says **Clear map** with every part that can be taken
  ticked, **Clear 2 parts** otherwise, and is dimmed with none.
- **Notes, each shown only when true**: the landing zones, lights, or smoke, fire and sounds a pieces clear leaves
  standing; the light baked into pieces that stay when only the lights go; the pods a plain Enemy Within map keeps
  where the floor was; then that it asks what the cleared map is for (with the pieces only).
- **Keep the scenery outside the play area** applies to each part the clear takes. The tick *Keep the map's triggers
  and scripts* is gone: the Triggers and scripts part is unticked instead.
- The window is a framed list of ticks, a part of the stylesheet's own (`.ticklist`, `.tickval`:
  [style.css](../../tools/viewer/web/style.css)); [UI-GUIDELINES.md](../../UI-GUIDELINES.md) lists it.

Checked: the browser check `clear-map` ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) on a test
server: the six rows and their ticks, counts and the triggers' row; unticked parts' notes and the button's words; the
lights alone with its note and no question; none ticked; the window at 1280, 1024 and 800 wide; keeping the outside;
the lights alone, then the pieces over them, undone twice; the triggers, landing zones and spawn points each alone; the
whole clear and the rest of the check as before. By hand on the test server: the window on URB_Bar, a lights clear and
the window opened again (pictures in private/shots). The node and viewer suites.
