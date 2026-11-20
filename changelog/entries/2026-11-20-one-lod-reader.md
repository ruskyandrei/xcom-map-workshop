### One reader of a mesh component's LOD records and of a bulk record (editor refactor, stage B3)

A mesh component's LOD lighting records (each LOD's shadow maps, its lightmap and its texture slots, and Enemy
Within's two mesh-swap records and their meshes) were read three times, each reader with its own copy of the layout
and of the licensee branch (review finding 52): by `lighting_records` for the bakers, by `lightmap_fields` for the
places the relight writes, and by `native_fields` for the transplant's references and bulk records. Now
[native_fields.py](../../tools/upk/native_fields.py) holds the one reader: `mesh_lods` (the licensee branch, once),
`lod_record`, `lightmap_record`, `object_refs` and `bulk_record`, each value with its place in the package.

- [lighting_records](../../tools/upk/lighting_records.py) (which imports `native_fields` beside it, found as it was
  itself) gives its records from it in the same form and key order
  (`component_record`, `lod_record`, `lightmap`, `refs`, `bulk_meta`), and `component_lods` with the rule that a
  StaticMeshComponent ends after its records; `bulk_meta` keeps its refusal of a negative count or size, which the
  shared reader can't have: a texture's unused mips in a separate file say -1 (40 of the Bar's Texture2D records).
- [lightmap_fields.component_fields](../../tools/bake/lightmap_fields.py) gives its places from it, through
  `component_lods` so that it refuses what `component_record` refuses, as it did by checking its own reading against
  `component_record`'s; that cross-check of one reader with itself is gone.
- `native_fields`' fields of a mesh component come from it, in the order they did; the check that an inline bulk
  record points to its payload stays its own.
- The relight's images now depend on `native_fields` (lighting_records imports it), so it is in the piece cache's key
  (relight.py's `TOOL_FILES`; the bake suite's key test found it missing). With lighting_records.py and
  lightmap_fields.py changed too, a project's next baked Build relights its kept pieces once.
- The checks of the three readers are now each reader's: a vertex-colour flag other than 0 or 1, a colour array whose
  stride or count differs from its header, an unknown lightmap type, an object that is not one, and a vertex
  lightmap's bulk record with a negative count or size are refused wherever a component is read (the transplant's
  reader took a negative inline size as 0 and did not compare a colour array with its header).

Checked: every export of URB_Bar and TempleShip read by the old readers and the new (`component_record`,
`component_fields`, `native_fields.fields`, `measure_common.component_light` over each of the 1,304 and 1,821 mesh
components; `texture_record`, `texture_fields`, `lightmap_textures.bulk_meta_offsets` and `native_fields.fields` over
each of the 935 and 603 textures) gives the same answers and the same refusals, word for word; so does
`native_fields.fields` over every export of both maps (14,051 and 14,137: its other classes' bulk records are
`bulk_record`'s too, and none of them holds a negative inline size). A test on a made-up
component, no install needed ([test_native_fields.py](../../tools/upk/tests/test_native_fields.py) `MeshLods`), reads
it in both licensee branches (EW's swaps and meshes, UDK's end after the LOD array; a texture lightmap and a vertex
one with its inline payloads) through the reader and the three that take from it, and refuses each broken layout in
each of them. The upk tests of native_fields (15) and audit_lighting (4, the UDK example map's licensee-0 records
among them); the bake tests of the lighting fixture (18), shadow maps (8) and inline lighting (5). At the end: the
bake suite (694 tests, 1 skipped: XCOM_TRANSPLANT_RING; 496 s with other work running), the upk suite (175, 7
skipped: the install-wide checks, run on their own with `--install` (175, 3 skipped), and no private reference
writer), the repo suite (38); the ten Builds (`build_outputs.py`) the same as on the stage's base; two real baked
Builds, the relight run, of the Bar's pieces and of its made pieces the same as on the base, every relit image
texel for texel (102 / 109 s and 144 / 158 s, after / before, other work running).
