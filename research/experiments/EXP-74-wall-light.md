# EXP-74: made walls lit as the game's are, and one-storey walls (custom geometry plan, M2, run B)

Date: 18 November 2026. Status: **run B passed**: the moon's shadow seen offline only, and pieces left floating
after a break (F-127, for run C). The custom geometry plan's stage M2 (branch `fracturing-wall-poc`): a
made wall's lightmap is a rectangle of its own size at the donor's density, it has a shadow map of the dominant light
of its own, a Build without baking gives it one even light, and a wall can be one storey. Played unattended in the lab
copy (the hidden game, the game-test skill): only what is new since EXP-73; the look is for a human eye too.

## What is new

- A long made wall lit at the donor's sharpness: offline, in a baked Build on URB_Bar, a 2-, 6- and 16-tile wall have
  0.193, 0.196 and 0.196 texels a unit on their faces, the donor 0.196 (each its own rectangle; the 16-tile wall's
  300 x 260 texels). Not yet seen: seams between the charts, the light's look on a long wall.
- The moon's shadow on a made wall: its own shadow map, filled by the relight (before, the donor's inside-wall setting
  left the moon off a made wall altogether).
- One-storey walls (208 tall, the donor's cornice at 192), alone and one standing on another.
- A Build without baking: each wall one even light (a texel of the nearest lit piece's lightmap) and that piece's
  shadow map at the same texel.

## The projects

`EXP-74 wall light` (baked) and `EXP-74 wall light quick` (no bake), the same walls
([exp74_project.py](../../tools/editor/examples/exp74_project.py)), in a test server's scratch store; the maps
`EXP74WallLight` and `EXP74WallLightQuick`. Copies of URB_Bar's inside wall (`XComDecoFracLevelActor_17`), as the wall
tool makes them. Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873
+ 96 j.

| Wall | Where | What |
| --- | --- | --- |
| W16 | pavement before the bar, along x, y -192, x -1728 to -192, floor 16 | sixteen tiles, two storeys, under the awning's lamps |
| R | pavement, y -192, x 0 to 576 | the reference: the donor's own mesh lit from nothing as the made walls are |
| W2 | parking lot, along x, y -672, x -1728 to -1536, floor 0 | two tiles, two storeys, in the moonlight |
| W1 | parking lot, y -672, x -1344 to -1056 | one storey, three tiles |
| W1a, W1b | parking lot, y -672, x -768 to -480; W1b 192 higher | a one-storey wall and another standing on it |

## Run B (hidden game)

Checks, each passed, failed or unclear:
1. **Load**: the battle starts on `EXP74WallLight`; no crash, no mesh or texture error in `Launch.log`.
2. **Sharpness and seams** (W16 against R): shots of W16's south face along its length and of R beside it, close
   enough to see the lightmap: W16 as sharp as R, no dark or bright lines along chart seams, no blotches.
3. **The moon's shadow**: W2 and W1 in the lot: the lit side lit by the moon, the far side in shadow; the shadow edges
   of anything across them follow it (the car or the lamp posts).
4. **Lamps**: W16's south face under the awning's lamps lit in pools as the pavement is.
5. **One storey** (W1): drawn whole, the cornice at its top, nothing above it; a soldier beside it has high cover.
6. **A wall on a wall** (W1a, W1b): drawn as one wall two storeys tall with a cornice between; no gap or flicker where
   they meet.
7. **Break**: a grenade against W16 and one against W1b: holes, rubble, nothing left floating.
8. **Quick Build** (`EXP74WallLightQuick`): the same walls, each one even light near the pavement's or the lot's; none
   black or patterned with another shape's bake.

## Result

**Run B** (18 November 2026, the hidden game, an Opus agent by the game-test skill; out folders
`<lab>/hidden-runs/exp74-runB` and `exp74-runB-quick`: reports, shots, Launch.log). Read against the shots.

1. **Load: passed.** `LoadMap: EXP74WallLight`, the intro done; the five made walls appear in `Launch.log` only in the
   routine convex-cooking lines every fracturing piece has; no error names a made wall, its lightmap or shadow map.
2. **Sharpness and seams: passed.** Close shots of W16's lot face along its length and of R: the same blue moonlight,
   smooth gradients, the tile texture crisp; no seam line, blotch or black part. The lot side has no hard light pool
   to compare sharpness by (its one lamp is a street lamp at W16's west end).
3. **The moon's shadow: not seen in the game; offline the shadow maps are right.** In the game every face of W2 and
   W1 is about as dim as the lot's ground, in the textured view and with lighting only (`viewmode lightingonly`),
   and nothing casts a shadow across them; the ground shows the walls' shadows on their north side. The map's moon on
   the lot is too weak to tell the sides apart by eye. Offline, each made wall's shadow map in the baked map has a lit
   part and a shadowed one (of each rectangle 22 to 34% at full light, 45 to 57% in full shadow, the rest edges: the
   moonlit face, the far face and the faces inside the wall), so the relight wrote them and the game has them.
4. **Lamps: passed** for the one lamp there is: at the street lamp on W16's west end the wall and the pavement
   brighten together; the bar face warm and even, as R's. The plan's "awning lamps" are not on that stretch.
5. **One storey (W1): passed.** Drawn whole, its cornice at the top, nothing above it; a soldier at (-1201, -721)
   reads cover 50 (high) toward the wall, flags 1.
6. **A wall on a wall (W1a, W1b): passed.** One two-storey wall with W1a's cornice between the storeys, the ends in
   line, no gap or flicker from either side.
7. **Break: holes and fire, no crash; pieces left floating (F-127).** A grenade by W16 took its lower storey out over
   about four tiles with fire on the wall; its upper storey spans the hole with nothing under it. A grenade by W1a
   took W1a out along its whole length, and W1b stayed 192 over the ground, a van's wheel seen under it. No rubble
   chunks were seen; no error after the blasts.
8. **Quick Build: passed for the made walls.** `EXP74WallLightQuick` loaded; W16, W2, W1, W1a and W1b each one even
   light on both faces, none black or patterned (W2 paler than its neighbours, its light from another piece). R, the
   donor's own mesh (the `relit` reference, which only a baked Build relights), shows the donor's bake of the bar's
   windows in the quick build, as any copy of a game piece keeps its home bake.

M2 is done: made walls are lit as the game's pieces are at any length, and walls can be one storey. What was left
floating goes to M3 (F-127): since 033a5d7 (M3 item 3) W1a's and W1b's columns list each other, so a blast on one
passes on to the other; run C looks at that, and at one of the game's own two-storey walls broken the same way.
