### The bake tools walk a grown package with the grower's names

Review finding 37. The property walker of the bake tools read tag names through the map's own name table, while
every writer adds a name new to the map to the grower's table, past the end of the map's. The next walk over that
object then stopped with "bad property name". Ten call sites patched the walker's names by hand, nine more used
`buildings.grown_walker`, and the rest did not. A Build stopped on it where it was reproduced: a copy with "Mouse picks
it" off on a map no object of which saves that flag's property (URB_HighwayFallen; CB2_MP_Blank and Command1 lack it
too), in `link_children`; and a light changed in two values it does not save where the first is new to the map, on
CsmallScout_Farm (a point light's falloff exponent) and CBattleship_01 (a spot light's inner cone).

- [native_copy.py](../../tools/bake/native_copy.py)'s `Walker(p, g)` takes its names from the grower `g` when it is
  given one; every site with a grower in hand passes it, in [native_copy.py](../../tools/bake/native_copy.py),
  [native_lights.py](../../tools/bake/native_lights.py), [buildings.py](../../tools/bake/buildings.py),
  [frac_walls.py](../../tools/bake/frac_walls.py), [made_cursors.py](../../tools/bake/made_cursors.py),
  [native_effects.py](../../tools/bake/native_effects.py), [native_spawns.py](../../tools/bake/native_spawns.py),
  [shell.py](../../tools/bake/shell.py), [intro_copy.py](../../tools/bake/intro_copy.py) and
  [stream_copy.py](../../tools/bake/stream_copy.py). The hand patches and `buildings.grown_walker` are gone. A walker
  of the pristine map, or of a written one, is built without a grower as before.
- Checked: [test_native_lights.py](../../tools/bake/tests/test_native_lights.py)'s fake package keeps its own copy
  of the name list, as the real reader does, so its property tests no longer pass by sharing the grower's list; a new
  synthetic test adds a name new to the map, writes another value and walks again. New map-backed tests add a name new
  to the map and walk again through each writer that stopped: `link_children` and `move_columns` after a copy's mouse
  flag on URB_HighwayFallen ([test_native_flags.py](../../tools/bake/tests/test_native_flags.py); the second on a
  fracturing copy whose columns are cut out, the case the review named), and `native_lights.apply` on
  CsmallScout_Farm and CBattleship_01. Each failed before the change. They skip without the maps. The bake and upk
  suites pass.
