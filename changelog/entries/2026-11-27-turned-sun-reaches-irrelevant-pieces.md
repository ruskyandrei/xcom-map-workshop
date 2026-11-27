### A turned sun reaches the pieces wholly in the old sun's shadow

A lightmapped piece wholly in a map's own sun's shadow lists the light on its IrrelevantLights and has no shadow map
of it, so a Build that turned the sun left it without the new one (F-198). Now, in a Build with baking whose sun
turned, the copy tool's step before the relight ([sun_bake.py](../../tools/bake/sun_bake.py) `own_shadow_maps`, called
by [native_copy.py](../../tools/bake/native_copy.py) `build` on the grown map with the light turned in it) traces each
such piece of the level toward the new sun in the scene after the edit, and gives each it reaches on a texel at least
a shadow map of its own, laid out on the piece's lightmap rectangle with a texel's ring, and takes the light off its
list, as a made piece is given one: it reuses [frac_walls.py](../../tools/bake/frac_walls.py)' `dominant_shadow`,
`own_shadow_size`, `shadow_map_export`, `irrelevant` and `set_shadow_refs`, through the growing writer, and reads the
map back. The relight's whole-map trace then fills the new maps. A piece that keeps a map of the light beside the
list keeps it and loses only the entry; the pieces the new sun does not reach stay as the map has them. The writer's
record says which (`sunShadowMaps`), and [build.py](../../tools/editor/build.py)'s light stage counts them
(`sunTurned.piecesGivenShadowMaps`).

Checked by the bake suite's [test_sun_bake.py](../../tools/bake/tests/test_sun_bake.py): a shadow map's layout, and a
made-up piece reached on all, some or none of its texels; URB_Bar built through the copy tool with the sun lane turning
its moon to a sun 16 degrees up from the west, read back: 60 of its 314 such pieces given maps (59 of their own, one
that kept its own), their 359,045 texel centres on the side a ray gives on 99.35% (99.99% away from the shadows'
edges), the 254 others byte for byte the map's and reached by the sun on no texel. The step takes 5.5 s on URB_Bar,
and the relight's trace grows with the new maps (767 shadow maps; the copy tool's whole run 41.6 s, 31 s before).
F-198 fixed.

Known gaps: the helpers stay in frac_walls.py, which sun_bake.py imports for them (a move to a module of their own
could follow); a piece reached only between its texels' centres is left out; nothing is seen in the game yet
(EXP-100).
