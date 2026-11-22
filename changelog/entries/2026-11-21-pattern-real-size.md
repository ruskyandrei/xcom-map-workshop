### The Texture mapping fold says a pattern's real size where the material's own tiling is known

A repeat is one unit of a mesh's texture coordinates, and a material may multiply them itself: a building material's
TileXY of 1.25 draws its texture 1.25 times in each, so a repeat of 192 shows the pattern every 153.6. The map's
export records that multiplier in a material's `render.uv.scale` where it reads one (a texture coordinate node's
tiling, or a building material's TileXY: [materials.py](../../tools/viewer/materials.py) `profile`), and the page
already draws by it; it doesn't say where it found nothing to read. The fold now uses what the export has, without a
new export:

- [made_mapping.js](../../tools/viewer/web/made_mapping.js) `materialTiling`: a material's multiplier and whether it
  is known (a scale other than 1, or a family whose tiling scalar the export reads, BLDG_Enterable, at 1 too; not a
  material whose coordinates go through a node the export can't follow, nor one it read nothing of, whose 1 is only
  the default). `surfaceSlots`: the slots a surface draws in, from its look's catalogue entry (a wall's picked side's);
  every drawn material of the piece where its look is in no catalogue. `patternSize`: on a mapped surface whose
  materials are all known and scale alike, the note "Its material repeats its texture 2 times in each repeat: the
  pattern shows every 96" (in counts: "3.75 by 2.5 times over the surface"; one axis each way: "every 48 along U and 3
  times along V").
- [made_mapping_wiring.js](../../tools/viewer/web/made_mapping_wiring.js): the note under the modes; where a material
  of the surface isn't known, the Repeat row's tooltip (`texRepeat` in [index.html](../../tools/viewer/web/index.html))
  says its material may scale its texture itself, which the export doesn't record, so the pattern may repeat more
  often than a repeat.
- One rule on both sides through [material_tiling_cases.json](../../tools/viewer/tests/material_tiling_cases.json):
  `materials.profile` gives each case's uv ([test_materials_and_floors.py](../../tools/viewer/tests/test_materials_and_floors.py)),
  `materialTiling` reads it known or not ([shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs)).

What it finds (the 2,408 materials of the 35 cached exports): the export read a multiplier for the building materials
alone (97 with TileXY: 86 at 1, 10 at 1.25, 1 at 1.2); no texture coordinate node's tiling was read anywhere (cooked
materials keep few expressions). Of the walls' catalogue, 114 looks' faces draw in a material at 1.25 or 1.2 (their
pattern's size is said) and 101 at a known 1; slabs (BLDG_Floors) and nearly all ground materials are not known.

Checked: [made_mapping_test.mjs](../../tools/viewer/tests/made_mapping_test.mjs) (the words in each mode, nothing for
an unscaled, unmapped or mixed surface, not known when any material isn't, the slots); the shared cases both sides;
the `texture-mapping` browser check (a wall's materials recorded at twice say the pattern is 96, at an unread 1 the
Repeat row says it may scale), `api-names`; web_names clean.

Known gaps: an export change would add what this can't show: whether a material's multiplier was read at all (a
`known` beside `render.uv`, so a read 1 and the default 1 differ for every family), and the tiling scalars other
families carry and the export doesn't apply (RoadAndSidewalk_Material's and Basic_Material's TileU, TileV and TileUV,
PROP_Objects_Tile's TileX and TileY, HQ_Props' Tile U and Tile V, ENV_Terrain's Tile, ENV_ForestGround's Rock_Tile,
M_Alien_Machinery's Tiling), each needing its shader's use of them confirmed, and materials that project by the world
(none recognised). It would raise `EXPORT_VERSION`, which this change does not.
