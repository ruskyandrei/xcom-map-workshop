### The Map grid's panel stands beside the other right-hand panels too

KB-8's fault, fixed for the Selected piece panel (the grid panel stands to its left), happened with the other panels
on the right as well: with the rail's **Map grid** on, the Buildings view's panel, a picked landing zone's, a picked
spawn point's and a picked effect's opened at the grid panel's place. The Buildings view's covered the grid panel's
**Done**; the grid panel covered the other three. Found while fixing KB-8 (the follow-ups' stage P1); the follow-ups'
stage P3 fixes it.

- **[The stylesheet](../../tools/viewer/web/style.css)**: P1's rule moves the grid panel to the left while any of the
  five panels is shown (`#viewport:has(:is(#inspector, #volumePanel, #landingPanel, #spawnPanel, #effectPanel)
  :not([hidden])) #gridPanel`). Each of the five can show while the tool is on, one at a time; the rule for windows up
  to 800 pixels wide, where the Selected piece panel alone is narrower, is P1's and stays.
- **The `grid-panel` browser check** ([browser_editing.py](../../tools/viewer/tests/browser_editing.py), its line in
  [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) opens the grid with each of the five panels shown,
  shown before the tool is on and while it is on, at 1280, 1024 and 800 pixels wide: the grid panel and that panel
  stand apart and clear of the rail, a click at the middle of **Done** lands on it and puts the tool away, and what
  is picked stays picked. It failed before the change (the Buildings view's panel at 1280 wide: both at x 968) and
  passes now, three runs.

The fit: at 1024 wide the grid panel stands from x 400 to 700 beside a panel from 712; at 800 wide from 176 to 476
beside a 300-wide panel from 488, and from 226 beside the Selected piece panel's 250 from 538; the rail ends at 58.

Checked: browser checks `grid-panel` (three runs) and `clear-map` pass; the node suite and `web_names` clean.
