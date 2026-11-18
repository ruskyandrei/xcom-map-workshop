# EXP-77: ground shapes made from numbers (custom geometry plan, M6, run F)

Date: 18 November 2026. Status: **prepared**. The custom geometry plan's stage M6 (branch `fracturing-wall-poc`):
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

Left for a later run: the farm's ramp replaced by one of ours, and a hole in the ground half covered by a patch (F-46).
Both need the farm's ground looks, which the materials audit gives.

## Result

Not played yet.
