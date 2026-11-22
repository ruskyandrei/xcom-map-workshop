### A clear takes the map's triggers out; a project can give the map another background sound (F-159, F-160; export 39, project schema 5)

The trimmed part of the triggers investigation (the full Triggers view stays on the reference branch
`editor-triggers`): the Build's side of both, the Clear map window's tick, and the page carrying the background sound
(its control waits on the user's choice of design).

- **A cleared map's triggers** (F-159). [native_copy.py](../../tools/bake/native_copy.py) `clear_level` takes the
  level's trigger volumes and sight points out (`CLEAR_TRIGGERS`, which `CLEAR_KEEP` kept until now) and switches off
  every sequence event whose Originator is a volume it took (`switch_off_events`, `bEnabled` false; the cleared
  record's `eventsOff`), unless the cleared mark says `keepTriggers`. The project's `clearKeepsTriggers` sets it
  ([mission_edits.py](../../tools/editor/mission_edits.py) `cleared_mark`, [compiler.py](../../tools/editor/compiler.py)).
  A cleared project saved before has no such field, so its next Build takes them out.
- **The map's background sound** (F-160). The export reads it ([background_sound.py](../../tools/viewer/background_sound.py):
  the scene's `backgroundSound`, with `triggerCounts` from [scene_metadata.py](../../tools/viewer/scene_metadata.py);
  export 39), and [background_sounds.json](../../tools/viewer/background_sounds.json) lists the game's 26 beds with the
  base map that plays each. The project's `backgroundSound` (`{cue, volume?}`, a cue or null; schema 5 in
  [projects.py](../../tools/viewer/projects.py), [project.js](../../tools/viewer/web/project.js) and the compiler) is
  checked by [effect_edits.py](../../tools/editor/effect_edits.py) `background_sound_mark` (left out where it can't
  be built: its shape, an export before 39, a map with none, a cue off the list) and goes into the native edit's
  `backgroundSound` lane ([native_edit.py](../../tools/editor/native_edit.py)) with the map it comes from as its
  donor. [transplant.py](../../tools/bake/transplant.py) brings a cue from its map as assets (`closure` and `bring`
  with `assets`; `stage_edit` for the lane's donor), and [native_sounds.py](../../tools/bake/native_sounds.py)
  `background` points the map's level-loaded `SeqAct_PlaySound` at it, or at none, with its volume, read back by
  `verify_background`. [build.py](../../tools/editor/build.py) runs the transplant for it, counts it as work that
  changes no light (it goes with the effects) and writes the manifest's `backgroundSound`.
- **The page.** The Clear map window has "Keep the map's triggers and scripts" (remembered, as the scenery tick is;
  hidden on a map with none), and its plan names the map's touch triggers, water volumes and sight points as going
  or staying, and says the background sound stays ([clear_map.js](../../tools/viewer/web/clear_map.js), from export
  39's `triggerCounts`). The project's `clearKeepsTriggers` and `backgroundSound` are kept, saved, recovered, undone
  with the clear or Reset all ([editor_state.js](../../tools/viewer/web/editor_state.js),
  [document_state.js](../../tools/viewer/web/document_state.js),
  [document_session.js](../../tools/viewer/web/document_session.js),
  [delete_reset.js](../../tools/viewer/web/delete_reset.js), `validBackgroundSound` in project.js), so a page saving
  a project never drops them; test hooks `clearKeepsTriggers` and `backgroundSound`.
- [clear_bar_project.py](../../tools/editor/examples/clear_bar_project.py) takes `--keep-triggers`, `--sound`,
  `--volume` and `--cache`; [build_outputs.py](../../tools/editor/tests/build_outputs.py)'s bar-clear input gives it
  the forest bed, so the new lane is covered. The examples that save into a store write the current schema.
- Records: [editor-contracts.md](../../research/editor-contracts.md) (schema 5's two fields, export 39's),
  [findings-register.md](../../research/findings-register.md) F-159, F-160,
  [EXP-94](../../research/experiments/EXP-94-background-sound-and-clear.md), [ARCHITECTURE.md](../../ARCHITECTURE.md).

Checked: the editor, viewer, node and repo suites; the bake suite's clear, copy tool, effects and transplant tests
(`ClearLevelTriggers`: Roadhouse cleared, 13 volumes and its sight point out, two events off, every other sequence
object byte for byte, all kept with `keepTriggers`; `StagedBackgroundSound`: Bar given DeepWoods' forest bed, read
back, none and a volume in Bar as it is); the compiler's `BackgroundSound` tests; a cleared Bar built quick with the
forest bed and read back; the browser check clear-map on a test server (the plan's words with the tick on and off,
a clear that keeps the triggers saved and undone). In the game, EXP-94: the forest bed plays across the map and after a load, the rats'
events stay off, a quicksave loads; with none the map loads and plays no bed.

Known gaps: the page has no control for the background sound yet: where it lives waits on the user's choice of
design (mock designs shown). Plain Enemy Within not played.
