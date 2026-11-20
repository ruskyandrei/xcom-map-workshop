### The Build's code in modules named for what it does, not in audits, fixtures and experiments

Review finding 53. The release shipped modules named and documented as audits, fixtures and experiments because the
Build and the editor imported parts of them. Each part moved to a module named for what it does; the surveys and lab
tools import it from there, and nothing about what the code does changed.

- [lighting_records.py](../../tools/upk/lighting_records.py): the lighting records every relight and copier reads (a
  mesh component's LOD records, a texture's mips, the properties an object saves, a file's SHA-256, and the viewer
  reader's names), out of [audit_lighting.py](../../tools/upk/audit_lighting.py), which keeps its census and imports
  them. The product's importers in [tools/bake](../../tools/bake) and [lights.py](../../tools/viewer/lights.py),
  and the tests of the product, import the new name.
- [floor_listing.py](../../tools/upk/floor_listing.py): which floors list a piece (`touched`, `listing`, `MARGIN`), out
  of [audit_buildings.py](../../tools/upk/audit_buildings.py); [buildings.py](../../tools/bake/buildings.py) lists by
  it.
- [kismet_links.py](../../tools/upk/kismet_links.py), the Kismet reader, now holds `intro_anchors` (where the dropship
  intro puts its flight for each map), out of [audit_clear.py](../../tools/upk/audit_clear.py);
  [intro_copy.py](../../tools/bake/intro_copy.py) reads it there.
- [lightmap_writer.py](../../tools/bake/lightmap_writer.py): the writer every baked Build's relight writes through
  (`Fixture`, its redirect, setscale, image and gray operations, the cache name's rules). The stage C0-C2 experiment's
  noop, scale and paint and its command line stay in [lighting_fixture.py](../../tools/bake/lighting_fixture.py), as a
  subclass, and re-export the writer's names. The relight, the copier and the Build
  ([build.py](../../tools/editor/build.py): its named copy and its manifest's tool list) use the new module.
- [lightmap_textures.py](../../tools/bake/lightmap_textures.py): the readers of an original bake's top mip, out of the
  EXP-16 statistics tool [lightmap_stats.py](../../tools/bake/lightmap_stats.py), and the texture clone, out of the
  gate C6 tool [grow_fixture.py](../../tools/bake/grow_fixture.py). The kept mips no longer go into the package
  object's `__dict__`: a weak table of the module's holds them for each package while it is open.
- [mapsini.py](../../tools/viewer/mapsini.py): the game's config lines (`lines_of`, `is_record`, `field`, `set_field`,
  `unquoted`, `add_stream`, `slot_record`, `plan_lz`, `check_change`, `write_checked` and the rest), out of the lab's
  fixture installer [deploy_fixture.py](../../tools/bake/deploy_fixture.py), which imports them for the lab.
  [installs.py](../../tools/viewer/installs.py), [gamemaps.py](../../tools/viewer/gamemaps.py) and
  [manager.py](../../tools/viewer/manager.py) import them there (their import lines alone changed), and
  [test_install_recovery.py](../../tools/viewer/tests/test_install_recovery.py) stands in for the writer there.
- The helpers used across modules are public: `light_factory.class_of`, `tagged_property` and `preamble`;
  `cover_blocks.recipe_imports` and `export_template`.
- The relight's piece cache is keyed on `lightmap_textures.py` and `lighting_records.py` in place of the old two, so
  a project's kept pieces are relit once more after this change.

The release: nothing it ships imports `tools/lab` any more, and
[test_release.py](../../tools/release/tests/test_release.py) now checks that, and that the new modules ship.
`make_release.FOLDERS` still lists `lab` for the embedded Python's path; that entry can go.

Checked: the upk and release suites; the bake tests of the fixtures, relight, faster bake, intro copy, buildings,
cover blocks, lights, map picture, the lab installer, inline lighting, shadow maps, walls and measurers; the viewer's
install, manager, game maps, deploy, lights, play, output names and pack tests.
