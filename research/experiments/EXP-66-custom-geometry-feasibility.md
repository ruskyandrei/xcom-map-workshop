# EXP-66: custom building and terrain geometry, read-only feasibility audit

Date: 16 November 2026. Research only: inspected existing packages and code, reviewed prior gameplay experiments,
and ran the existing cover-block tests. No new visible mesh was built, installed or played.

## Question and result

Can the editor move beyond the original maps' fixed wall lengths, window/door openings and ground shapes?

**Custom static geometry has a credible direct-writer route; fully fracturing custom walls remain a separate
research problem.** The editor already generates hidden box meshes with working collision. Extending that to
visible walls and terrain needs geometry, material, collision and fresh-lighting authoring. It is not merely
unhiding those boxes. This is T-42 in the [findings register](../findings-register.md).

The implementation proposal is kept in the private plans folder, as repository policy requires.

## Reproduction and measurements

Run from the repository, using the configured game or an explicit cooked folder:

```text
python -B research/evidence/custom-geometry-audit.py --output <scratch>/geometry-audit.json
python -B research/evidence/custom-geometry-audit.py --cooked <CookedPCConsole>
python -B tools/run_tests.py bake -k test_cover_blocks
```

The [audit script](../evidence/custom-geometry-audit.py) reads two packages, validates sampled meshes against the
existing native-field layouts, and emits names, counts and package hashes. It writes no game data. The retained
[measurements](../evidence/custom-geometry-audit.json) describe this install, not every release or mod combination.

| Measurement | Result |
| --- | --- |
| Farm slope mesh | `TornEarth.Meshes.SmallscoutRamps`, ordinary `StaticMesh` |
| Render geometry | 1,123 vertices, 1,788 triangles, one LOD, one material section |
| UVs and lightmaps | Two UV channels, `LightMapCoordinateIndex` 1 |
| Collision | BodySetup present, simple line collision, ten convex/box elements, no skipped sphere/capsule elements |
| Native terrain actors in the two packages | No `Terrain` or `Landscape` exports |
| Bar wall samples | Four `FracturedStaticMesh` assets, 30/55/60/77 fragments, two UV channels, vertex colours and 6-7 material sections |
| Bar fragment columns | 1,037 across 70 fracturing actor exports, including exports without columns; this is not a count of placed walls |
| Existing cover-block suite | 36 tests passed, no skips |

Inference: custom ramps, rocks and ground patches can be investigated as ordinary meshes. Implementing a native
Terrain/Landscape system is not a prerequisite for replacing this particular farm slope.

## Existing foundations and their boundaries

- [cover_blocks.py](../../tools/bake/cover_blocks.py) writes a new StaticMesh and BodySetup. Its hidden pieces have
  been played: [EXP-31](EXP-31-cover-blocks.md), F-79/F-80; its floor variant in
  [EXP-32](EXP-32-invisible-floor.md). The writer is box-specific: fixed collision nodes, 24 vertices, 12 triangles,
  one UV channel with overlapping faces, no material binding in its mesh section, and no component texture lightmap.
- [transplant.py](../../tools/bake/transplant.py) brings existing cooked art and dependencies into another map;
  [native_fields.py](../../tools/upk/native_fields.py) maps references in static and fractured meshes. Preserving an
  existing mesh's data is different from generating valid new collision or fracture topology.
- [buildings.py](../../tools/bake/buildings.py) creates building/floor volumes and membership. A newly assembled hut
  has passed roof/wall cutaway and destruction checks using existing pieces: [EXP-44](EXP-44-hut-building.md).
- [relight.py](../../tools/bake/relight.py) has a fresh/absolute lighting calculation, but `prepare_component` requires
  an allocated LOD-0 texture lightmap. A new mesh needs suitable UVs and fresh records/textures before using it.
- Current copy poses in [compiler.py](../../tools/editor/compiler.py) author position and rotation and retain source
  scale. Fracturing copies carry tile columns through rigid grid moves. Neither is an arbitrary wall-resizing tool.

## Important gameplay constraints

A wall opening must be open in the collision, not only in the render mesh. Separate convex pieces around its jambs,
lintel and sill avoid a single hull filling the hole. The game still tests tiled occupancy, headroom and movement;
arbitrary visual dimensions do not guarantee a traversable opening. A working door or vaultable window also needs
the relevant interactive actor and state.

The [cover-build reading](../native/cover-build.md) and F-81/F-83 explain the farm slope: simple collision can sit
above the drawn surface, and floor normals below 0.9848 (about ten degrees of slope) normally skip cover generation.
EXP-32 demonstrates selected flat invisible standing plates as a workaround, not arbitrary terrain qualification.

F-69 records fragment columns, neighbour caches and attached destructibles. The sampled walls also carry native
fragment topology and material sections. Native-style custom destruction requires generating those coherently;
the current rigid-copy code cannot do that merely by changing a mesh's vertices. Whole-panel destruction is an
alternative worth testing, not a demonstrated result of this audit.

## External reference checks

Epic documents UE3 static-mesh import with custom convex collision, multiple UV channels and LODs, including
door/window cutouts. Its September 2011 importer expects FBX 2012. This supports a possible authoring/reference
route, not automatic compatibility with EW's cooked format.
[Epic's UE3 pipeline](https://docs.unrealengine.com/udk/Three/FBXStaticMeshPipeline.html).

The UDK has a fracture tool, but EW's native fragment layout and actor columns require additional handling.
[Epic's Static Mesh Editor](https://docs.unrealengine.com/udk/Three/StaticMeshEditorUserGuide.html).

Reusing installed cooked materials avoids making new shader compilation the first dependency. The Uncooker explains
why recovered materials are not a ready runtime import path, and LWCE documents executable changes to permit custom
material compilation. No executable patch was attempted here.
[Uncooker FAQ](https://github.com/chrishayesmu/XCOM-Uncooker#faqs),
[LWCE notes](https://github.com/chrishayesmu/XCOM-LW-CommunityEdition/blob/master/Notes/exe_patches.md).

The next proof is one visible generated primitive with an existing material and fresh lighting, followed by a
wall aperture and a ground wedge. Rendering, collision, movement, cover, sight, cutaway and persistence must be
checked independently. The present evidence does not qualify a new visible mesh or a general importer in game.
