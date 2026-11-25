# EXP-20: the growing writer (gate C6; baker step L4, UDK-removal U2)

Date: **7 November 2026**. Status: **run 1 passed (deployed 13:26): the game loads a grown map, and the bar's east floor reads its light from two new texture exports; run 2 passed (13:47): a lamp post copied as a new actor of the map stands in the game, lit like its neighbours;
run 3 passed for the lighting (14:12: the copy baked for where it stands, through a save and reload), but a
soldier could walk into the copy (F-57); run 4 (the copy with its tiles: seeds and a rebuild volume) hung while
loading (T-14: the writer split an export-table field across two compressed chunks); run 4b (the writer cuts chunks
only where an item starts) passed (15:22: the mission loads, the copy blocks and gives cover); run 5 passed (15:51: the lamp post
and a dumpster copied into one variant; the dumpster breaks as the map's own do); run 6 passed (16:31: the editor's
Build makes a project's copies natively, EXP-13's destructible props; they stand lit, break, and survive a save and
reload, and the log shows no clone's net index twice); run 7 passed (16:59: the temple project, its stacked console pairs made in the map and linked there;
they are lit, and break together); run 8 passed (18:04: the pool table moved, its originals taken out of the map, no patch;
gone from the old place, standing lit at the new, broken, through a save and reload; but no dropship intro, F-45);
run 9 passed (the same with the variant's own intro copy: the Skyranger lands, F-45 verified); run 10 (Temple
Ship's power cores, two copied and one deleted, counted as loot) could not end its mission, Temple Ship being scripted
as the final mission: the loot count is left for the UFO maps**.
Design: standalone baker, gate C6 in section 5 and step L4 in section 13;
UDK-removal plan, U2 and section 3.3. Branch `standalone-baker`. Tools:
[`package_grow.py`](../../tools/upk/package_grow.py), [`grow_fixture.py`](../../tools/bake/grow_fixture.py).

## Question

Every map edit so far kept the package's size: fixed-size field changes, new mips in a separate cache. Baking a copy
into the map (L4) needs new objects in the package: new textures at first, then a new actor and component. Can we
add exports to a cooked EW map so that the game loads them?

The UDK-removal plan names appending as the first layout to try, "not an assumed legal UE3 layout" until the game
takes it.

## The layout (the bar's map, `URB_Bar.upk`)

- An uncompressed summary (4,909 bytes in the file), then 26 LZO chunks. The logical offsets start at 4,493: the
  file's summary is 416 bytes longer than the logical one, its chunk table. So physical and logical offsets are
  already independent.
- Chunk 0 is the header: the name table (3,620), the import table (331), the export table (14,051 entries, 956,216
  bytes: 68 each, more with net object counts) and the depends map (an empty array per export, 4 bytes each). The
  summary's header size (1,132,833) ends it.
- Then export data, contiguous, to the logical end (28,491,606), with no holes. Inline bulk data (small mips) holds
  absolute logical offsets.
- After the summary's known fields come 4,368 bytes of texture allocations (export indices for preallocation),
  copied as they are.

## The writer: append, move only the tables

[`package_grow.py`](../../tools/upk/package_grow.py) leaves every byte of the old package where it is:
- fixed-size edits in place, as before (`package_edit.py`);
- new exports' data, and the new data of any export that grows (relocated; its old bytes stay, unreferenced), after
  the logical end;
- then a new export table (the old entries, then the new ones) and depends map, and a new name table only when names
  are added;
- all of that in new literal-LZO chunks after the last;
- the summary points at the new tables, with the new counts (its generation's too), and its chunk table gains the new
  chunks.

So no export moves, and no inline bulk offset changes, except inside data the caller places, from `next_offset()`.
What the game has to accept: the export table and depends map after all export data, far past the header size, and
a chunk appended after the last.

## Run 1: two lightmap textures cloned for the bar's east floor (built and deployed 7 November)

[`grow_fixture.py`](../../tools/bake/grow_fixture.py), cache `Lighting_7005`:
1. The east half of the bar's floor, `XComLevelActor_302` (the room around the central counter), reads its light from
   `NormalizedAverageColor0_5` and `DirectionalMaxComponent0_5`, two 1024² atlases that 69 other components share.
2. Both are cloned as new exports, `NormalizedAverageColor0_91` (14,052) and `DirectionalMaxComponent0_91`
   (14,053): the same class, outer and flags, a new name number, their data copied with the inline mips' offsets
   moved. The floor's slots 0 and 1 point at the clones.
3. The fixed-size tools then paint the floor's rectangle **green** in the clone's colour texture, and **blue** in the
   original's. No component reads that rectangle of the original any more.

**Checked offline:**
- The grown map reads back with 14,053 exports, both clones of class `LightMapTexture2D`.
- The floor's slots name the clones. The clone's colour texture is green at the floor's rectangle, the original's blue.
  The directional clone reads the same texels as its original.
- The 69 other components still read the originals.
- Tests ([`test_package_grow.py`](../../tools/upk/tests/test_package_grow.py)): a growing write with no change keeps
  every export where it was and moves only the tables. A new name and a relocated export read back. Cloned textures
  read back with their own inline payloads at their new offsets.

**What to look at** (a new campaign; the first mission is the bar; no dropship cutscene, as in EXP-17 run 1, F-45):
1. **The mission loads.** A crash or hang while loading means the game refuses the appended tables or chunk.
2. **Inside the bar, roof cut away, the floor around the central counter:**
   - green (keeping its plank detail and its pools of light): the game reads the new exports, and C6 passes;
   - blue: it reads the originals by name, not the clones;
   - black or garbage: the clones load but their data doesn't.
3. **The rest looks normal:** the other half of the floor, behind the brick partition; the rug; the ceiling ducts; the
   sidewalk and asphalt outside. They read the original atlases.

**Result (13:28; four shots, 13:28:14 to 13:28:30): passes.**
- **The mission loaded.** The game takes the appended chunk, and the export table and depends map after all export
  data, 27 MB past the summary's header size.
- **The floor around the central counter is green**, keeping its plank detail and its light and shadow pattern, up to
  the rectangle's ragged block edges. So the floor reads the new exports `NormalizedAverageColor0_91` and
  `DirectionalMaxComponent0_91`, and the clones' data loads: the directional clone gives the usual pools of light.
  Nothing shows blue.
- **The rest looks normal:** the other half behind the brick partition is orange wood, and the rugs, the counter and
  the pool table are unchanged.
- **Gate C6 passes for textures.** The appending layout is the growing writer's layout from here. Next for L4: a new
  actor and its components (a copy as a real piece of the map), with its own baked lightmap.

## Run 2: a lamp post copied as a new actor of the map (built 7 November)

The first copy made in the map itself, not spawned by a patch. Tool:
[`native_copy.py`](../../tools/bake/native_copy.py).

**How a placed piece is stored** (the bar's lamp post `XComLevelActor_37` and dumpster `XComDestructibleActor_294`):
- The actor export holds tagged properties only: its mesh component (`StaticMeshComponent`, `CollisionComponent`),
  `Location`, `Rotation`, and for a destructible its light environment and `DestroyedEvents` (structs naming its
  damage actions). Its data starts with a state frame and a net index.
- Under it: the mesh component (properties, then its LOD records: shadow maps, lightmap), the component's
  `ShadowMap2D`s, and for a destructible the light environment, the damage actions and their cues.
- Their archetypes (`ARC_ParkingLotLightpost_Half` and its `StaticMeshComponent0`) are exports of the map, outside
  the level, shared by every placed lamp post.
- Outside the actor, only the Level refers to it: its actor list, the Level's first native field (owner, count
  1,537, actors). A dumpster is also in a building visibility group (`XComVisGroupData_5`).
- The Level export (405,683 bytes) holds no absolute offsets, so it can move. Its one empty slot, index 1, is the
  slot UE3 keeps for the default brush, so it isn't used.

**The copy:**
- The actor and everything under it are cloned as new exports: `XComLevelActor_469` (14,052), its
  `StaticMeshComponent_882` (14,053, under the new actor) and `ShadowMap2D_4506` (14,054, under the new component).
- References among them are remapped: the actor's `StaticMeshComponent` and `CollisionComponent`, and the
  component's shadow map.
- The copy stands at (−1155, −1874.4), midway between the lamp posts at x −1779 and −531, in the row along the
  bushes at the map's edge by where the squad lands.
- The new actor gets net index 7,578, and the package's net object count goes to 7,579. The component's
  `VisibilityId` is −1, so precomputed visibility made for the original's place doesn't cull it.
- The Level is relocated with 1,538 actors. Its data after the list is unchanged.
- The copy still reads the original's lightmap and moon shadow map: it is lit as if it stood at the original's place.
  Its own bake is the next run. It has no tiles either, so it gives no cover and can be walked through; the editor's
  build will seed and rebuild them, as for patch copies.

**Checked offline:** the grown map reads back with the new actor and its children, the new place and rotation, the
Level's list ending with it, and the original untouched. Tests:
[`test_native_copy.py`](../../tools/bake/tests/test_native_copy.py) covers the reference walker on a dumpster
(including its damage actions) and a cloned lamp post.

**What to look at** (a new campaign; the first mission is the bar):
1. **The mission loads.**
2. **The row of lamp posts along the bushes**, at the map's edge near where the squad lands: a new lamp post midway
   between two of them, standing as they do. It should be lit like the others (from the original's lightmap, so a
   little off is expected), not black and not missing.
3. **The original lamp post** (of the two either side of the new one, the one nearer the squad's landing place)
   unchanged.
4. If possible, a save and a reload: the new lamp post still there.

**Result (7 November, 13:47): passed.** The lamp post looks good. The shots
(`<lab>\looks\look-134712.png` from above, `look-134730.png` along the row) show the new post midway between
the two originals, standing as they do. Its mesh is lit like theirs and the originals are unchanged. A save and
reload was not reported.

What it lacks, as expected: the pool of warm light on the pavement. The originals' pools come from a separate
light actor, not the post. Above `XComLevelActor_37` hangs `SpotLight_53`, 413 units up: a static spotlight
(brightness 1.5, radius 1,270, cone 10–70°, warm colour) baked into the pavement's lightmap. The copy is the post
alone, so it brings no light. Giving a copied lamp its light is step L6 (lights in the editor): the light copied
with the post and baked into the receivers around it.

So a new actor in the map works: the Level's list, a fresh net index and new exports are enough for the game to load
and draw it. Next (L4): the copy's own lightmap and moon shadow map, relit for where it stands.

## Run 3: the copied lamp post baked for where it stands (built 7 November)

The same copy as run 2 (`XComLevelActor_37` as `XComLevelActor_469`, midway to the next lamp post), now with
lighting of its own: `python -B tools/bake/native_copy.py URB_Bar.upk <lab>\bake-fixtures\native2
URB_BarNative2 --actor XComLevelActor_37 --at -1155 -1874.4 0 --bake --cache Lighting_7011`. It took under a minute.

**The copy** (`native_copy.py --bake`):
- Its three lighting textures are cloned as new exports, and the copy reads them. Those are its lightmap's two
  (`NormalizedAverageColor1_21` and `DirectionalMaxComponent1_21`, a 1,024 × 512 atlas in `Lighting.tfc`) and its
  moon shadow map's (`ShadowMapTexture2D_335`). The clones start as the original's bake.
- Its lightmap lists one more light, `SpotLight_17`, the next lamp post's spotlight. The original's lightmap
  lists only its own spotlight, `SpotLight_53`. Midway, both are about 620 units away, and `SpotLight_17`'s cone
  reaches the copy (unshadowed peak 0.108). `SpotLight_45` is within range but its cone misses (peak 0), so it is
  left out. The guid list sits inside the copy's component record; a texture lightmap's record holds no offsets,
  so it can grow.

**The relight** (relight.py `--native-copy XComLevelActor_469=XComLevelActor_37 --receivers-near 600`, on the
grown map). The scene before the edit leaves the copy out.
- **The copy's lightmap** goes from our light on the original where it stands (its own spotlight beside the lamp
  head) to ours on the copy where it stands (both spotlights, from the side). 1,988 of 2,460 texels changed.
  - The brightest texels at the original, on the lamp head right beside its own light, come out much darker (the
    test checks under 0.7 of before). That is right for a lamp without its light (step L6).
  - The lower pole comes out darker too. The likely cause is the bushes beside the copy's place: our model shadows
    foliage as solid (masked materials' holes are step L5), so that part may be darker than Lightmass would make it.
    Not yet confirmed.
- **The copy's moon shadow map**: 86 texels darker, from the original's place to the copy's.
- **The receivers around it** take the copy's shadows. 46 lie within 600 units, the quick reach test keeps 25, and
  the edit changes 5 of them:
  - the pavement (`XComLevelActor_21`, 1,184 texels: a dark patch under the copy's base, which the base mostly
    covers);
  - the road (`XComLevelActor_143`, 382);
  - a bush (`XComDestructibleActor_213`, 32);
  - the original lamp post (8);
  - a planter (`XComLevelActor_71`, 4).
  Two of them also have their moon shadow maps changed: the pavement (665 texels) and the bush (113).

**Checked offline:**
- The variant reads back with the copy pointing at its cloned textures, now in the variant cache
  `Lighting_7011`. The clones matched the original atlas before the relight. After it, they differ only inside the
  copy's rectangle (its gutter texels filled from their neighbours, as for every relit receiver).
- The copy's lightmap lists 2 lights. The original still reads its own atlas.
- New test: the copy with its own lighting in
  [`test_native_copy.py`](../../tools/bake/tests/test_native_copy.py). It covers the cloned textures, the added
  light, the relight's report (source lights 1, added `SpotLight_17`) and the dark lamp head, and the copy's moon
  shadow map.
- Deployed to the test slot as `URB_BarNative2` with `Lighting_7011.tfc`; both lab files match the build.

**What to look at** (a new campaign; the first mission is the bar), at the same three lamp posts as run 2:
1. **The mission loads.**
2. **The copy** (the middle lamp post): lit from both sides now, by the spotlights of the lamp posts either side of
   it. Its lamp head is darker underneath than the other two (it has no light of its own), and its pole is likely a
   little darker low down, near the bushes. It should not be black, flat or blotchy.
3. **The pavement around its base**: no dark halo or square showing beyond the base.
4. **The two originals** unchanged.
5. A save and a reload: the copy still there and lit the same.

**Result (7 November, 14:12): passed for the lighting; the copy isn't in the tiles.** Everything seems
fine, a save and reload included. The shots (`<lab>\looks\look-141243.png`, `look-141305.png`) show the copy
lit like its neighbours from the side, its head darker underneath, no mark around its base, the originals as they
were.

One issue: a soldier could walk into the new lamp post. In `look-141243.png` the move cursor stands on
the copy's base. The tiles (cover, movement, line of sight) are baked into the map, and nothing in it covers the
copy: findings register F-57. Run 4 adds them.

## Run 4: the copied lamp post in the tiles (built 7 November)

Run 3's copy again, now with its tiles (F-57): `python -B tools/bake/native_copy.py URB_Bar.upk
<lab>\bake-fixtures\native3 URB_BarNative3 --actor XComLevelActor_37 --at -1155 -1874.4 0 --bake --cache
Lighting_7012`. Tiles are on by default; `--no-tiles` leaves them out.

**What the battle rebuilds.** Once the level and its streaming levels have loaded, `XGBattle` calls
`DoWorldDataRebuild`, and waits for it to finish before play starts. A saved game's load does too (state
`RebuildingWorldData`). It rebuilds the tiles within each `XComRebuildWorldDataVolume`'s bounds, the radar arrays and
the Meld containers; nothing else. The bar has no such volume. And above the ground the rebuild re-checks only tiles
whose baked flags have one of the low 12 bits (F-29).

**What the bake marks for a lamp post.** At the original post (tile 23, 0):
- the tile's own column is marked at every level from 0 to 6 (low bits 0x6A at the ground, 0x2A to 0x4A above);
- the level above its top (7) has a bit of its own (0x20);
- its neighbours carry direction bits toward it at every level (0x4 on the tile at x − 1, 0x2 at x + 1, 0x8 at y + 1).

The copy's tiles had nothing above the ground, and nor did the tiles around them.

**What run 4 adds** (`native_copy.add_tiles`):
- **Seeds:** bit 0x1 on the 84 tiles above the ground that the copy's box crosses, with a quarter tile margin as
  `seed_map.py` plans a copy. That is tiles 16–17 × 0–1, plus a ring of one tile and one level above: tiles 15–18 ×
  0–2, levels 1–7. None had low bits before. The seeds are in-place edits of the map's world data
  (`seed_tiles_under`).
- **A rebuild volume:** `XComRebuildWorldDataVolume_0`, over those tiles plus the plan's 8 units: x −1,352 to −952,
  y −1,928 to −1,624, z −8 to 520. Its rebuild reaches 364 units from the centre, in x and y and in z.
  - It is a clone of the bar's `TriggerVolume_0` (its actor and brush component). Both still point at that volume's
    brush model.
  - It is retyped to `XComGame.XComRebuildWorldDataVolume`. The class, its default object and that object's
    `BrushComponent0` are three new imports, under the map's XComGame package export (the cooked maps hold their
    XComGame class imports there).
  - It is placed and scaled with a new `DrawScale3D`. Its `Tag` is set to the class name.
- The Level's actor list gains both new actors: the copy and the volume.
- [`package_grow.py`](../../tools/upk/package_grow.py) now adds imports: a new import table after the export data,
  the old entries first, so no import index changes. With new names it also writes a new name table. Neither had
  been tried in the game before this run.

The lighting is run 3's, unchanged: the same texels, shadow maps and receivers.

**Checked offline:**
- The variant reads back with the volume of the right class and archetype, over the intended box. Its brush
  component reads its new template, and the 3 imports are there. All 84 seeds are set. The Level's list ends with
  the copy and the volume, and the copy reads its own lighting textures.
- Of the original map's exports, all but the Level stay where they were.
- New tests: [`test_native_copy.py`](../../tools/bake/tests/test_native_copy.py) covers the copy's tiles (grid,
  seeds, volume, Level list). [`test_package_grow.py`](../../tools/upk/tests/test_package_grow.py) covers a new
  import.
- Deployed to the test slot as `URB_BarNative3` with `Lighting_7012.tfc`; both lab files match the build.

**Not known until the game check:**
- whether the game takes the new import and name tables (gate C6 covered only exports);
- whether the rebuild marks the copy's tiles as the bake marks the original's.

The post stands right on a tile edge (x −1,155; the edge is at −1,152), so it may block both tiles it straddles.

**What to look at** (a new campaign; the first mission is the bar):
1. **The mission loads.** A crash or a hang at load most likely means the new tables (imports and names).
2. **The copy blocks movement.** Hovering the move cursor over the copy's base should show no move there, and a
   path past it goes around. Same as the originals: try one of them for comparison.
3. **Cover beside it.** A soldier next to the copy should show the same cover icon as next to an original, if the
   originals give any.
4. **The rest of the street as before:** paths along the pavement and across the road near the copy.
5. A save and a reload: the copy still blocks.

**Result (7 November, 14:30 and 14:32): the game hung while loading the mission, twice.** The game
crashes before loading the first mission. Windows logged both as "stopped responding" (AppHang), each about
10 seconds after the log's last write. The log stops where the mission load began (the game writes it in 120 KB
blocks, T-06), and no crash dump was written.

The cause found offline (findings register T-14): the growing writer cut its appended data into 1 MB compressed
chunks wherever the cut fell. In run 4 the cut landed inside the new export table, splitting one entry's 4-byte
field (bytes 29,540,181–29,540,185 across the chunk boundary at 29,540,182). The cooked maps never do this: in
URB_Bar, no export's data and no table entry crosses a chunk boundary. In runs 1 to 3 the cut also fell inside the
export table, but between fields, by chance. The game's loader serves a read only from one chunk, and a read across
two is the likely hang.

## Run 4b: run 4 with chunks cut only where an item starts (built 7 November)

The same copy, lighting and tiles as run 4, from the fixed writer, as `URB_BarNative4` with `Lighting_7013.tfc`.
- [`package_grow.py`](../../tools/upk/package_grow.py) cuts its appended chunks only where an export's data or a
  table starts (`chunk_cuts`). An item bigger than a chunk gets one to itself.
  - The write check now refuses a package in which any export's data, or the name, import or export table or the
    depends map, crosses a chunk boundary.
  - Checked field by field on every package so far: none crosses one in URB_Bar, runs 1–3 or run 4b; run 4 had the
    one.
- The rebuild volume's archetype is left empty, as the template's is and as the game's own rebuild volumes have it
  (Firaxis's DLC1 Confounding Light stream has six; the two read have no archetype, no `DrawScale3D` and a brush
  model each of their own). Run 4 had pointed it at the class default object, which should mean the same.
  - 109 cooked packages place `XComRebuildWorldDataVolume`, among them `patch_bar`, which this slot streams.
- The variant reads back as run 4's did:
  - the copy's own lighting (cache `Lighting_7013`);
  - the volume over x −1,352 to −952, y −1,928 to −1,624, z −8 to 520;
  - all 84 seeds, the 3 imports, and both actors in the Level's list.
- The lab wrapper now passes `-forcelogflush` to the lab copy (a line `args=-forcelogflush` in its marker,
  `tools/lab/XComLabWrapper.cs`). The game writes its log line by line, so a hang keeps it.
- Deployed to the test slot; both lab files match the build.

**Not proven:** that the split field was the only cause. Run 4b also changes the archetype. If it loads, the
volume, seeds and tables work; if it hangs again, the flushed log shows where.

**What to look at:** run 4's list (a new campaign; the first mission is the bar).

**Result (7 November, 15:22): passed.**
- The mission loads, so the moved name and import tables are taken, and so is the retyped volume.
- In `<lab>\looks\look-152255.png` the move cursor beside the copy shows a cover shield, so the rebuild
  put the copy in the tiles.
- The log, flushed line by line now, is complete. It shows the volume and the copy among the level's actors, and no
  error about either.
- It also shows six errors at load, `duplicate NetIndex`. Every clone except the two actors kept its original's net
  index: the copy's component, its shadow map, the three cloned textures, and the volume's brush component. Run 3's
  log has the same errors (for its five clones), at load and again through its save and reload. The game carries
  on regardless. Findings register T-15; run 5 gives every clone a fresh index.

## Run 5: the lamp post and a dumpster, every clone with a fresh net index (built 7 November)

`python -B tools/bake/native_copy.py URB_Bar.upk <lab>\bake-fixtures\native5 URB_BarNative5 --copy
XComLevelActor_37 -1155 -1874.4 0 --copy XComDestructibleActor_294 -776 -1239 0 -15656 --bake --cache
Lighting_7014`.

**What is new:**
- **Several copies in one variant.** `native_copy.py` takes `--copy ACTOR X Y Z [YAW]` as often as wanted, which the
  editor's Build will need. Seeds already made for one copy count as marked for the next.
- **A destructible copied natively** (the baker design's section 6, damage). The dumpster `XComDestructibleActor_294`
  is copied as `XComDestructibleActor_528`. It is parked in the empty car-park bay between the sedan
  (`XComDestructibleActor_37`) and the SUV (`XComDestructibleActor_36`), on the bay's lines, turned 90° from the
  original's facing.
  - The copy brings its whole subtree: its light environment, mesh component and two shadow maps, and its damage
    actions. Those are two effect cues, a sound cue and the mesh swap, with their cues, remapped to the clones.
  - So it should take damage, swap its mesh and play its effects as the original does. Whatever the original does
    for lighting once damaged, the copy does too.
- **Fresh net indices** (T-15). Every clone whose original has a net index above 0 gets the package's next.
  - In URB_Bar, 1,948 objects share index 0 and the game takes none of them for a duplicate; the rest are unique and
    below the count (one dominant light component has 12,804).
  - The count goes from 7,578 to 7,598 for the two copies, their textures and their volumes.
  - A clone inside a forced-export package (which counts its own) is refused.

**The bake:**
- 72 receivers lie within 600 units of the two copies; the quick test keeps 38, and 19 components change.
- **The dumpster:** 4,505 of 5,758 texels changed, and its lightmap adds `SpotLight_53` (peak 0.077).
  - Its original, by the bar (x −1,539, y 1,719), has a much warmer bake. In the bay its relit faces are bluer and
    darker (median flat light 0.385 → 0.322).
  - Some of its faces show grain at that lower level.
  - Its moon shadow map changes on 3,469 texels, about half darker and half lighter.
- **The car park around it** takes its shadows: the asphalt (`XComLevelActor_242`, 3,693 texels, and its shadow map
  1,613), the two cars (794 and 505), the wheel stops and the bay lines.
- **The lamp post:** as in run 3.

**Tiles:** the dumpster's cross tiles 18–22 × 4–9, levels 1–3. 65 were seeded; 25 already had marks, most likely
from the cars beside it. It has its own rebuild volume (`XComRebuildWorldDataVolume_1`, reach 409).

**Checked offline:**
- No export's data or table crosses a chunk boundary.
- The only repeated net index is the original's 0 group.
- Both copies' seeds are set, and each has its volume. The Level's list ends with the two copies and their volumes.
- [`test_native_copy.py`](../../tools/bake/tests/test_native_copy.py) now checks that a cloned lamp post's
  clones take fresh net indices, from the count up.
- Deployed to the test slot as `URB_BarNative5` with `Lighting_7014.tfc`; both lab files match the build.

**What to look at** (a new campaign; the first mission is the bar):
1. **The mission loads;** the lamp post copy as in run 4b (lit, blocks, cover).
2. **The dumpster in the car park,** in the bay between the sedan and the SUV in the row nearest the pavement:
   - lit like the cars around it, not black or blotchy (expect it darker and bluer than the original dumpster by
     the bar);
   - blocks movement, and gives cover beside it.
3. **Damage it:** shoot it or throw a grenade at it. It should break as a dumpster does elsewhere in the map, with
   no black or bright patches once broken, and its cover should change as a broken one's does.
4. A save and a reload.

The flushed log will show whether the duplicate net-index errors are gone.

**Result (7 November, 15:51): passed.**
- The lab's HE and AP grenades had been raised for this test: damage 30, environment damage
  500, radius 288. That is a lab config change, outside the repository.
- `<lab>\looks\look-155113.png`: the dumpster stands in its bay between the SUV and the blue sedan, lit like
  the cars.
- `look-155150.png` and `look-155212.png`, after the grenade: it has swapped to its broken mesh (lid gone, lit
  evenly, no black or bright patches). The cars beside it burn, and the move grid crosses its bay.
- **The log:** the cloned textures, shadow maps, damage actions and cues no longer share their originals' net
  indices.
  - Five components still did: both copies' mesh components, the dumpster's light environment, and both volumes'
    brush components.
  - A component's data starts with its template owner class, an empty reference (0), and the net index follows it.
    The writer read that 0, took it for an unregistered object, and skipped the clone.
  - Fixed after the run (T-15): the net index is taken as the 4 bytes before the tagged properties. That holds for
    actors (after their state frame), for components, and for plain objects.
  - A two-copy build now gives every clone a fresh index: 7,578 to 7,596 for the two actors, their components,
    shadow maps, damage actions, cues and volumes. No index in the map's space repeats besides the 0 group.
  - The test had missed it for the same reason; it now reads the index from the right place.

## Run 6: the editor's Build makes a project's copies natively (built 7 November)

Until now `native_copy.py` was run by hand. Run 6 is the editor's Build doing it for a saved project: the
[EXP-13](EXP-13-destructible-props.md) project `EXP-13 destructible props` (revision 1: 7 added destructible props,
1 moved, 2 deleted), built from the editor's projects folder with
[`build.py`](../../tools/editor/build.py) as the Project menu's Build runs it.

**What the Build does now:**
- **Compile, split** (`compiler.native_split`): the copies of plain and destructible pieces in no break group are
  made in the variant map. Here that is all 8: the moved dumpster's copy and the 7 added props. The patch keeps the
  exact hider for the 3 hidden pieces (the moved dumpster, the deleted dumpster and the fence section), and no copier.
  A collectible's copy or a group that breaks together would stay the copier's.
- **Patch:** the hider alone, built and cooked in 30 s (UDK, as before).
- **Light:** `native_copy.py --bake --copies native-copies.json --edit-spec <the patch's spec>` on the pristine base
  map: each copy a new actor with its own lightmap and shadow-map textures, a fresh name and net indices, its tile
  seeds and a rebuild volume; then relight.py with the 8 copies and the 3 hides together.
  - The grown map reads the install's texture caches through `tfc-folder.txt` beside it: the builds folder is on
    another drive than the install, so the 1.4 GB `Lighting.tfc` could only have been copied.
  - Copies may turn on any axis now: a piece standing at rotation 0 saves no `Rotation`, so the copy's is added to
    its properties (228 of the bar's pieces stand so; the old code refused them). The knocked-over trash can is
    rolled 90°.
- **Seeds:** no seed plan from the patch; the copies seeded their own tiles.
- About 2.5 minutes in all.

**The build** (`URB_Bar_EXP13Destr_d3e1`, cache `Lighting_4963704`):
- The copies are `XComDestructibleActor_528` to `_535`, each followed in the Level's list by its
  `XComRebuildWorldDataVolume`.
- 40 components relit, 57 reached but unchanged, 20 shadow maps. The 3 hidden pieces are left out of the scene
  after the edit (they cast no shadow there) and are not relit.
- Each copy's lightmap went from its original's light where it stands to its own where it stands (texels changed:
  77–81% for the dumpsters, 59–79% for the small props). Five of them list extra lights that reach only their new
  place (the keg adds `PointLight_8`).
- Tiles: 3 to 63 seeded per copy, the rest already marked by the map's own pieces.

**Checked offline:**
- The variant's map space repeats no net index besides the 0 group (count 7,578 → 7,703). Nine of the map's own
  Polys read −1 there, as in the base map.
- The Level's list ends with the 8 copies and their 8 volumes.
- Every copy's lightmap textures are in the variant cache.
- Unit tests: the compiler's split, the Build's stages for each case (copies and hides; copies alone, no patch;
  hides alone; the copier's copies; nothing to build), a copy turned on every axis of a piece that saves no
  Rotation, and the lighting test reading the cache through the link file.

**What to look at** (a new campaign; the first mission is the bar), as EXP-13's checks:
1. **The map loads.**
2. **The 8 copies stand as posed,** in the street where EXP-13's copies stood: two dumpsters (one turned 45°), an
   upright trash can and one lying on its side, a box stack, a keg and a trash bag. They are lit like the map's own
   pieces around them, with no black or bright patches, and cast shadows.
3. **The fenced lot:** the moved dumpster turned and one tile on, the deleted dumpster gone, and the gap in the fence
   where the section was, with its neighbours standing.
4. **Cover:** high cover beside the dumpsters, low or none beside the small props; the deleted dumpster's tiles and
   the fence gap can be walked through.
5. **Damage:** a copy shot or blown up breaks as the map's own do, and its cover goes.
6. A save and a reload.

The flushed log should show no duplicate net index for any clone (T-15's component fix, from run 5).

**Result (7 November, 16:31): passed.** Installed by the lab watcher at 16:22.
- `<lab>\looks\look-162915.png`, `look-162938.png` and `look-162945.png`, before any damage:
  - all the copies stand as posed: the keg stack and the box stack beside the moving van, the trash bag and the
    upright trash can on the asphalt, the trash can on its side by the blue sedan, and the two dumpsters, one turned
    45°;
  - the move cursor shows cover shields along them;
  - they are lit as the map's pieces around them, with no black or bright patches. The dumpsters are dark: they
    stand in moonlight away from the lamps, as relit (their flat light median went from 0.41 where the original
    stands to 0.24–0.25).
- `look-163040.png`, after the grenades: both dumpsters swapped to their broken meshes (open, lids gone), lit evenly.
  The keg, box stack and trash bag are gone, leaving scorch marks, and the sedan beside them burns.
- `look-163102.png`, after a save and a reload: the same broken
  state.
- The fenced lot isn't in the shots. The log shows the hider hiding 3 of 3 exact targets and rebuilding the tiles
  around them, at the first load and again at the reload.
- **The log:** no net-index error names any object of the variant. The 10 `duplicate NetIndex` lines left are the
  engine's own (camera and checkpoint properties), the same 10 as in logs from 4 November; run 5's session had 20.
  T-15 is fixed in the game. A checkpoint line, "XComWorldDataContainer ... invalid NetIndex 7576", is also in the
  logs of 4 and 6 November, before any native copy: the game's own at a save.
- So the editor's Build makes plain and destructible copies baked for their place. Copies in a group that breaks
  together, and collectibles' copies, still come from the copier and are lit live: the temple's near-black low-cover
  pair (F-56) is such a copy.

## Run 7: the temple project, its groups that break together made in the map (built 7 November)

Run 6 left the groups that break together to the copier, which makes them at load and lights them live: on the
temple, one stacked console pair came out near black (F-56). Run 7 makes those groups in the map too and links them
with the game's own link.

**The link:** `AffectedChildren`, an array on every destructible. When a piece enters a damage state (damaged,
destroyed), `SyncChildStates` passes that state to each piece it lists. The exe's native code (reached through the
class's vtable, slot 0x3FC, at 0x00ABC400) asks each child `IsInState(NewState)` first and calls `GotoState` without
forced events, so links may go both ways: a chain stops at a piece already in the state. Each member of a group lists
every other member; the map's own pieces left in place get the others added to their own list.

A copy also no longer keeps its original's children: over 30 of the bar's destructibles list parts (a pool table its
top, vans their doors), which a copy would have broken along with itself. A part copied in the same build is linked
to its copy instead.

**The project:** `temple_improved`, revision 7, as in EXP-14 runs 14 and 15: the two laser barriers
(`XComDestructibleActor_9_copy4` and `_copy5`) in place of two deleted low covers, and a low-cover pair at each place
on the raised walk, two consoles (`XComDestructibleActor_28`) laid on their sides and stacked back to back
(`_copy14`/`_copy15` in group 2, `_copy16`/`_copy17` in group 1).

**The build** (16:42, `TempleShip_TempleIm_2001-20261107-164201`, under 4 minutes; installed by the lab watcher at
16:45):
- Compile and split: all 6 copies native, in 2 groups that break together; the patch is the hider of the 2 deleted
  low covers alone (no copier). No seed plan: the copies seeded their own tiles.
- The copies are `XComDestructibleActor_822` to `_827`. Each console of a pair lists the other in `AffectedChildren`
  (822 and 823, 824 and 825); the barriers list nothing. The consoles keep their full rotations (rolled −16384, yaws
  32768 and 0).
- **The relight:** 13 components relit, 164 reached but unchanged, 145 left by the quick test.
  - The south pair (822 and 823, F-56's place) bakes darker than its source console where it stands (flat light
    median 0.050 → 0.023 and 0.034), as dim as the block it lies on (`XComLevelActor_1042` 0.025, `_1043` 0.022): the
    place is dim, and the pair now takes its light, bounce included, instead of the live light's black.
  - The north pair: 0.044 and 0.050. The barriers, moved from a dim place to the bright flip floors: 0.097 → 0.46
    and 0.37, as the floors (0.43).
  - Each copy's lightmap lists the lights of its new place (3 to 11 added).
- Checked offline: no net index repeats in the map's space (count 16,026 → 16,096); the Level's list ends with the 6
  copies and their volumes; every copy's lightmap is in the variant cache.

**What to look at** (a new campaign; the first mission is Temple, after the arrival cinematic), as EXP-14 run 15:
1. **The map loads.**
2. **Each laser barrier**, either side of the first hall past the doorways: lit like the map's own barriers, its
   shadow on the floor and none left of the low cover it replaced.
3. **Each low-cover pair** on its raised block on the centre line: both consoles lit like the walk around them. The
   pair that came out near black in run 15 (F-56) should now be lit as its place is: it was baked there, bounce
   included.
4. **Break together:** grenade one console of a pair. Both should go to the same state (damaged, then destroyed), as
   in EXP-14 run 14, and the pair's cover goes when they're destroyed.
5. A save and a reload.

**Result (7 November, 16:59): passed.** The consoles exploded together, though the
grenade hit only one.
- `<lab>\looks\look-165755.png`: a pair standing on its block, lit, its own red lights showing, not black.
- `look-165927.png`, after the grenade: the pair's wreck stands upright with cover shields around it. It also blocks
  the tile beside it. That is the wreck's own shape (the consoles stand on their sides to make a 1×1 cover
  block), nothing to fix.
- The log: the hider hid 2 of 2 exact targets. Of the 12 net-index lines, 10 are the engine's own and the other 2
  name two of Temple's own psionics textures, in its logs from 6 November too; none names a clone.
- So the groups that break together work as the game's own linked pieces, made in the map, and F-56's pair is lit
  for its place. Step L4 is done for every copy but a collectible's.

## Run 8: the pool table moved, its originals taken out of the map (built 7 November)

Up to run 7 the Build's patch still did two things: its exact hider hid the pieces an edit deletes or moves, and its
copier made collectibles' copies at load (a copy made in the map would be loot, and the copier's isn't).
Collectibles' copies are to count as loot by default. So run 8 takes both into the map, and an M1 project's Build
makes no patch and runs no UDK.

**A hidden piece** (`native_copy.hide_pieces`):
- Its slot in the Level's actor list is set to 0, as a level designer's delete leaves it. The level loads, ticks
  and attaches its components from that list, and the loot count walks it (`XComCollectible.CollectCollectibles`,
  native, through the actor iterator), so a hidden collectible no longer counts.
- It's taken out of every destructible's `AffectedChildren`, so nothing breaks it along with itself.
- An `XComRebuildWorldDataVolume` over its tiles and a ring of one rebuilds them at load: the bake marked the piece
  there, and the rebuild finds nothing. No seeds are needed, since those tiles already carry the bake's marks.
- The relight removes it as a caster (`relight.py --remove-caster`), as it did for the hider.
- Still referring to it: the building's floor caches (`Floors[].m_aCachedActors`) and a visibility group
  (`XComVisGroupData`) list it, and its export stays in the package. An actor outside the list is loaded (the
  references load it) but never attached, and the floor code acts only on attached components (native-code notes),
  so those references should stay dormant. F-58 tracks it until the game shows it.

**A collectible's copy** is made in the map like any destructible's, so it's a collectible in the Level's list and
counts as its original does (intact as the item, damaged as the damaged item). The editor's report says so for each
edit: a copy counts as loot too, a moved one still counts once, a deleted one no longer counts. An option to mark a
copy as not loot is for later.

**The project:** `EXP-17 pool table moved` (`7a1f0e17-1010-4d0e-9b6c-5e4f3a2b1c10`, revision 1), as in EXP-17 run
10: the pool table (`XComDestructibleActor_491`) moves from beside the street windows to the open floor under the
ceiling spot `SpotLight_3`, by the island counter's corner nearest the street windows, turned a quarter turn; the
glass on its edge (`_45`) moves with it. The table lists the glass in `AffectedChildren`, so breaking the table
breaks the glass.

**The build** (17:16, `URB_Bar_EXP17Move_7a1f-20261107-171649`, 4 minutes; installed by the lab watcher at 17:20):
- Compile and split: both copies native, both originals hidden natively; no patch, so no patchtool, UDK or cook.
- The copies are `XComDestructibleActor_528` (the glass) and `_529` (the table). The table's copy lists the glass's
  copy in `AffectedChildren`.
- The originals: out of the Level's list (`_45` export 12078, `_491` export 12143), each with a rebuild volume
  (14074, 14076) in it, and listed by no destructible.
- **The relight:** 109 components written, 98 reached but unchanged, the 2 originals skipped as removed; the quick
  test kept 207 of 420.
- Checked offline: no net index repeats in the map's space (6,526 indices).

**What to look at** (the test slot plays `URB_Bar_EXP17Move_7a1f`, a fresh start):
1. **The map loads.**
2. **The old place** beside the street windows: no table and no glass, no cover shield there, and a soldier can
   walk through where the table stood. The rug there is evenly lit, as in EXP-17 run 9.
3. **The new place** under the ceiling spot by the island counter: the table stands lit like the room, its shadow
   baked on the floor and the rug's edge, and it gives cover and blocks movement.
4. **Break it:** a grenade on the table. The glass on its edge should break with it (the assembly link).
5. **The building cutaway:** with a soldier inside the bar, nothing ghostly shows at either place when the roof and
   upper floor cut away (F-58).
6. A save and a reload: the old place stays empty, the new table stays where it is.

**Result (7 November, 18:04): passed.**
- `<lab>\looks\look-180256.png`: the table at its new place by the island counter, lit like the room, and the
  floor beside the street windows clear where it stood.
- `look-180306.png`: a move path running through the table's old place to the street windows; cover shields only at
  the wall.
- `look-180314.png`: the table at its new place with cover shields all round it.
- `look-180353.png`, after a grenade: the table's wreck where it stood, and fires out in the street.
- `look-180415.png`, after a save and reload (a note typed in the console): the same.
- The log: the 10 `duplicate NetIndex` lines are the engine's own, as in every log since run 6; none names an object
  of the map. Nothing about the hidden pieces.
- So the Build's native hides work in the game: the pieces are gone, their tiles open, and the cutaway shows no
  ghost (F-58 verified). Collectibles' copies made in the map still need a loot check at a mission's end.
- **The dropship intro didn't play.** F-45 again: the intro's Kismet in
  `CIN_DropshipIntros` picks the landing by the exact map name. patchtool's `XComMapEdIntro` renamed `URB_Bar`'s entry
  to the variant's name at load, but only in a patch shipped with `map.shipAs`; the Build's patch is compiled
  `--stream-only`, without it. So no Build variant has had the intro, with a patch or without. Run 9 gives the variant
  an intro of its own (see F-45).

## Run 9: the pool table again, with its own landing intro (passed 7 November)

Run 8 had no dropship intro (F-45). The intro's Kismet is in the streamed `CIN_DropshipIntros`: XGBattle fires
`SeqEvent_OnTacticalIntro` with the map's name, and Switch String nodes pick the landing by that exact name. A variant's
new name matches none, so no landing plays. patchtool's `XComMapEdIntro` renamed `URB_Bar`'s entry at load (EXP-08 run
1c), but only in a patch shipped with `map.shipAs`. The Build compiles its patch with `--stream-only`, which has no
`shipAs`, so no Build variant ever had the intro, run 6's and the EXP-17 relit fixtures included. It was noticed in
run 8.

**The fix, in the data** ([`intro_copy.py`](../../tools/bake/intro_copy.py)):
- The Build copies the base record's intro stream as `CIN_DropshipIntros_<variant>.upk`.
- The copy is the same except for one entry: `URB_Bar`'s in `SeqCond_SwitchString_8` (entry 3 of 36) names the
  variant. Each entry is a small struct whose `StringName` holds the name.
- The variant's record streams the copy in place of the original (slot 0); the lab install does the same
  (`replaceStreams` in the manifest, `deploy_fixture.plan_maps(replace=...)`).
- The name keeps `CIN_DropshipIntros` at its start. The exe recognises the intro streams by that substring: three
  places in the exe copy (0x4C5944, 0x64BAB6, 0x78B210) look for `CIN_DropshipIntros` (and `CIN_FastropeIntros`) with
  a substring search, never an equality.
- An intro with no landing of its own for the base map gets no copy, and the variant streams it as the base does.
- The copy is about 6 MB, per variant.

**The build:** the same project as run 8 (`7a1f0e17…`, revision 1), from the editor's Build into the builds folder;
the lab watcher installs it.

**What to look at** (a new campaign, the first mission):
1. **The Skyranger lands**: the intro plays as it does on the original bar (the camera, the dropship coming in, the
   squad getting out), then the mission starts.
2. The pool table stands at its new place as in run 8.

**Result: passed.** The lab watcher installed the build at 18:23 (the test slot plays `URB_Bar_EXP17Move_7a1f` with no
patch, streaming `CIN_DropshipIntros_URB_Bar_EXP17Move_7a1f` in place of `CIN_DropshipIntros`). It was played
by hand and the landing intro worked. No screenshots were taken for this run. So a variant's own intro copy
gives it the base map's landing, with no patch and no code in the game: F-45 is verified for the Build.

## Run 10: collectibles' copies as loot (built and installed 7 November, 21:08)

Since run 8 a collectible's copy is made in the map as a collectible, and a deleted one is taken out of the Level's
actor list. The mission's loot comes from `XGBattle.CollectLoot`, which runs at the end of every mission (all but
one council type): `XComCollectible.CollectCollectibles` (native) walks the level's collectibles into the mission's
artifacts. So a copy should count as one more item, and a deleted original as one fewer. Nothing has shown it yet.

Which maps have collectibles (a read-only scan of the LWR install's 786 packages): the UFO maps (power sources,
navigation computers, stasis tanks, surgery bays, food), the two alien bases, `DLC1_3_Gangplank`, `DLC2_3_Furies`,
and Temple Ship, whose 6 are all `eItem_UFOPowerSource` (archetype `UFO_PowerCore.Archetypes.ARC_PowerCore2_COLLECT`).

**The project:** `Loot check` (`da7ea9e7-7f70-49f6-a55d-c7bfbecd5700`, revision 1) on Temple Ship:
- two copies of the power core `XComCollectible_56`, at the two places EXP-14 run 2 put its core copies (readout
  tiles (22, 37, 10) and (22, 25, 10)), made as `XComCollectible_58` and `_59`;
- the map's core `XComCollectible_0`, the middle one of one row of three, deleted (taken out of the Level's list).

The Build took 276 s; the lab watcher installed it at 21:08: the test slot plays `TempleShip_LootChec_da7e` with no
patch. Temple Ship has no landing intro of its own in `CIN_DropshipIntros`, so the variant gets no intro copy.

**What to look at** (a new campaign, the first mission):
1. Leave every power core undamaged: a damaged core counts as a damaged item.
2. End the mission with the console command `killaliens` (with no number; `killaliens 1` leaves one alien alive).
3. **The mission's loot list should show 7 UFO power sources**: the map's 6, one fewer for the deleted core, two
   more for the copies. F9 on that screen.

**Result: not shown; left for the UFO maps.** `killaliens` did not end the mission on Temple Ship: the map is
scripted as the final mission, and its end doesn't come from all aliens dying. No loot screen, no screenshots. The
reasoning above stands for now, lootables taken as fine; the count gets its game check when the
editor takes on UFO maps, whose missions end normally and whose power sources and navigation computers are
collectibles.
