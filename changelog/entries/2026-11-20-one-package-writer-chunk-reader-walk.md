### One package writer, one chunk reader and one bounded property walk

Review finding 52, its first step. The package tools wrote, read and walked the same things several ways, and the
copies checked different things.

- **One writer.** [seed_tiles.py](../../tools/upk/seed_tiles.py) `seed_package`,
  [world_links.py](../../tools/upk/world_links.py) `write_package` and [bake_actor.py](../../tools/upk/bake_actor.py)
  `rewrite` now build edit lists for [package_edit.py](../../tools/upk/package_edit.py) `write_edited`, in place of
  their own block writers. They take a container or an edit in any chunk (later chunks move along, the chunk table
  follows), an uncompressed map such as DLC2_3_Furies, and blocks of any size; seed_tiles' second `lzo_literals`
  (which refused blocks under 19 bytes) and its `chunk_table_offset` are gone. On URB_Bar the seeded, link-moved and
  actor-baked packages are byte for byte those the old writers made.
- **One chunk reader.** [decomp.py](../../tools/upk/decomp.py) `read_chunk` checks a chunk header's tag, block size,
  block table sums and length; the map decode, [upkinfo.py](../../tools/upk/upkinfo.py) `load`'s packages compressed
  whole and package_edit's writers read through it (package_edit's `read_chunk` is that one). The map decode also
  refuses a chunk whose size is not the chunk table's. [audit_cross_map.py](../../tools/upk/audit_cross_map.py)'s
  copy of the whole-file decode now calls `upkinfo.load`.
- **One bounded property walk.** [props.py](../../tools/upk/props.py) `tags` (and `read_tags`) walks tagged
  properties with the viewer reader's checks: a name or kind outside the table, a negative size, a value past the
  end, and a list without its None are refused, never read through. It takes the names the bytes were written with,
  so a Build's grown bytes walk with the grower's (review finding 37). The Build's `Walker`
  ([native_copy.py](../../tools/bake/native_copy.py)), the Kismet reader `kismet_links.P.props` (every Build that
  makes an intro copy) and bake_actor walk with it.
- **One static tile store reader.** world_links `static_tiles` reads the static flags with `parse_store`'s checks
  (every chunk of the grid saved, as before). native_copy reads them through it once for each open package
  (`static_flags`, in place of a parse for each seeded copy), and seed_tiles' unchecked `parse_static_store` is gone.

Tests: [test_package_edit.py](../../tools/upk/tests/test_package_edit.py) (the actor baker in blocks of 10 bytes;
on URB_Bar, seeds land on the empty tiles and nowhere else, an uncompressed bar seeds as the compressed one, a link
move changes only the container), [test_bad_input.py](../../tools/upk/tests/test_bad_input.py) (damaged chunk headers
refused, a chunk of another size than its table refused) and [test_props.py](../../tools/upk/tests/test_props.py)
(the walk, what it refuses, the Kismet reader on it).

Checked: the upk suite; the bake tests of the native copies, save tiles, shell, intro copy, lights, cover blocks,
flags, effects, buildings, fractured walls, spawns, streams, transplant and clear; quick and baked Build outputs of
ten real project inputs (scratch builds, relight stubbed) byte for byte those of the code before; on installed maps,
the decodes of five maps and the twelve packages compressed whole, the intro anchors of CIN_DropshipIntros, the
Kismet reader over every export of it and of URB_Bar (one component the reader never could read now fails with a
ValueError, not a struct error) and the Build's walker over every export of URB_Bar and TempleShip are the same as
before.

Left for a later step: the other walkers of tagged properties (props.read_props, typed_props, map_inventory,
script_enums, pack_card, audit_cross_map, audit_install in tools/upk; the viewer's Package.tagged; relight,
lightmap_fields, light_factory, inline_lighting, map_frame and native_spawns in tools/bake), `Walker.refs`' guess at
reference arrays, audit_install's first-block header read and the lab's save reader (tools/lab/save_tiles.py), and
wdparse.py's static store parser (research).
