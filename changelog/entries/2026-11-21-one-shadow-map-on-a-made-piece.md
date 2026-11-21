### A made piece lists one shadow map of the moon, its own: the donor's is no longer cloned

A wall, slab or ground shape made from numbers on a donor that stands outdoors kept its donor's shadow map of the
map's dominant light (the moon), cloned with its texture and listed first, and got its own added after it (follow-up
2.2). The donor's map is laid out for the donor's mesh, not the piece's: the relight traced it again on the made mesh
over the donor's whole rectangle (up to 262 x 262 texels against the piece's own 16 x 56), each one written as a texture
of its own, and the game never had a component that lists two maps of one light (none of 4,074 components with a
moon map in six maps does: URB_Bar, URB_PoliceStation, URB_CommercialAlley, URB_Demolition_EWI, TempleShip,
CLrgScout_ForestTrench). Now:

- [native_copy.py](../../tools/bake/native_copy.py): `made_shadow_maps` names the donor's LOD 0 distance-field maps of
  the dominant light on the component that gets the made mesh (every distance field of a piece of another map, which
  the copy points at that light; a map another LOD lists too stays, none of the six maps has one); `clone_assembly`
  (its new `made`) clones neither them nor their textures and says which it left (`uncloned`); `clone_copies` passes
  the made components, found by [frac_walls.py](../../tools/bake/frac_walls.py)'s new `made_component` (`donor_component`
  is now the one place that says which component a made kind takes, `add_walls` included).
- `frac_walls.set_shadow_refs` (in place of `add_shadow_ref`) writes LOD 0's list without those maps and with the
  piece's own at its end. A piece that gets no map of its own (the light listed irrelevant) keeps none of the donor's
  for that light either. Maps of other lights stay. The Build's record of the piece (`generatedWalls`' `shadowMap`,
  written by the new `shadow_record`) names the donor maps left out (`donorMapsLeftOut`), where there were any.
- In a Build without baking the same holds: the donor's map (read from the donor's own texture) is not cloned, and the
  piece lists the even light's piece's map at one texel alone, as an inside donor's copy did already.

Checked:

- [test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py), each new test failing before the change (two maps
  listed, or no `set_shadow_refs`): `LodReaders` (the list written with the donor's taken out, the own added, or none
  left); `BakedLayout` gains a block on the Bar's asphalt (XComLevelActor_131, outdoors) beside its walls on the inside
  donor: one map, its own, the donor's neither cloned nor listed, its texture not cloned; `GroundShapes` (the one class
  that runs `--fresh-copy`, follow-up 4.6b) now asserts on the relight's output: each shape lists its own map alone,
  traced from nothing over its lightmap rectangle and nothing else, and the relight wrote both lightmap images into the
  shape's own cloned atlas over that rectangle (moved to the variant's texture cache, or kept in the map where the
  atlas's mips all lie there). [test_native_copy.py](../../tools/bake/tests/test_native_copy.py)'s `MadeShadowMaps`:
  the asphalt's moon map is the one left, an inside wall leaves none, a map with no dominant light none, a 'relit'
  copy has no made component. The bake suite: 713 tests pass, 1 skipped (the transplant ring), 379 s with other work
  on the computer.
- `build_outputs.py` record on the start commit and on the change, compare: only `bar-flags` and `bar-made` differ, in
  the variant map and the manifest's hash of it. By the packages kept: bar-flags has 2 exports fewer (two made slabs'
  cloned ShadowMap2D_4264, their donor a roof outdoors) and 540 bytes less, bar-made 1 fewer and 270 bytes less; the
  made pieces' components are 4 bytes shorter (one reference less in LOD 0's list); of the 14,419 and 14,320 exports in
  both, every other one is the same or differs only by references renumbered, bulk offsets moved and net indices.
- The real baked ground Build (EXP-77's made ground, 16 made pieces on URB_Bar), at the start commit and twice on the
  change: 14 pieces listed two maps, now one; the 16 own maps are byte for byte as before (coordinate scale and bias,
  light, every mip of their textures); 14 cloned maps and textures (12,760,402 bytes of mips) are gone: the shipped map
  77,280,666 -> 64,387,486 bytes, the relight's texture cache 55,564,258 -> 42,814,782; the relight traces 34 shadow maps,
  not 48, and their summed worker seconds were 67.6 -> 19.4 and 17.8 (the computer loaded by other stages' work;
  `relight_probe.py`: the fresh pieces' maps 45.7 -> 1.4 s summed, the replayed pool clock 17.4 -> 16.5 s, as the shadow
  maps ran beside the pieces). Every other file of the package and every relit image and kept piece (183) is byte for
  byte the same; the two runs on the change are identical but for times. The bar-floor Build (no made piece) is byte
  for byte the baseline's, twice.

Not yet seen in the game (decision D1): which of two listed maps the game draws was never checked; with one listed,
the piece's own is drawn. The follow-ups' stage B3 prepared the hidden game run; its result goes into the findings
register and an experiment file, and this change merges only if it passes.
