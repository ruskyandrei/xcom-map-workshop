# EXP-76: a made upper floor and roof over a room of made walls (custom geometry plan, M5, run E)

Date: 18 November 2026. Status: **prepared**. Part of the custom geometry plan's stage M5 (branch
`fracturing-wall-poc`): floor and roof slabs made from numbers. Each is a copy of one of the game's fracturing slabs
with its own mesh (tools/bake/frac_slab.py), columns by the slabs' rule, and the donor's floor flags. Played
unattended in the lab copy (the hidden game, the game-test skill), checking only what is new.

## What is new

- A slab made from numbers: its fragments (half tiles cut on a diagonal, whole and double tiles), its top and
  underside on its donor's materials, a collision box for each solid strip round its holes.
- A made upper floor: units walk on it, it is floor where there is standing room over it, and a hole in it is no
  floor.
- A made roof: in its building's top floor, cut away with it when the cursor is inside, and (the donor's flags) taking
  no clicks.
- A break in a slab: what falls, and what the tiles over and under it become.

## The project

`EXP-76 floors and roofs` ([exp76_project.py](../../tools/editor/examples/exp76_project.py)) is in a test server's
scratch store. Its map, `EXP76FloorsAndRoofs`, is built with the lighting baked, on URB_Bar's parking lot (floor 0).
Game tiles count from the map's corner (-2785, -1921, -1), so tile centres are at x -2737 + 96 i, y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| Room | x -1728 to -1344, y -1056 to -768; a doorway in its south side at x -1632 to -1536 | four made walls (the bar's inside wall), two storeys, joined at the corners |
| Floor | over the whole room, its top at 194; a hole at x -1536 to -1440, y -960 to -864 | a copy of the bar's upstairs floor (`XComFracLevelActor_17`), made from numbers |
| Roof | over the whole room, its top at 386 | a copy of the bar's roof (`XComFracLevelActor_3`), made from numbers |
| Building | the room's footprint: floor 1 from -16 to 208, floor 2 from 208 to 400 | as the Room with a roof tool makes it |
| Lone roof | x -1152 to -960, y -1056 to -864, its top at 386, nothing under it | a roof standing in the air |

The room's tiles: x centres -1681, -1585, -1489, -1393; y centres -1009, -913, -817. The doorway's tile is
(-1585, -1009). The hole's tile is (-1489, -913).

## Run E (hidden game, with saving)

1. **Load**: the battle starts on `EXP76FloorsAndRoofs`, with no crash and no error naming a slab.
2. **The look**:
   - from the default camera outside, the roof's top and the room;
   - from overhead with the fog off, the lone roof;
   - the roof's top on its donor's gravel material, lit, with no holes or flicker.
3. **Under the floor**: a soldier walks in through the doorway, (-1585, -1105) to (-1585, -1009), then to (-1681, -817):
   - he stands on the ground floor (z about 0);
   - the camera's floor shows the ground, with the floor and roof cut away over him;
   - a shot looking up at the hole from the ground.
4. **On the floor**: a soldier is put on the upper floor at (-1681, -1009), storey 1 (`aim ... --floor 1`, then
   TeleportToCursor) and walks to (-1393, -817), storey 1:
   - he stands at about 194 and the walk is a path over the slab;
   - he cannot be sent onto the hole's tile (-1489, -913) on storey 1 (no floor there): "did not move", or he ends
     beside it.
5. **The roof takes no clicks**: the cursor aimed inside the room on the ground floor lands at about 0, and aimed on
   storey 1 at about 194, never on the roof (386). Read with ShowCursorLoc.
6. **A break in the floor**: from the upper floor, a grenade on (-1393, -1009), storey 1 (two tiles from the hole):
   - the floor holed there, and what falls;
   - whether the walls under it and the roof over it stay (F-127);
   - a soldier standing on a floor tile that breaks (put him on (-1393, -817), storey 1, and throw at his tile):
     does the game drop him to the ground below and keep him in play (T-47: the game's landing event fires for a prop
     whose mesh swaps, and has not been seen for a fragment gone from a floor)?
   - the soldier on the floor sent onto the broken tile: does the game still take it as floor?
   - a soldier on the ground under it;
   - the save's tiles if needed (tools/lab/save_tiles.py).
7. **Save and load**: a quicksave after the break, then a load. The hole the grenade made is still there, and the
   soldiers stand where they stood.

## Result

Not played yet.
