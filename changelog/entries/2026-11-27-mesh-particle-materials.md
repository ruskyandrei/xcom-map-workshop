### Mesh particles drawn with their MeshMaterial module's materials (draw version 8, export 50)

The crashed Raider's plasma fire in CLrgScout_TheBarrens (P_Plasma_Fire_A) was drawn as a still, see-through green
shape. Its burst mesh has no material of its own. The game draws it with the material its emitter's MeshMaterial
module lists, M_Plasma_Fire_Mesh (added, unlit, two-sided). The export never read that module, so the mesh took the
neutral stand-in. Findings register F-233.

- **The rule.** Each section of a mesh emitter's mesh is drawn with what its enabled MeshMaterial modules list for that
  section. Failing that, it takes the emitter's material where its type data overrides the mesh's, then the mesh's
  own. The section's material, program, blend and lighting follow:
  [effects_draw.py](../../tools/viewer/effects_draw.py) `mesh_materials`, and `Exporter.particle_mesh` in
  [export.py](../../tools/viewer/export.py). Draw version 8, export 50, and the contract
  ([editor-contracts.md](../../research/editor-contracts.md), section on an emitter's `draw`).
- **What else changes.** In the 43 maps the cache held, 20 systems now draw otherwise. Those drawn with the stand-in
  before: the plasma plumes and destroyed power core, the hologram nav sphere, the flying seagulls, the shock rings
  and the generators' electric ball. The seagulls lose the sparrows' materials, the unlit rats lose the lit ones, and
  the hologram wall's face and the machines' debris take their own.
- **Checked.** In [test_effects_draw.py](../../tools/viewer/tests/test_effects_draw.py) (the `viewer` suite):
  - the modules' list on a made-up package (a switched-off module skipped, a later one's entry winning);
  - the order of module, override and the mesh's own;
  - on the install, the Barrens plasma fire's burst drawn with M_Plasma_Fire_Mesh, added, unlit and two-sided, with
    its program.

  The viewer, editor, repo and node suites pass. 11 viewer tests were skipped because a game was open, and 4 editor
  tests because the blank map had no export. On a test server, the Barrens map exported anew shows the fire as
  glowing green wisps in both looks, with no console errors, and its holograms are see-through, none grey.
- **Known gaps.**
  - Where an emitter has both a module and an override, the module comes first. That order is read from Firaxis's
    settings (Machine_Alien's alien debris material would never show otherwise), not from the engine's code.
  - Nothing was played: the fire was not compared with the game side by side.
  - Every map is exported again on its next open (export 50).
