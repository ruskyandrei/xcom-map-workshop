### A copy's lightmaps the size of what it reads, and no folder of a computer in a pack or a build's manifest (F-151; KB-15 out, KB-16)

A baked Build gave every copy a clone of each lightmap and shadow-map texture its source reads, a whole 1,024-texel
atlas for a rectangle of a few dozen texels, and since 0.6.0 the map holds them uncompressed: a reported map pack's
city variant with 166 copies was 336 MB (F-151, KB-15). Now each copy, piece from another map and made piece gets
textures the size of what it reads (smaller built maps plan, `private/plans/done/smaller-built-maps-plan.md`, stages
S0 to S3 and S5; decisions D1 to D6 at their proposals).

- [lightmap_textures.py](../../tools/bake/lightmap_textures.py): `crop_box` (the rectangles a copy reads with the
  writer's one-texel ring, on whole DXT1 blocks, a power of two each way, at least the game's smallest),
  `cropped_texture` (the source's bake over the box, its top mip's blocks or bytes copied as they are, its lower mips
  made from it), `blank_texture`, `moved_record` (a coordinate scale and bias pointed into the box, exact in the
  records' 32-bit floats). Each is a texture as the game's own small ones are inside a map: every mip inline and
  uncompressed, the chain down to one texel with DXT1 sides stored no smaller than 4, MipTailBaseIdx its last mip,
  NeverStream, no cache name (`top_mip_bytes` reads a G8 shadow map's top mip too).
- [native_copy.py](../../tools/bake/native_copy.py): `lighting_boxes` finds each texture's box over every record of
  the copy that reads it (the textures one lightmap record reads share one box; a texture whose records can't move
  exactly is cloned whole); `clone_assembly` makes the cropped textures and rewrites the copy's lightmap records and
  ShadowMap2D coordinates. Pieces from other maps are cropped the same way (the plan said blank: a crop is no larger
  and keeps the home map's bake where the relight writes nothing). A made piece's LOD 0 textures are no longer
  cloned at all where nothing else reads them.
- [frac_walls.py](../../tools/bake/frac_walls.py): a made wall's, floor's or ground's lightmap is textures of its own
  of its rectangle's size with its ring (`own_light`), the rectangle one texel in; its shadow map of the dominant
  light a blank texture of that size (`own_shadow_size`), in place of a clone of a 1,024 field. Its density is its
  donor's, as before, no larger than 1,022 texels a side.
- [relight.py](../../tools/bake/relight.py) and [shadowmaps.py](../../tools/bake/shadowmaps.py): a copy relit from its
  source takes the source's texels in the copy's own layout; the layout check is
  [lightmap_texels.py](../../tools/bake/lightmap_texels.py) `moved_rect` (the same rectangle, moved by whole texels).
- [build.py](../../tools/editor/build.py): a relight that writes no texture cache, or one no texture names, is "its
  lightmaps inside the map, none moved" (`lightingInside` with 0 textures); `lightingInside.held` and a log line say
  what the map holds of lightmaps ([lighting_size.py](../../tools/bake/lighting_size.py) `inside`), with a warning
  from 100 MB (decision D4: the game loads them with the map and keeps them in memory for the battle).
- [lighting_size.py](../../tools/bake/lighting_size.py), new: a map's lighting textures, who reads each, its box and
  what it would weigh at that size (`--list`, `--json`).
- [research/evidence/lighting-texture-survey.py](../../research/evidence/lighting-texture-survey.py), new, with its
  result: the game's 18,906 lightmaps and shadow maps in 138 maps, the small ones' properties and mip chains.
- The folders (KB-16): [folder_scrub.py](../../tools/viewer/folder_scrub.py), new, holds the scrubber the pack export
  used (moved from manager.py) and a guard for folders it was not told of: a drive's or share's path becomes
  `<folder>`, the name after Users or home `<user>`, and the export's answer says so
  ([manager.py](../../tools/viewer/manager.py)). The build folder's own `manifest.json` now names folders by
  placeholders too (`<builds>`, `<projects>`, `<install>`, `<cache>`, `<temp>`, `<home>`); the record with the real
  folders is the work folder's `build-log.json` and what the Build returns (decision D5).
  [profile_build.py](../../tools/bake/profile_build.py) reads `<builds>` as the package's own builds folder.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): rows for the sized lighting textures and the folder scrubber.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-15 out; KB-16 in until a release carries the folder fix (a 0.6.0 pack's
  `packages\<map>\manifest.json` names the maker's folders: delete it from the zip, nothing reads it).
- Release notes: a map built before keeps its size until it is built again, and a pack until it is exported again.

Checked: the bake suite (896 tests; `test_lighting_size` new: the mip chains read off the game's, the box rule,
every record of URB_Bar and of the intro map's non-square atlases moved exactly, sized textures read back by the
audit reader, the writer editing one in place with no cache; `test_native_copy`'s copy with its own lighting reads
its source's texels over its rectangle and ring; `test_frac_walls` on the new layout), the editor's `test_build`
(nothing to move, the size warning, the scrubbed manifest), the viewer's `test_pack_export` (the guard). The reported
project built on main and on this branch: 340.8 MB against 55.8 MB, its lightmaps inside 306 MB against 23.6 MB;
every one of its 166 copies' lightmap rectangles with their ring (332 textures, 1.9 million texels) and shadow maps
(140, 0.9 million texels) the same texel for texel, the map's 137 own lighting textures byte for byte. URB_Bar with
five copies the same way (796,800 and 303,252 texels, 234 textures). build_outputs.py: every package file of its 11
inputs byte for byte as before; the manifests differ by their placeholders, the new tool's hash and, where the
stand-in relight writes no cache, "inside, none moved".

Known gaps: a copy's lower mips are made from its own texels, not the atlas's. Compressed storage was left out
(decision D3).
