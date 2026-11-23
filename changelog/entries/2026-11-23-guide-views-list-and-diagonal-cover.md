### The user guide: the Views list, the Diagonal cover view, and diagonal cover only where marked

The guide gone over against the editor of branch diagonal-marks (the rail's Views list, diagonal cover marks built,
the Diagonal cover view, marks that follow their pieces) and of main since its last update (Map settings' Long War
Rebalance section). In [guide.html](../../tools/release/guide/guide.html):

- **The tool strip** has its eleven buttons (item 6 the Views button; Snap is item 9), and a new section, **the
  Views list** (`#views`), with a picture of the list kept open and a row for each view and Map grid in its legend,
  in place of the old view buttons; "The Normal view's switches" says where they stand now. Every "hover the Normal
  view button", "in the flyout", "on the left rail" or "its button in the tool strip" says the list's row instead (the
  task of taking a building, the grid and clear-map tasks, Lights, Effects, Buildings, Map grid, Landing zones,
  Spawns, prefabs), and the pictures whose first mark was a view's button now mark the Views button showing the
  view's icon.
- **View options** has fifteen items: Area lights and Outline the pieces a light reaches moved to the Lights view's
  row (the Lights section says them), and Diagonal cover is item 11 (`#diagonal-cover`), the marks drawn in the
  normal view. Its old paragraph, which said the Build works diagonal cover out and gives a copied or moved slanted
  wall the corners it finds, is gone: the Build no longer finds diagonal cover by itself (KB-20).
- **A Diagonal cover section** (`#diagonal`, in the contents): what a mark is and that the Build gives diagonal cover
  only where one is; the view with a numbered picture (the Views button, the picked mark, its gizmo moving by whole
  tiles whatever Snap says, its corner dots, a mark of the map, one of the project, the panel's kind, tile, corners,
  Delete and Reset), [ and ], Deleted marks, what the last build gave a mark, a corner with no wall, box select;
  **a new mark** (`#diagonal-add`) from the Add panel with its picture; **marks that follow their pieces**
  (`#diagonal-follow`); a 0.7.0 project's slanted pieces build without diagonal cover until marked. A typical task
  (`#task-diagonal`), the keys table's Shift+C, [ ] and Del rows, a row in the kinds of pieces, the Snap list, the
  Add panel's kinds, Reset all, the limits and the in-game limits say it too.
- **Map settings** has a bullet for its Long War Rebalance section (Largest abduction, Keep Hold the Line off this
  map; carried by a map pack), and the Map menu's item 2 says it.

Pictures ([shots/](../../tools/release/guide/shots/)), taken on a test server with
[take_shots.py](../../tools/release/guide/take_shots.py):

- new: views-list, effects-switches and spawns-switches (the list with the Effects or the Spawns view on), in place
  of normal-flyout, effects-flyout and spawns-flyout, which are gone; diagonal and diagonal-add, on CSmallScout_Farm;
- retaken: rail, view-options, window (its tool strip), lights, landing-zones, effects, spawns, map-grid and
  buildings-draw (their first mark on the Views button), and clear-map, which lacked the window's "Keep the map's
  triggers and scripts" tick since it came in (its alt says both ticks now);
- kept: the rest, whose part of the editor did not change, though some show the old tool strip beside it (box-select,
  cover-blocks, buildings-view, the Add panel's pictures) or the Align section's Grid row missing above the flags
  (flags).

take_shots.py: `rail` marks the eleven buttons (the pointer off the Views button first); `views-list` (the list kept
open by a click, `open_views`/`close_views`), `effects-switches` and `spawns-switches` (`view_switches`: the list
with that view on) replace `normal-flyout`, `effects-flyout` and `spawns-flyout`; `view-options` numbers fifteen rows;
the lights, landing-zones, effects, spawns and buildings shots mark `#viewsButton`, and map-grid opens the list on its
Map grid row; a new last shot, `diagonal`, opens CSmallScout_Farm, takes the Add panel's new mark (`diagonal-add`),
puts it down, gives the hull corner's mark a second corner by a click on its dot and takes the view, then undoes it
all. Its corners are ones whose dots stand clear of the mark's gizmo: from that camera, a dot near the gizmo's
arrows takes no click.

Checked: `python tools/run_tests.py viewer -k guide` (6 tests) and `release` pass; `repo` passes but for one failure
in another session's uncommitted tools/viewer/tests/test_play.py (folders of one computer), none of these files. Every
new and retaken picture looked at; the page as published photographed at the tool strip, the Views list, View
options, the Diagonal cover section and its parts, Map settings, the new task and the two switches pictures
(`guide_tools.py look`). The full run on a fresh scratch folder stopped at mission-objects while the editor read
URB_SlaughterhouseA anew (its export was older than export 40; the run left the new one in the cache): that picture is
kept, and diagonal was taken on its own on the same server.

Known gaps: the last release's zip (0.7.0) still has the earlier guide, and the guide page isn't republished until
main is pushed. The diagonal picture has no "Last build" line in its panel: a project whose one change is its marks
fails to build (the copy tool's check for something to do leaves the marks out: "give --copy, --copies"), found while
taking it and reported, not fixed here. The help panel's words in index.html still name "the rail's ⇧Z button", "the
rail's pin", "the Normal button's flyout" and hovering the spark or the pin (not this guide's files).
