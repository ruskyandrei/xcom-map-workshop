### The game's cover rule worked out from a map's pieces, and a diagonal cover finder checked against the game's maps

Stage C1 of the diagonal cover plan: the first part of writing diagonal cover tiles in the Build. Nothing a Build
makes changes yet.

- [tile_world.py](../../tools/bake/tile_world.py), new: a map's listed actors as the game's tile build traces them:
  each mesh component's simple collision (convex hulls and boxes, with their saved face normals and edge directions)
  or triangles, placed in the world; the flags the trace kinds filter on (`cover`, `height`, `engine`, and the
  occupancy's still box), every property read through the archetypes in the map down to the game's script defaults
  (`Resolver`); a separating-axis box sweep, a line check and an overlap test; `solid_piece` and `World.empty` for
  pieces made elsewhere.
- [tile_rule.py](../../tools/bake/tile_rule.py), new: the cover step for one tile as research/native/cover-build.md
  reads it (sections 3 and 4, steps 1 to 13), straight or diagonal, with the build's visiting order for the step-outs'
  floor test; `finder`: a wall at 45 degrees crossing the tile, high cover, no straight cover.
- [diagonal-finder.py](../../research/evidence/diagonal-finder.py), new, and its record
  [diagonal-finder-2026-11-22.json](../../research/evidence/diagonal-finder-2026-11-22.json): the rule and the finder
  over the install's 97 base maps against their bakes.
- [findings-register.md](../../research/findings-register.md): F-151. [ARCHITECTURE.md](../../ARCHITECTURE.md): the
  tile build's row.

Checked: [test_tile_rule.py](../../tools/bake/tests/test_tile_rule.py) (sweeps on pieces made here: a face met at the
box's distance, a box passing an edge, a start inside, a turned face, the kinds' filters, an overlap; a 45-degree
corner's diagonal cover and its location, the finder's three conditions, the visiting order; CsmallScout_Farm's
eight marked tiles bit for bit and to 0.15 unit, the finder taking them and leaving a bulldozer's corner); the check
over the install: 293 of 293 marked tiles exact.

Known gaps: the finder's condition is the designers' usual choice, not their rule (F-151: 245 of 289, 110 unmarked
of the same kind); pieces of streamed levels, PathBlockingVolumes, terrain and fragments a fracturing piece lost are
not read; a sweep that starts inside a solid is taken as a hit at once (not read in the exe; none on a marked tile).
