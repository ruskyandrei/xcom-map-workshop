### What of a level's drawn geometry the export doesn't read: the D5 check

Stage D5 of the game-likeness plan: a check over the install for drawn geometry the map's export misses (BSP surfaces,
terrain, instanced meshes with more than one instance). Nothing the editor or a Build makes changes.

- **A research tool**, [audit_world_geometry.py](../../tools/upk/audit_world_geometry.py) (not shipped), with its
  evidence in [world-geometry-audit-2026-11-27.json](../../research/evidence/world-geometry-audit-2026-11-27.json):
  `survey` reads every map the install's records name and every package their records stream (231 in the lab copy):
  the level's model and its model components (the BSP nodes each draws, less invisible surfaces and portals, their
  materials and box), terrain and the engine's other world-geometry classes, and every instanced mesh component (a
  class whose chain in the script packages reaches `InstancedStaticMeshComponent`): its instances, and how many the
  game draws as the level loads (Enemy Within's toggled kind by the visibility bit of each instance's entry, read
  from the class's constant). `package` prints one package's record. Its readers of a model's geometry, a model
  component (a layout no tool read before) and an instanced component's instances are bounded by their export and
  must end on its last byte.
- **What was found** (findings register F-230, F-231):
  - no terrain, Landscape, SpeedTree, foliage, spline mesh or fluid surface in any package;
  - BSP drawn in one package only: Act2_Pier_script, a stream of the tutorial map, a box of 12 triangles in the
    engine's default material 3,200 units over its map (left undrawn);
  - the engine's own instanced meshes are the flamethrower's two on each map's level volume, empty and hidden;
  - the fracturing brick walls' decoration and debris are instanced meshes on the map's level volume (2,291
    components, 21,885 instances): 428 decoration chunks on 9 maps are drawn as the map loads, along the broken edges
    of the walls the map shows broken. A chunk is drawn where its fragment is there and a fragment across one of its
    faces is not: all 16,906 entries agree. The editor draws those walls' holes without the chunks. A stage to draw
    them is planned and not built; whether the game draws chunks for a Build's own breaks needs one look in the game.
- **Checked:** [test_audit_world_geometry.py](../../tools/upk/tests/test_audit_world_geometry.py) (the `upk` suite):
  the three readers on made-up packages, with their refusals; on the install, the toggled kind and its bit,
  Act2_Pier_script's box, URB_Bar with nothing drawn, URB_PoliceStation's 70 chunks and the rule on every entry
  (skipped without the install).
