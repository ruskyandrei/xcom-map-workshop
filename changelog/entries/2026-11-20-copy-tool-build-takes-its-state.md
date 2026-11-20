### The copy tool's build takes one record, its BuildState, in place of thirty parameters

Review finding 51, refactor stage B4, step 1: `native_copy.build` took thirty parameters, and every caller named
them all.

- [native_copy.py](../../tools/bake/native_copy.py): `BuildState` is a dataclass whose first fields are the Build's
  inputs (the map, the output folder, the variant, the copies, the options and the native edit's other lanes, in
  `build`'s old order and with its defaults), each with a comment; the fields `build` fills (the map read, what the
  edit took out) follow, each named with the step that fills it. `build(st)` reads the inputs into the names its
  lines always used, so its body is as it was. Two fields of the state shared a name with an input and are renamed:
  clear_level's record is `cleared_record` (`cleared` is the compiler's clear), and the resolved light edits the
  manifest and the relight command read are `light_state` (`lights` is the native edit's). `main` makes the state
  from the command line.
- The tests that build make the state: [fixtures.py](../../tools/bake/tests/fixtures.py)'s `native_build`,
  `copies_build` and `lanes_build` (and two of its docstrings' words), and the calls in the tests of native copies,
  made walls, ground and slab measures, building edits, effects, flags, lights, spawns and the transplant. The
  command line's test reads the state `main` hands to `build`.

Checked: `build`'s body, less its seven lines reading the state, is the old one's syntax tree with the three renames
(a scratch check built on `moved_code.python_normal`, since moved_code compares whole functions and the signature
changed); `moved_code.py` on `manifest_parts`, `relight_command`, `BuildState.gone` and `main` with the renames and
the call's new record as substitutions: the same; the ten Builds (`build_outputs.py`) equal to the code before; the
bake suite.
