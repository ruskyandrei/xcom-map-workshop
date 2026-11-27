### Export 46: the map's decals read as the game stores them

The reader and the export of stage D1 of the game-likeness plan. The editor does not draw decals yet; that, and
editing them, is a later stage.

- **The reader**, [decal_records.py](../../tools/upk/decal_records.py) (new). A placed decal's component saves the
  triangles the game clipped it to on each surface it lies on, each surface's part in that surface's own space with the
  component it is. The reader reads them to the component's last byte and refuses what does not fit (F-210). A decal
  takes its frame from its actor: its place, the actor's -X axis its normal. Its size and material are the component's,
  else its archetype's in the package, else Default__DecalComponent's. `coordinates` and `surface_frame` give what the
  game's decal vertex shader makes of a point: its texture coordinates, its blend by the surface's angle, its depth and
  its tangent frame (F-211).
- **The export**, [decals.py](../../tools/viewer/decals.py) (new) and [export.py](../../tools/viewer/export.py)
  (`EXPORT_VERSION` 46). The scene's `decals` (a stream's in its layer) gives each decal:
  - its actor's name, level, place and rotation, whether it is hidden, and whether it is in the level's actor list (a
    Build's clear takes it out with the Pieces part);
  - its frame, its size (width, height, near and far planes, tiling, offsets, rotation, blend range, depth bias) and
    its material;
  - its prefab, and the piece its largest part lies on;
  - a mesh, `decal-<actor>.glb`, of all its parts' triangles in the world, grouped by the piece each part lies on
    (`receivers`: the piece's id and the part's range of the index buffer). The vertices carry the decal's texture
    coordinates, blend and depth in two UV channels, and its tangent frame on the surface.

  The form is in [research/editor-contracts.md](../../research/editor-contracts.md) section 12, and the rows in
  [ARCHITECTURE.md](../../ARCHITECTURE.md) section 2. A piece of another map carries nothing new: the library's piece
  version is unchanged. KNOWN-BUGS.md KB-3's cause names what is still missing.
- **The survey**, [audit_decals.py](../../tools/upk/audit_decals.py) (a research tool), with its evidence in
  [decal-audit-2026-11-27.json](../../research/evidence/decal-audit-2026-11-27.json). It covers the 153 packages the
  map records name (11 s):
  - 3,351 decal components: 3,069 placed, 282 archetypes'. Every one reads to its end.
  - Every saved frame member is its actor's.
  - Every stored vertex of the 3,062 clipped decals lies inside its box and its planes.

  It also slices the 165 decal materials: F-212, what the slice still needs before the page can draw them.
- **Checked**:
  - [test_decal_records.py](../../tools/upk/tests/test_decal_records.py): made-up packages (a receiver read to the
    end, an unclipped decal, refusals, the frame, an archetype's members), the vertex shader's sums, URB_Bar's 38
    decals, and the defaults against Engine.upk.
  - [test_decals.py](../../tools/viewer/tests/test_decals.py): a decal's mesh from two parts; on URB_Bar every
    record and mesh file, and a part on a piece the export lacks left out.
  - Fresh exports of the four maps of track H: URB_Bar 38 decals (4,434 triangles, 0.8 MB of meshes, 0.07 s of a 15 s
    export); CSmallScout_DirtRoad 70 (22,891 triangles, 3.9 MB, 0.25 s); LAbductor_FarmOutskirts 12; AlienBase01 none.
    Their only new diagnostics are the decal materials' fallbacks (F-212).
- **Known gaps**: the texture's direction across a decal (F-211) is the shader's own frame, not yet seen in the game.
  A scaled receiver's blend and depth are worked out in the world, which is not exactly the game's.
