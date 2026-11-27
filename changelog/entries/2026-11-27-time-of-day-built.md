### The Build writes the time of day: the sun or moon, the sky light and the records' time

Stage T-S2 of the game-likeness plan: a project's `sun` (the Map settings window's Sun, moon and sky section) now goes
through the compiler and the Build into the variant map and its records, in a Build without baking as in one with.

- **The compiler** ([light_edits.py](../../tools/editor/light_edits.py) `sun_mark`): a record of the right shape on a
  map with a sun or moon makes the native edit's new `sun` lane: the dominant light's actor and component (their
  names in the persistent level), the record's rotation, colour and brightness, whether the rotation is another than
  the map's own (`directionChanged`; within 2 units of it on each axis it is the map's own, the page's rule) and the
  sky light's actor, component, colours and brightnesses (null where the map has none). The report's `sun` gives the
  time, whether the light turns and the TimeOfDay of the records (`auto` is night while the moon is up:
  [sun_curve.py](../../tools/viewer/sun_curve.py) `game_time`, the page's `gameTime`, both held to the new `gameTimes`
  of [sun_record_cases.json](../../tools/viewer/tests/sun_record_cases.json)). Warnings, none an error: a map with no
  sun or moon passes the record over (`sun-no-light`), a map without a sky light (`sun-no-sky`), a second directional
  light left as it is (`sun-second-light`), and a quick Build that turns the light keeps the old shadows
  (`sun-shadows-stale`, added by the Build through `light_edits.stale_sun`, since the compiler does not know the
  Build's kind). The note `sun-not-built` is gone. The light verdict for the sun, moon and sky light names the Map
  settings window's section, and another directional light's says the time of day leaves it as it is.
- **The lane through its four places**: [compiler.py](../../tools/editor/compiler.py) (the spec's `sun`, the report's
  `sun`, `sun` among the edits that need the export's light data), [native_edit.py](../../tools/editor/native_edit.py)
  `native_split`, the copy tool [native_copy.py](../../tools/bake/native_copy.py) (`BuildState.sun`, its reading in
  `edit_state`, the step `sun_in_place` beside the light edits, the read-back, the manifest's `sun`) with
  [native_lights.py](../../tools/bake/native_lights.py) as its maker (`apply_sun`, `verify_sun`), and
  [build.py](../../tools/editor/build.py), which writes it into `native-edit.json`. The lights are set in place and
  keep their names and GUIDs: the DominantDirectionalLight's `Rotation` where the direction changed, its component's
  `LightColor` and `Brightness` (past its shadow map of the level, F-176), the SkyLight component's `LightColor`,
  `Brightness`, `LowerColor` and `LowerBrightness`, each only where it differs from the map's, a colour keeping the
  map's alpha byte. The sun is drawn live, so a Build with baking makes it as it makes effects, with the map's lighting
  kept; retracing a turned sun's shadows is stage T-S4's.
- **The records**: `config_lines` sets each record's `TimeOfDay` (mapsini.py's `set_field`, the one writer) and the
  manifest's config says `timeOfDay`; Play in game, the campaign install and map packs carry it with the Build's
  records as they are.
- **The page**: the Sun, moon and sky section no longer says the Build does not write it
  ([sun_settings.js](../../tools/viewer/web/sun_settings.js)).
- **EXP-99's project** [exp99_project.py](../../tools/editor/examples/exp99_project.py): URB_Bar made day by the time
  bar (the page's own rules run by node) at a time (13:00 by default), or with the map's own direction
  (`--keep-direction`); [build_outputs.py](../../tools/editor/tests/build_outputs.py) holds the sun lane with it (input
  `bar-sun`).
- Documents: the `sun` row of [editor-contracts.md](../../research/editor-contracts.md) (the lane's form, what the
  Build writes, the report's `sun`) and [ARCHITECTURE.md](../../ARCHITECTURE.md) (the family, the copy tool's step,
  the time of day's row); finding F-200.
- Checked: [test_compiler_sun.py](../../tools/editor/tests/test_compiler_sun.py) (the lane, the report, the
  direction rule, the game time, the four warnings, the verdicts),
  [test_build.py](../../tools/editor/tests/test_build.py) (every record's TimeOfDay, the lane in both kinds of Build
  with the lighting kept, the quick Build's warning),
  [test_native_lights.py](../../tools/bake/tests/test_native_lights.py) (on the install's URB_Bar: the moon turned and
  recoloured and the sky light's four values written and read back, the GUIDs, depths and shadow info kept, nothing
  else of the map changed; a lane as the map has it writes nothing; another light or a wrong read-back refused), the
  lane's line in [test_native_copy.py](../../tools/bake/tests/test_native_copy.py),
  [test_sun_curve.py](../../tools/viewer/tests/test_sun_curve.py) and
  [sun_rules_test.mjs](../../tools/viewer/tests/sun_rules_test.mjs) (the game times),
  [test_manager.py](../../tools/viewer/tests/test_manager.py) (a Build's record of the day installed for campaigns
  both ways, played and packed keeps its TimeOfDay); quick Builds of EXP-99's
  project at 13:00 (turned) and 10:00 (direction kept) read back: only the sun's actor and component and the sky
  light's component differ from the base map; `build_outputs.py` recorded on the stage's base and on the change: the
  twelve inputs before it the same, byte for byte, quick and baked.
- Known gaps: not played (EXP-99 is the game run). A Build with baking keeps a turned sun's old shadows until T-S4.
  `build_outputs.py record` without `--only` stops on this cache before and after the change: no input holds the
  `kismetCuts` and `streamHides` lanes, so both records named every input.
