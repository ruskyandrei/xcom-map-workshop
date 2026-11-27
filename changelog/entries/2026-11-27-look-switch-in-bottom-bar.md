### The Game and Neutral look switch moves to the bottom bar

The look switch (Game, Neutral) stood at the top of View options. It is now a group of the bottom bar, after Frame and
before Scene and Floors, in the bar's own style, shown on every map. K still switches it. View options keeps the look's
settings under its Look heading: the line of the project's last baked Build, Area lights and Brightness.

- Where: [index.html](../../tools/viewer/web/index.html) (`#lookGroup` in the dock; the switch keeps its id `lighting`,
  so every script that reads it is unchanged), [style.css](../../tools/viewer/web/style.css) (a comment),
  [guide.html](../../tools/release/guide/guide.html) (the bottom bar's legend gains Look as item 2, View options' legend
  numbers 1 to 16, the Game look's text points to the bar), [take_shots.py](../../tools/release/guide/take_shots.py)
  (the dock shot marks the switch, View options' rows renumbered), the guide's pictures `dock` and `view-options` taken
  again.
- Checked: in a test server's page the switch sits in the bar, a click and K switch the look; browser_smoke.py's
  map-lights, lights, time-of-day, map-settings and likeness checks pass on URB_Bar of export 49; the node, repo and
  guide tests pass; both pictures looked at against their legends.
- Known gaps: none known.
