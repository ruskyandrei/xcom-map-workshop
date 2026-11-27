### The sun across the game's maps, and the time a whole map's sun shadows take

Stage T-S0 of the game-likeness plan (the sun plan's S0): what the time of day will need, read offline from the
install. Nothing the editor or a Build makes changes.

- **A research tool**, [audit_suns.py](../../tools/upk/audit_suns.py) (not shipped), with its evidence in
  [sun-audit-2026-11-27.json](../../research/evidence/sun-audit-2026-11-27.json):
  - `maps`: every base map the editor lists (97): its dominant light (height, yaw, colour, brightness, its shadow
    maps on the pieces, its own shadow map of the level), the other directional lights, the sky lights, the sky domes
    and their materials, each record's `TimeOfDay`, its lighting samples, its fog's colours and values and its grade
    and bloom (the editor's atmosphere reader), and what its light reads as (moon, dim, sunset, low sun, day);
  - `trace`: every sun shadow map of a map traced from nothing by the baker's own code (`fresh_shadow_map`) on the
    relight's own workers, counted and timed;
  - `level-map`: the dominant light's shadow map of the level held against the map's geometry;
  - `write-back`: the lighting samples' marks written into a scratch copy and read back, and the light writer tried
    on the dominant light's component.
- **New readers** in [lighting_records.py](../../tools/upk/lighting_records.py): `light_volume` (the lighting
  samples with their place; `probe_volume` now counts what it gives), `mark_places` and `mark_edits` (the
  fixed-size edits that set the samples' marks, as `package_edit.write_edited` takes them), `dominant_shadow_map`
  (the light's own map of the level: the depths saved ahead of the component's header, its size, matrices and
  light-space box) and `matrix_rows`.
- **What was found** (findings register F-175 to F-177):
  - 97 base maps, read by their light's colour: 50 blue moons, 10 dim lights, 16 day suns, 15 low suns, 3 sunsets,
    3 with no dominant light; the records say Night on 58 maps, Day on 32, both on 2, None on 5, and on 5 maps the
    light reads otherwise. 70 have a sky light (27 none), 93 a sky dome (NightSky on 44 of them); 12 have a plain
    directional light. Fog is on in 94 maps; 23 have a post-process volume that grades.
  - The light's own shadow map of the level is a grid of 16-bit depths along the light over its light-space box
    (URB_Bar: 132 by 97, about 50 units a texel); traced from the map's geometry, 92% of its texels lie within 25
    units of the stored depth.
  - `native_lights.set_property` writes the dominant light's component (brightness, colour, a flag added, the
    actor's rotation; GUIDs and shadow map kept), but only from the start past that shadow map:
    `native_lights.props_start` gives a start inside it, and the write is refused there.
  - **URB_Bar's every sun shadow map from nothing: 24 to 27 s with 16 workers** (the Build's number on a 32-thread
    computer), 2.1 minutes in one process: 627 components, 53 atlases, 4.78 million texels written, 67.5 million
    rays. 81 debris components with sun shadow maps (72,900 texels) are not read by the baker's component reader.
  - The samples' marks write back: all 1,743 of URB_Bar's flipped, read back, and written back as they were.
- Checked: [test_lighting_records.py](../../tools/upk/tests/test_lighting_records.py) (the volume and its marks'
  edits on made-up bytes, the shadow map of the level on made-up bytes and on URB_Bar); the tool's four runs; the
  `upk` and `repo` suites.
- Known gaps: the light's reading is by colour only (the records are the game's word); the trace's time is for the
  pieces' shadow maps alone, not the light's map of the level or the samples' marks (each a few thousand rays more).
  `lighting_records.py` is among the code the piece cache's key names (`relight.TOOL_FILES`), so a project's next
  baked build relights its pieces afresh once.
