# EXP-78: the farm's earth mounds replaced, and a hole half covered (custom geometry plan, M6, run F part 2)

Date: 18 November 2026. Status: **prepared**. The second part of the custom geometry plan's run F (branch
`fracturing-wall-poc`). EXP-77 is the first: ground shapes made from numbers on URB_Bar. This one takes a piece of
the game's own ground out and puts made ones in its place. Played unattended in the lab copy (the hidden game, the
game-test skill), checking only what is new.

## What is new

- One of the game's own walkable pieces deleted. `XComLevelActor_28` (TornEarth.Meshes.SmallscoutRamps, ten collision
  hulls) is the earth the crash threw up round the farm's UFO. Its tiles must lose its floors: nothing of the old
  mounds' floor may be left.
- A made block and ramp standing in part of its place, from the crater floor up to the field.
- A ground plane deleted, leaving a hole whose east half a made patch covers. F-46: the tile rebuild gives a hole's
  tiles a floor at the level's bottom, which here is the crater floor's height. The 3D cursor needs real geometry.

## The project

`EXP-78 farm ground` ([exp78_project.py](../../tools/editor/examples/exp78_project.py)) is in a test server's scratch
store. Its map, `EXP78FarmGround`, is built with the lighting baked, on `CsmallScout_Farm`. The crater round the UFO
and the ground east of x 480 are at -128, and the field west of x 480 is at 0. Game tiles count from the map's corner
(-2497, -3553, -129), so tile centres are at x -2449 + 96 i, y -3505 + 96 j.

Before the edit (the export's baked floors):
- the mounds' west strip, x 480 to 960, y -2880 to -2400: floors at -67, -3 and about 3;
- the mound south of the UFO, x 1340 to 2510, y -3280 to -2880: floors at -67, -3, 61 and up to about 103. At
  (1871, -3025), for one, they are -67, -3, 61 and 90.

| Piece | Where | What |
| --- | --- | --- |
| `XComLevelActor_28` | the crash site's mounds | deleted |
| Mound | x 480 to 864, y -2880 to -2496, on the crater floor (-128) | a block in Dirt (a copy of URB_MilitaryAmmo's `StaticMeshActor_67`), 128 high: its top at 0, level with the field west of it |
| Ramp | x 864 to 1152, y -2784 to -2592, on the crater floor | a ramp in Dirt rising west from -128 to the block's top at 0 (about 24 degrees, so its tiles are sloped, with no cover on them) |
| `XComLevelActor_145` | x 1439 to 2399, y -480 to 480, at -128 | the ground plane there deleted (nothing else gives its tiles a floor) |
| Patch | x 1920 to 2400, y -480 to 480 | in Grass (a copy of URB_CommercialStreet's `XComLevelActor_129`), its top at -127: the hole's east half |

Tiles:
- the ramp's are x 911, 1007, 1103 by y -2737, -2641; the block's x 527, 623, 719, 815 by y -2833 to -2545;
- on the crater floor east of the ramp: (1199, -2737);
- on the field west of the block: (431, -2737);
- the patch's tiles are x 1967 to 2351 by y -433 to 431; the uncovered hole's x 1487 to 1871 by the same y.

## Run F part 2 (hidden game)

1. **Load**: the battle starts on `EXP78FarmGround`, with no crash and no error naming a ground shape. The Skyranger
   lands as on the farm (its records and landing zones are found under the farm's other spelling, `CSmallScout_Farm`).
2. **The look**:
   - the block and the ramp, in the dirt material, lit;
   - where the mounds were: what is drawn now (the ground under them, or a gap);
   - the patch's grass beside the hole, and what the hole shows.
3. **Up and down the made ramp**:
   - a soldier on the crater floor at (1199, -2737) walks to (815, -2737), up the ramp and onto the block's top
     (about 0);
   - he walks on to the field at (431, -2737), level;
   - he walks back down to (1199, -2641).
   - On a ramp tile, (1007, -2737): his cover (none expected: sloped tiles).
4. **Nothing left of the old mounds' floor**:
   - the cursor (ShowCursorLoc) aimed at (1871, -3025) and (527, -2449), and a soldier sent to each;
   - what height he stands at: the old floors (-67, -3, 61 to 103, about 3) must be gone; expected is the crater
     floor's height or the ground left under them;
   - a shot from low of the old south mound's place.
5. **The hole and the patch** (F-46):
   - a soldier walks onto the patch at (2159, -49): he stands at about -127 and the cursor lands on the patch;
   - the cursor aimed in the uncovered half at (1679, -49): does it land, and at what height?
   - a soldier sent to (1679, -49): does he walk there, and at what height?
   - a shot of him in the hole and of the patch's edge at x 1920.

## Result

Not played yet.
