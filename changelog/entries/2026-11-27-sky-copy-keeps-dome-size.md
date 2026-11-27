### The editor draws the chosen sky in the size of the dome it replaces

With a sky chosen in the Map settings window, the Game look drew each copy of the chosen dome in that dome's own size.
On URB_Bar the small dome turned over under the map became a full-size one, which the view (it draws the sky at the far
plane, with no fog) showed as a second sky under the map: a mirrored sun below it, and from some cameras a near-black
background. The view now draws each copy with the replaced dome's own matrix, its place, turn and size (both are the
game's one sky dome mesh), so the bowl under the map stays as the map has it. The Build's copies keep the chosen dome's
size: in the game all below the horizon is the fog's colour, so nothing of it shows (EXP-100; F-202 accepted).

- Where: [sun_wiring.js](../../tools/viewer/web/sun_wiring.js) (`placeDome`),
  [findings-register.md](../../research/findings-register.md) (F-202).
- Checked: on URB_Bar of export 45 at 13:00 with the noon sky in a test server's page: the two copies drawn in the
  noon material, the small bowl under the map and no second sky; browser_smoke.py's `sky-choice`, `time-of-day` and
  `map-settings` pass.
- Known gaps: none known.
