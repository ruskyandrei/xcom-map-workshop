# EXP-77: ground shapes made from numbers (custom geometry plan, M6, run F)

Date: 18 November 2026. Status: **played** (run F, 18 November 2026: passed; the shapes' own shadows unclear at the bar's night light). The custom geometry plan's stage M6 (branch `fracturing-wall-poc`):
patches, blocks and ramps made from numbers as plain static meshes. Each is a copy of one of the game's ground pieces
(its material, its lightmap and shadow map of its own), with its collision a box or a ramp's wedge written as the
game's cooker writes hulls (tools/bake/hulls.py). Played unattended in the lab copy (the hidden game, the game-test
skill), checking only what is new.

## What is new

- A plain mesh of our own, shown: drawn in a ground material of the game's (URB_Bar's asphalt plane, `Asphalt_VP`, a
  vertex-painted blend: the shape's vertices take the donor's commonest painted colour), lit by the bake, casting and
  taking shadows.
- A convex hull of our own that is not a box (the ramp's wedge): the tile rebuild's floors on it, units walking it.
- A block units stand on, reached by the ramp; a block's cover; a patch's floor a unit over the lot.
- A rock (M6 item 6): an irregular convex piece from a seed, its collision its own hull. It is drawn in Rock (a copy
  of CLrgScout_ForestTrench's `XComLevelActor_34`, Rock_E), standing in the way and giving cover by its height.

## The project

`EXP-77 ground` ([exp77_project.py](../../tools/editor/examples/exp77_project.py)) is in a test server's scratch store.
Its map, `EXP77Ground`, is built with the lighting baked. Every shape is in Asphalt, a copy of URB_Bar's
`XComLevelActor_131`. Game tiles count from the map's corner (-2785, -1921, -1), so tile centres are at
x -2737 + 96 i, y -1873 + 96 j.

| Shape | Where | What |
| --- | --- | --- |
| Ramp | lot (floor 0): x -1728 to -1440, y -960 to -864 | rising east to 96 at x -1440: about 18 degrees, so its tiles are sloped (no cover on them, F-81) |
| Block | lot: x -1440 to -1248, y -960 to -768 | 96 high; the ramp's high edge meets its west side |
| Patch | lot: x -1152 to -864, y -960 to -672 | its top 1 over the lot |
| Cover block | on the patch: x -1056 to -960, y -864 to -768 | 64 high (low cover, by the game's sweeps) |
| Out_asphalt | lot: x -1440 to -1344, y -1248 to -1152 | a block 64 high outdoors |
| In_asphalt | the bar's kitchen (floor 16): x -1536 to -1440, y 768 to 864 | a block 64 high indoors, listed in the bar's building by its own box |
| Rock | lot: x -768 to -576, y -960 to -864 | a rock in Rock, 128 high, seed 7 |
| Out_rock | lot: x -288 to -192, y -1248 to -1152 | a block in Rock, 64 high |

Tiles: the ramp's are (-1681, -913), (-1585, -913) and (-1489, -913); the block's top (-1393, -913), (-1297, -913),
(-1393, -817) and (-1297, -817). The tiles east and west of the cover block are (-913, -817) and (-1105, -817).

## Run F (hidden game)

1. **Load**: the battle starts on `EXP77Ground`, with no crash and no error naming a ground shape.
2. **Shown outdoors**: close shots of the ramp, the block and Out_asphalt from the default camera's angle and from low:
   - drawn in the lot's asphalt (not a default or checker material);
   - lit, and shadowed where the lot is;
   - their own shadows on the lot;
   - no flicker where the patch lies over the lot.
3. **Shown indoors**: In_asphalt in the bar's kitchen, lit by the bar's lights. With a soldier in the kitchen, the
   block stays with the ground floor, and the bar's upper floor cuts away as usual.
4. **Up the ramp onto the block**: a soldier from (-1777, -913) walks to the block's top (-1297, -817):
   - his path goes up the ramp;
   - he stands at about 96;
   - he walks back down to (-1777, -913).
   - On a ramp tile, (-1585, -913), read his height and cover (sloped: none expected).
5. **The block from its side**: from (-1201, -817), east of the block, goto (-1297, -817): does he climb, go round by
   the ramp, or find no path?
6. **The patch**: a soldier walks onto (-1009, -913) and stands at about 1.
7. **Cover by the cover block**: on (-913, -817) and on (-1105, -817), read `m_iCurrentCoverValue` and
   `CurrentCoverPointFlags`. Low cover toward the block is expected.
8. **Unbroken**: a grenade on the block's top or beside the ramp. The shapes stay, as does their collision: a soldier
   still walks the ramp after.
9. **The rock**:
   - close shots from the default camera and from low: drawn in the rock material, lit, with its own shadow;
   - a soldier sent onto its tiles, (-721, -913) and (-625, -913): he can't stand there, or he stands on its top
     (say which, and at what height);
   - cover on (-817, -913) west of it and (-529, -913) east of it: `m_iCurrentCoverValue` and
     `CurrentCoverPointFlags`;
   - a walk from (-817, -913) to (-529, -913): his path goes round it.

The farm's ramp replaced by one of ours, and a hole in the ground half covered by a patch (F-46), are
[EXP-78](EXP-78-farm-ground.md), run F's second part.

## Result

Run F, 18 November 2026, unattended (the hidden game; the shots stay in `<lab>\hidden-runs\exp77-runF`). Every check
passed. The shapes' own cast shadows couldn't be told from their dark faces at the bar's night light (unclear), and
EXP-78 looks again on the farm.

1. **Load: passed.** The battle started on `EXP77Ground` with no crash. The log names the shapes only in the engine's
   usual "Cooking Convex" notes, which it prints for the game's own pieces too.
2. **Shown outdoors: passed, but their own shadows were unclear.**
   - The ramp, the block and Out_asphalt are drawn in the lot's asphalt grain, their tops lighter than their sides,
     like the lot around them. Low shots show no flicker where the patch lies over the lot.
   - A second take from above showed a parked car's shadow plainly, but the shapes' cast shadows couldn't be told
     from their own dark faces at this light.
3. **Shown indoors: passed.** With a soldier in the bar's kitchen, the bar's roof cut away as usual. In_asphalt
   stands solid on the kitchen floor with its top lit. The other looks' indoor blocks stand beside it, as the project
   puts one of each look there.
4. **Up the ramp onto the block: passed.**
   - A soldier from (-1777, -913) walked five tiles to the block's top (-1297, -817) and stood at z 163, 96 over the
     lot's 67. The cursor read 160 there. He walked back down to (-1777, -913), z 67.
   - On the ramp tile (-1585, -913) a soldier stood at z 120 with no cover (cover value 0, flags 0, not in cover), as
     a sloped tile should be.
   - Others walked from the ramp onto the block, and from the block down the ramp to the lot.
5. **The block from its side: he climbs.** From (-1207, -817), east of the block, a goto onto (-1297, -817) moved
   him one tile: he climbed straight onto the 96-high block at z 163, with no detour by the ramp. Beside the block he
   had high cover (F-129).
6. **The patch: passed.** A soldier on (-1009, -914) stands at z 68.16, against 67.15 to 67.18 on the lot, and the
   cursor reads 65 there against the lot's 64.
7. **Cover by the cover block: passed.** Low cover toward the block on both sides:
   - east (-919, -817): cover 30, in cover, flags 0x84444 (cover toward -X, low, peeks, climb onto);
   - west (-1097, -817): cover 30, flags 0x108888 (toward +X, low).
8. **Unbroken by a grenade: passed.** An HE grenade landed on the lot beside the ramp's middle tile (four explosion
   damage lines, a tile rebuild of 95 tiles). The block and the ramp stand whole afterwards. A soldier then walked
   from the block's top down to the ramp's lowest tile (z 88) and back up to the top (z 163).
9. **The rock: passed, but its own shadow was unclear.**
   - It is drawn in a faceted brown and grey rock texture, lit, touching a parked car.
   - The cursor reads z 166 and 157 on its tiles.
   - A soldier can't stand on it: orders onto (-721, -913) and (-625, -913) ended on the lot beside it, at z 67.
   - High cover beside it: west (-817, -913) 50, flags 0x8808 (toward +X); east (-541, -914) 50, flags 0x2406
     (toward -X).
   - The path preview from east to west swings south round it, and both walks completed.
