# EXP-74: made walls lit as the game's are, and one-storey walls (custom geometry plan, M2, run B)

Date: 18 November 2026. Status: **prepared**. The custom geometry plan's stage M2 (branch `fracturing-wall-poc`): a
made wall's lightmap is a rectangle of its own size at the donor's density, it has a shadow map of the dominant light
of its own, a Build without baking gives it one even light, and a wall can be one storey. Played unattended in the lab
copy (the hidden game, the game-test skill): only what is new since EXP-73; the look is for the user's eye too.

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

Not played yet.
