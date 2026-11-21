### browser_smoke's fixed waits: each one that is not a camera wait replaced by a wait for what the check reads

Editor refactor, stage P10. Of [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s 42 fixed waits
(`wait_for_timeout` and `time.sleep`, on 40 lines), 20 went (no assertion dropped, no time-out made longer):

- **Waits for a state the check reads:** the floor-placing preview under the pointer before a click
  (`viewer.placing().ghost.visible`, as library-all already waited); the floor tile tip saying the piece's name, then
  "deleted since" (`#floorTip`, written by the draw loop); the Map lighting mode with the lights as edited
  (`viewer.lighting.counts`); the likeness drawn, switched off (none and no particles), back on, deleted and undone
  (`viewer.likenessState()`); output-names' held answer: the test's own slow fetch records the name asked for, and
  the check waits for the name typed to be asked before reading the dialog meanwhile.
- **Read at once where the page acts in the event's own listener**, which Playwright's mouse and key calls wait for
  (measured on the Bar: 150 of 150 moves, presses, releases, wheel turns and keys were seen by the page's listeners when
  the call returned): the Map grid's and a no-spawn volume's handle drags (the press takes the handle under its own
  point, the release sets the size), and the hunts for a gizmo's handle along a line (the gizmo takes its hovered axis
  in its pointermove listener; copy-drag's hunt always read it so).
- **A negative check made exact:** copy-drag's Escape during a Shift drag now waits for the release to be handled and
  checks that no paste began (`viewer.copySerial()`: a paste numbers its copies before anything it waits for), where
  a 200 ms grace looked for a copy turning up; library-effects' sound row checks that the hover took no tip into the
  likeness pane (what a row the pane is to show does at once), where 600 ms looked for the pane.

Kept, with why written beside each: the key holds (arrow-pan's and turn's 300 ms, the text field's 200 ms: how long a
key is held, then 100 ms for the last camera step); `settled`'s camera polls; frames drawn after the camera was put
somewhere before screen points are read (floor-placing's drag, the Spawns view's pod and volume handles, the zone
gizmo's ring after R) and before pictures (map-lights, floors-cut, previews, the run's screenshot, likeness's framed
effect); likeness's 1.5 s of likenesses drawn before the frame time it reports, and its picture polls; polls of a
server or page state at 250 ms (`wait_recovery`, `wait_opened`) and the server start and stop polls (Playwright's
`wait_for_function` does not wait for an async predicate's answer, so a poll that fetches stays a loop).

Checked on a test server: copy-drag, clear-map, library-effects, floor-placing, floor-tiles, lights, output-names,
likeness, spawns and header five times in a row with `--only`, all passing (60 to 66 s a run, 77 s at the base
without header; other agents' runs make the times noisy); `browser_smoke.py --all` twice with `--play-install`.
