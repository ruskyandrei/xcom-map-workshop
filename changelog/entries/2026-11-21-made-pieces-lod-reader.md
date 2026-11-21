### The made pieces read a component's LOD 0 through the one reader

Editor follow-ups, stage B2 (item 3.11). [frac_walls.py](../../tools/bake/frac_walls.py) read LOD 0 of a mesh
component's native data three times on raw bytes, with no bounds: `_lod_colours` (where the painted colours lie, which
a made piece's colours replace), `lightmap_offsets` (where the lightmap's textures, scale and bias lie, which
`set_light` writes over) and `add_shadow_ref` (a made piece's own shadow map added to the list). A count that ran past
the record read on into the next bytes, or stopped with a `struct.error`, and `add_shadow_ref` wrote a list cut short
without a word.

- **`frac_walls.lod0`** reads the record with [native_fields.py](../../tools/upk/native_fields.py)' `mesh_lods`, the
  one reader of it ([ARCHITECTURE.md](../../ARCHITECTURE.md), section 3, "The compiler and the Build"): every count
  held to the bytes, every reference to the package's objects, each value with its place. The three readers take
  their places from it, and `add_shadow_ref` also checks the shadow map it adds is an object of the package.
- **The map being grown:** a made piece's component bytes are in the numbering of the map the Build is growing, with
  the objects it added. `GrownObjects` gives the reader that numbering (the grower's imports and exports, its licensee),
  so a reference to a clone made earlier in the Build reads as one.
- **native_fields' `lod_record`** gives the painted colours' places too: `overrideVertexColorsOffset` (the flag's) and
  `overrideVertexColorsEnd` (where they end).
- **What changed for a caller:** what does not read as the layout is a `ValueError` (the reader's `FormatError`) from
  each of the three. `lightmap_offsets` of a component with no LOD record is now that error, where it gave None: its
  one caller in a Build, `component_data`, stopped on the same component a line later with the same words.
- ARCHITECTURE.md's rule of the one reader says the grown map's bytes are read by it too.

Checked:

- A scratch script held the start commit's three functions (from `git show`) against the new ones over every mesh
  component of URB_Bar and URB_PoliceStation (2,543: 2,141 with a LOD record, 402 without): the same places and the
  same bytes from `add_shadow_ref` for all 2,141, on each component's bytes and on the whole package's; the 402
  without a record raised as before in `_lod_colours` and `add_shadow_ref`, and give the error in place of None in
  `lightmap_offsets`.
- New test `LodReaders` ([test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py)), on a made-up component
  that needs no install: the places are the record's, and a component with no LOD record, a LOD count past its end and
  a shadow map count past its end are a `ValueError` from each of the three. Before, 7 of its 9 cases failed (a
  `struct.error`, bytes read on, a list cut short, or None); the two that passed were the no-record refusals the old
  `_lod_colours` and `add_shadow_ref` already had. [test_native_fields.py](../../tools/upk/tests/test_native_fields.py)
  checks the two new places in both licensee branches.
- The upk suite (181 tests, 7 skips for their usual reasons); test_frac_walls (53 tests);
  `tools/editor/tests/build_outputs.py`: the eleven inputs' quick and baked Builds the same as at the start commit.

Known gap: native_fields.py is in the relight's piece cache key (relight.py `TOOL_FILES`), so a project's kept pieces
relight once on its next baked Build, as after stage B1's change to decomp.py.
