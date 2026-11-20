### What nothing used taken out of the viewer and the editor

Review finding 63, its first group for `tools/viewer` and `tools/editor`. Each name was searched for across the
repository (tests, notes, the browser checks and the examples included) before it went.

- **No caller at all:** `missions.entry_id`, `pictures.valid_record`, `spawns.ARCHETYPES` (the same table as
  `scene_metadata.LANDING_ROLES`, whose comment now names itself), `builds.stop_process`, and the compiler's
  `PARTNER_MILESTONE` and `STAGE_GRID_PLAYED` ([compiler.py](../../tools/editor/compiler.py),
  [missions.py](../../tools/viewer/missions.py), [pictures.py](../../tools/viewer/pictures.py),
  [spawns.py](../../tools/viewer/spawns.py), [builds.py](../../tools/viewer/builds.py)).
- **Only tests used them:** the compiler's `MILESTONE` (an empty table a test asserted empty: the test now asserts
  that every class with a family builds), `M1_CLASSES` (the Bar's parity test keeps the four classes as its own
  `STATIC_CLASSES`) and `STAGE_LEVELS_PLAYED` (the same 18 as `prefab_bounds.PLAYED_LEVELS`, which the comment now
  names).
- **Branches that could not run:** the compiler's fallback for a missing `ground_looks.json` (it is checked in);
  [build.py](../../tools/editor/build.py)'s check that `find_export` takes `minimum` (it always does: only a test's
  stand-in lacked it, and now takes it); `maplist.MISSION_LABEL['Special']` (`mission_of` answers a special mission
  before the table).
- **build.py:** `package()`'s unused `count`; `EXPORT_MINIMUM` is now the compiler's own rather than a second 18.
- **Unused imports:** `library.piece`'s `Exporter` and `Package`, `area_light_bindings`' `sys`, and those of ten
  test files and two example scripts.

Checked: the editor suite (355 tests, the two pinned-Bar tests run) and the viewer suite.

Kept, and why: `spawns.same_place` (only tests use it, as the Python side of the page's `samePlace`);
`prefabs.py`'s `file_stem` (re-exported in its `__all__`); `prefab_stage`'s `SHELL_DONOR`, which a scan calls
unused but `prefab_tests.py` reads from it (its comment now says so); the test files' `import installs` (it puts
`tools/bake` on the path). Left to their owners: `browser_documents.py`'s unused `project_url` (the browser checks), and the unused
imports under `tools/bake`, `tools/upk` and `tools/lab`.
