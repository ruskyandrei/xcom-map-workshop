### A made ramp's mapped slope takes its texture in its own plane

A made ground ramp's sloped top was mapped as if projected from above, so a repeat of 64 drew about 67.5 long up a
slope rising 100 over 300 (1 / cos of its angle), and the Texture mapping fold's handles worked on that projection. The
slope is now mapped in its own plane, in the generator and on the page alike:

- The rule ([uv_mapping.py](../../tools/bake/uv_mapping.py) `along_slope`, `slope_extent`, written in its docstring):
  a point of the slope is at a = x0 plus its distance up the slope from the low edge, b = y; the slope's extent runs
  from x0 to x0 plus its length. Its low edge keeps a = x0, where a flat top beside it has it too.
- Aligned to the world: the frame's place is added as on any top (a + its x, b + its y), so the pattern lines up with
  the world's, and with a flat top's aligned to it, along the low edge, and runs up the slope by its true length from
  there; at the high edge it no longer meets a flat top's (the slope is longer than its run).
- [ground.py](../../tools/bake/ground.py) `faces_of` maps a free ramp's slope by it when its mapping lists the top.
  The look's own texture (no mapping) stays projected from above, as the donor's top is; a rock's faces stay projected
  too; a ramp steeper than 60 degrees has its slope among its sides, as before.
- The page's twin ([made_mapping.js](../../tools/viewer/web/made_mapping.js)): `surfacePlane` gives the ramp's top a
  unit axis up the slope (its origin where a = 0), `surfaceExtent` the slope's run up it, and `surfaceAt` now reads a
  point's place from the plane itself (its signature is `(plane, p)`;
  [made_mapping_wiring.js](../../tools/viewer/web/made_mapping_wiring.js)'s drags and test hooks hand it the plane),
  so the blue dot, ring and white dot sit and drag on the slope, a unit of the surface a unit up it.
- Shared cases: [slope_mapping_cases.json](../../tools/bake/tests/slope_mapping_cases.json) (four ramps and mappings:
  a repeat's size, a fit, a turned and flipped count, one aligned to the world from x0 96 at z0 -20), read by
  [test_texture_mapping.py](../../tools/bake/tests/test_texture_mapping.py) (the places, the extent, the rule, and the
  built slope's corners) and [shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs).
- [ARCHITECTURE.md](../../ARCHITECTURE.md)'s texture mapping row names the case file.

Checked: test_texture_mapping.py (the ramp's slope under a 30-degree fit over the slope's extent, a repeat of 50 up
the slope, the shared cases; free numbers without a mapping still byte for byte with their digests) and the bake
suite; made_mapping_test.mjs (the slope's plane, normal, extent, its low and high edges, a point and back) and the
shared cases; the `texture-mapping` browser check's new ramp part (the blue dot on the slope, 100 of the surface 100
up it, the slope's extent its length, the pattern slid along it), `rock-corner`, `free-handles`, `api-names`; against
`04b9ee4`, the commit the branch started from, with this work order's three changes in: the quick and baked Builds of
build_outputs.py's 11 inputs the same (none maps a ramp), and every compile of the editor suite (compile_record.py)
the same but the three of the new atlas-note test.

Known gaps: a ramp with no mapping still draws its look's texture projected from above, stretched up a steep slope (the
donor's own top is mapped that way, and the look is the donor's); a slope steeper than 60 degrees is mapped as a side
(b up the height, stretched by 1 / sin of its angle). Rocks keep their projection.
