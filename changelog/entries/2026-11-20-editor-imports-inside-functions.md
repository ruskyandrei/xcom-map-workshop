### The editor's imports inside functions: the one that can move goes to its module's top, the rest are listed

The compiler part of the editor refactor (plan section 2) asks for no import inside a function in `tools/editor`.
Moving an import to a module's top changes when the imported module loads, so one moves only where the imported
module is already loaded by the time the importing module's top runs; the others stay where they are, each listed here
with why. Nothing the editor does changes.

- **Moved:** [made_edits.py](../../tools/editor/made_edits.py) `wall_look_storeys` imported `frac_wall`; the import is
  now at the module's top, after `import made_split`. `frac_wall` is loaded there already: the module's
  `import ground as ground_shapes` loads it (through `frac_slab`). Checked: the order in which Python loads modules
  (`python -X importtime -c "import <module>"`) is the same before and after for `compiler`, `made_edits`,
  `compiler_tables`, `light_edits`, `mission_edits`, `piece_lookup`, `prefab_stage` and `build` (an `import frac_wall`
  planted at `compiler_tables`' top shows as a different order); `moved_code.py` finds `wall_look_storeys` the same
  but for the import line.
- **Left, in what the release ships** (each would load a module that is not loaded yet when the importing module's
  top runs, so every process that imports the compiler or the Build would load it, earlier or for the first time):
  - [compiler_tables.py](../../tools/editor/compiler_tables.py) `donor_shape` and `made_wall_along`: `frac_wall`. The
    tables module loads first, before every family; `frac_wall` loads later, with the made pieces' family.
    `made_wall_along` also catches an `ImportError` of it.
  - [light_edits.py](../../tools/editor/light_edits.py) `submitted_light`: `storable_cone` from the viewer's
    `lights`, which no compile loads otherwise (only a light with a cone out of range reaches it).
  - [mission_edits.py](../../tools/editor/mission_edits.py) `spawn_rules_notes`: `spawnrules`, which the compiler does
    not load (a Build loads it in `build.py`, after the compiler); only a compile with the library of an install
    reaches it.
  - [compiler.py](../../tools/editor/compiler.py) `find_export`: the viewer's `catalogue`, which only finding an
    export needs.
  - [piece_lookup.py](../../tools/editor/piece_lookup.py) `Library.record`, `Library.load` and `Library.effect`: the
    viewer's `library` and `projects`. The compiler does not load them, and `library` imports the compiler back
    inside its own functions.
  - [build.py](../../tools/editor/build.py): fifteen imports in nine functions (`inline_lighting`, `seed_map`,
    `seed_tiles`, `shell`, `package`, `lightmap_writer`, `package_grow`, `map_frame`, `scene_metadata`,
    `native_spawns`, `stream_copy`), each the module one stage of a Build needs; none is loaded when `build.py`'s top
    runs. (`build.py` is the next stage's, C11.)
- **Left, in what does not ship:** the tests' 47 (in `build_outputs.py`, `compile_record.py`, `test_build.py`,
  `test_compiler.py`, `test_compiler_generated.py`, `test_patchtool_record.py` and `test_spawn_edit_fixtures.py`) and
  one example generator's (`exp51_project.py`). A test loads a module for the one test that needs it, or after setting
  up what the module reads when it loads (the record tools import `compiler` and `build` once their scratch settings
  and wrappers are in place); the rule is read as being about the product's code.

Checked: the compile recorder (`compile_record.py`): the same 1,091 calls of 369 tests as at the start of stage C8;
the ten Builds (`build_outputs.py`), quick and baked, the same; the editor suite (369 tests) and the release suite
(15).
