### A material's parameter values read by a method of their own

A move, nothing else: the loop of `Exporter.material` that gathers a material's texture parameters, their sampling,
scalars, vectors, static switches, blend mode and sidedness through its parents is now `Exporter.parameters(chain)`,
which `material` calls. Stage E1 of the game-likeness plan makes a particle material's program from the same values
without exporting the material as a piece's.

- Where: [export.py](../../tools/viewer/export.py).
- Checked: CSmallScout_DirtRoad and URB_Bar exported before and after the move into scratch caches, their `scene.json`
  equal byte for byte.
