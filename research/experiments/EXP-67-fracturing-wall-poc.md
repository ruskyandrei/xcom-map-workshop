# EXP-67: a fracturing wall made from numbers (proof of concept)

Date: 17 November 2026. Status: **prepared, not played.** The custom geometry plan's section 0, stage F4, at the
user's ask ("can we first focus on getting a PoC of a fracturing custom wall and see if (a) we can get them to look
good and similar to the ones the game has, (b) we can get them to fracture similarly"). Stages F0 to F3 were built
and checked offline the same day; this run is the one thing they cannot answer: what the game does with the walls.
Findings: [T-42](../findings-register.md).

## What was built (offline, no game)

- **F0, the audit** ([frac-wall-audit.py](../evidence/frac-wall-audit.py),
  [its numbers](../evidence/frac-wall-audit-2026-11-17.json)), over the install's 151 maps: every one of 25,209 static
  and 1,679 fracturing meshes written back from its numbers byte for byte; on the 664 fracturing meshes, each
  collision triangle's fourth value is its section's slot times the fragment count plus its fragment (858,183 of
  858,183); 644 placed walls and their 13,392 columns: the box rule gives 11,069 of the 11,463 columns a tile long and
  a storey tall, and MinZ, the sort by it, the component's fragment heights and index count follow from the mesh on
  every wall (T-42 has the details).
- **F1, the writer** ([gen_mesh.py](../../tools/bake/gen_mesh.py)): a static or fracturing mesh's native data read
  as numbers and written back; its collision tree made for new triangles.
- **F2, the generator** ([frac_wall.py](../../tools/bake/frac_wall.py)): a wall from its numbers (its ends, its
  openings, a seed), built as the donor is: six slots, the donor's cross-section with its skirting and cornice, its
  texture repeats, Voronoi fragments through the thickness, their inside faces, records and neighbours, lightmap
  coordinates and one collision box for each solid round the openings.
- **F3, the Build** ([frac_walls.py](../../tools/bake/frac_walls.py), with
  [native_copy.py](../../tools/bake/native_copy.py) and [relight.py](../../tools/bake/relight.py)): a copy of a
  fracturing piece that carries `generated` is cloned as any is, then given the new mesh (under the package
  `XComMapEdGeo`), its body setup, the component's saved numbers and painted colours, and its columns by F0's rule;
  it is lit from nothing and its tiles rebuilt over its own box. A project carries the request on an added copy
  ([compiler.py](../../tools/editor/compiler.py); the editor keeps it on save).

Read back from the built map with a fresh reader: both new meshes write back byte for byte; each component names its
mesh, with its lowest and highest fragment heights and its index count as the game's walls save them and one painted
colour for each vertex; each column lists exactly the fragments whose box overlaps it, lowest first; the level lists
the three walls. The built map's export (a scratch cache) shows the twin and the reference alike, and the custom
wall with its doorway, on the donor's materials (`EXP-67-row.png`, `EXP-67-twin.png`, `EXP-67-custom.png`,
`EXP-67-custom-north.png`; [the shots file](EXP-67-shots.json)): the lower storey's diamond tiles and the dark upper
storey on the south face, brick over panelling on the north, the skirting and cornice and the ends' caps, the storey
line at the same height on both; the doorway cut clean through the trims.

## The project

`EXP-67 fracturing walls` (URB_Bar, [exp67_project.py](../../tools/editor/examples/exp67_project.py), in the
editor's project store), a full build with the lighting baked (`EXP67FracturingWalls-20261117-003949`: the map
`EXP67FracturingWalls`, its SHA-256 starting `9e838a5f323b`; the shots above are of a scratch build of the same
project, `URB_Bar_X67`, whose walls are the same meshes). Three copies of the bar's inside wall
`URB_BarIntWallB_FRACTURED` (`XComDecoFracLevelActor_17`, 560 long, 400 tall, two storeys), each at yaw 0 on the tile
edge y −192 between the pavement's middle and south rows, west to east:

| Mark | What stands there | Built as | x (world) |
| --- | --- | --- | --- |
| R | the reference: the donor's own mesh, lit from nothing as the made walls are | `XComDecoFracLevelActor_18` | −1720 to −1160 |
| T | the twin: made from numbers at the donor's own size (30 fragments, 808 triangles, seed 1) | `XComDecoFracLevelActor_19` | −952 to −392 |
| C | the custom wall: four tiles (27 fragments, 620 triangles, seed 2), a doorway one tile wide and 176 tall | `XComDecoFracLevelActor_20` | −192 to 192; doorway −96 to 0 |

R and T differ only in their meshes: same materials, toughness, rubble and effects, same light (both lit fresh). R is
used in place of the donor where it stands in the bar, whose light is the room's.

Known before the run, and not held against it:
- A made wall's columns list no neighbouring walls and none list it: a blast does not spread across a joint to or
  from it (F-69's limit). These three stand apart anyway.
- Its columns list no props hung on it (none are).
- Its collision tree's nodes don't narrow (each child keeps its parent's box): every check through it tests every
  triangle. The game's own trees narrow on all but 50 of 249,031 inner nodes. If a shot or a trace goes through T or C
  where R stops it, the tree is the first suspect.
- The walls stand outside the bar's building ("in no building floor"): they don't cut away with its storeys. A wall
  inside a building is a later check.

## Run 1

Play in game on the project's build, the test squad; **Enable saving** on for step 8. What the run adds over the
offline checks:

**(a) The look**
1. **R and T side by side, south face (tiles):** do they look alike: surfaces, the storey line, the skirting and the
   cornice, the ends? Any seam, crack or dark line on T that R hasn't?
2. **North face (brick over panelling):** the same question, from the gap between the walls and the bar.
3. **C:** the doorway's sides and top (the inside faces should not show until it breaks; the trims stop at the
   doorway's sides), and the light on it against R's and T's.

**(b) The break**
4. **Rifle fire** at R, T and C, a few shots each at about the same place (the lower storey): do holes open on each,
   of about the same size and raggedness? Rubble and impact effects on all three? The destroyed material on what is
   left round the hole?
5. **A grenade** against each (or a rocket): the same questions, and does anything float or stay standing that should
   fall (a fragment with nothing under it)?
6. **Cover and walking:** a soldier beside C's doorway, on either side: is there a full shield toward the wall? Can a
   soldier walk through the doorway? Through a hole the grenade made down to the ground, on T?
7. **Sight:** a soldier and an alien either side of a hole: are they seen through it, and can a shot be taken through
   it? A shot at an unbroken part of T or C stops there (see the tree, above).

**(c) Save and reload**
8. With all three broken: save (say which slot), load it. Are the holes still there, and the same?
9. Anything odd: a crash, a wall drawn wrong or black, a part of a wall that can be walked through while it stands.

Claude reads `Launch.log` after the run, and the save with [save_tiles.py](../../tools/lab/save_tiles.py) (the tiles
round the walls), and looks at what the user shows with F9.

What it can say (the plan's section 0.2): **both pass**: the plan is rewritten round fracturing walls; **the look
passes, the break does not**: walls that look like the game's and break a panel at a time; **neither**: the plan's
sections 1 to 8 as written.
