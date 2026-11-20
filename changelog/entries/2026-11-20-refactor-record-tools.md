### Two record tools for the editor refactor: the ten Builds byte for byte, and every compile of the editor suite

The editor refactor's checks (its plan's stage 0, items 0.1 and 0.2): a step that touches the compiler, the Build,
the copy tool, the package tools or the relight must leave their output as it was, and these two tools record that
output on the code before and after so that the two can be compared. They are tools, not tests: the test runner does
not run them, and their records are not checked in. No product code changed.

- **[build_outputs.py](../../tools/editor/tests/build_outputs.py)**, the ten Builds.
  - `record --out <folder> [--only NAME ...]`: ten project inputs, each a quick Build and a baked Build into scratch
    folders under `<folder>`, with the Build's `run` hook a recorder. Every tool runs as in a real Build except the
    relight (relight.py, or native_copy.py `--bake`): its command line and the SHA-256 of each file it names are
    recorded, and in its place native_copy.py makes the edit without `--bake` and a stand-in relight record lets the
    Build go on. `outputs.json` holds, for each input and Build, the SHA-256 of every file of the package (the
    variant map, the intro and stream copies, the readme), the manifest and compile report (times, attempt ids,
    the tools' own hashes and folders masked; the Build's clock is fixed), the relight's command (folders masked)
    and the native edit the Build wrote; and for each input its project document, the compile's whole spec, report
    and native edit, and the export it read.
  - The ten inputs are made by the generators in [tools/editor/examples](../../tools/editor/examples), each run in a
    process of its own on scratch settings with its compile recorded and its own Build refused. Seven of them merge
    the documents of two or three generators on one map (refused where two documents disagree on a piece or an
    override); two add a field or a piece in code (a spawn rule; an invisible floor). Together they hold every lane
    of the native edit: the Bar's copies, moves and deletions with cars and lights; effects, sounds and flares; spawn
    points moved, given values, copied and deleted, with a spawn rule; made walls with openings, flags and a break
    group, made floors, roofs and ground, map pieces broken; cover blocks that break with their group and an
    invisible floor; a building of the project and the map's own edited; Clear map on a larger grid with landing
    zones; a car, a door and a ladder of other maps; pieces' flags; cars and made walls on the police station; and its
    data recovery's capture point moved in its mission stream. `--list` prints each input with its lanes, and
    `record` fails when a lane (read from `native_split`'s and native_copy.py's code too) is in none of them.
  - `compare <before> <after>` lists what differs by input (files, manifest keys, compile keys, the relight's
    command, the export read) and exits 1.
  - The install and the cache come from the settings or `--game`/`--cache` (exit 2 without them). The cache is only
    read: the exports' scene.json and the library index are copied into a scratch cache, where the library makes
    pieces of other maps afresh from the install. A whole record takes about two minutes.
- **[compile_record.py](../../tools/editor/tests/compile_record.py)**, every compile of the editor suite.
  `record --out <file>` runs the editor suite's test files in one process with `compiler.compile_project` and
  `compiler.native_split` wrapped before any test file is imported (so the files that import the names themselves
  reach the wrappers), and writes each call in order: the test, a hash of its inputs (document, scene, families on
  and off, the kind of library) and its outputs whole (a compile's spec, report and the native split of its spec; a
  native split's patch spec and native edit). `compare <before> <after>` gives each test's first differing call with
  the differing keys, and exits 1. Masked, in the inputs only: the light GUIDs test_compiler makes from Python's
  string hash and the savedAt of test_prefab_stage's project, which are new each run; nothing else differs between
  two runs.
- **[test_record_tools.py](../../tools/editor/tests/test_record_tools.py)** (editor suite, no install): the two
  tools' compares say a difference for its input or test alone and compare every part of a record; the masks, the
  lanes, the merge and its refusals, and the planted byte.

**How a stage uses them** (a tool checks the code of the checkout it runs in): make a scratch worktree of the
stage's base commit and record there (`build_outputs.py record --out <base folder>`,
`compile_record.py record --out <base file>`), record again on the stage's head, and compare the two records of each
tool. Both build records must read the same exports: if the cache gets a newer export of an input's map between
them, `compare` says so.

Checked: two records of one commit compare equal (build_outputs: ten inputs, quick and baked, about two minutes a
record; compile_record: 1091 calls, 822 of them compiles, of 369 tests, about ten seconds); a record with one byte
planted in one copy's pose (bar-pieces, the destructible copy's x) differs from the first for that input alone, in
its document, compile, both maps, manifests, compile reports, native edits and relight command; a record with no
install or no cache exits 2; the editor suite (369 tests) and the repo suite.

Known gaps: no input makes an edit that only a patch or a larger grid makes, so the Build's relight-alone path
(relight.py on a named copy of the map) is not among the ten; the baked Build's map is the quick one's, since the
relight is not run (a step in tools/bake or tools/upk runs real baked Builds as well, by the plan's ground rules);
compiles in a subprocess of a test are not recorded.
