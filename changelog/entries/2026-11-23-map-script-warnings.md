### The map's script warnings say which piece and what happens; the Buildings view lists no changed map buildings

The user built the reported boat (a cleared EWI_ChryssalidHive) and the Build window showed fifteen identical "moved or
deleted, its mission script acts on the hidden original, not on the copy" rows under "A mission".

- **The window cut each row's piece away.** It dropped everything up to a row's first ": " (meant for a mission's
  name), which in these rows is the piece's name and the Kismet list. A row now drops its mission's name only where it
  starts with it; rows of no mission stand under "The map's own script (Kismet)", and the head says so when there is no
  mission ([build_window.js](../../tools/viewer/web/build_window.js) `missionWarnings`, `SCRIPT_LABEL`;
  [build_play.js](../../tools/viewer/web/build_play.js)).
- **What each one is** ([compiler.py](../../tools/editor/compiler.py) `kismet_named`, F-63): a moved piece the map's
  Kismet names is still a warning (the script acts on the hidden original, not on the copy at its new place); a
  deleted one the script waits on (an event's or a condition's) is a warning; a deleted one the project copied from
  the original is a warning naming the copies, which the script misses; a deleted one the script only acts on is a note
  (the piece is gone and what the script does to it shows nowhere; a cleared map deletes many). On the boat the hive's
  Kismet destroys fourteen of its props and swaps their materials when its chryssalids burst out (remote events fired
  from outside the level, which a cleared map does not stream): seven deleted ones became notes, the seven copied onto
  the boat are warnings with their copies' names, and the kept alien spawn point is the eighth.
- **The Buildings view's list of the map's changed and deleted buildings is gone**, at the user's word: a cleared map
  listed every deleted building with a Restore button ([buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js),
  [index.html](../../tools/viewer/web/index.html)). A changed building's box still has Restore the map's; a deleted one
  comes back with Ctrl+Z or Reset all. The guide says so ([guide.html](../../tools/release/guide/guide.html)).

Checked: [test_compiler.py](../../tools/editor/tests/test_compiler.py) (moved, deleted, deleted and copied, waited on,
copied alone), [build_window_test.mjs](../../tools/viewer/tests/build_window_test.mjs) (a mission's name dropped, a
script row whole, the head with no mission); the browser checks `map-buildings` (no list; restored by its function),
`floor-boxes`, `cursor-floors`; by hand on a test server: the reported boat's Buildings view shows no list, and its
unbaked build's window lists the eight rows by name. Editor and node suites, the guide's test.
