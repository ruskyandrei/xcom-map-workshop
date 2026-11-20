### The Build takes its inputs as one record, and names its stages' state where it is made

[build.py](../../tools/editor/build.py): `Build.__init__` took 21 parameters (22 with `self`: the project, four
folders, the options, the server's ids and five stand-ins a test gives for its tools). It takes one record now,
`BuildInputs`, a frozen dataclass whose fields are those parameters in the same order with the same defaults, so a
caller's arguments move into it unchanged (`build.Build(build.BuildInputs(project, cache, output, lwr, udk, quick=True))`).
`main` makes it from the command line; the server starts `build.py` as a process, so its command line and the server
are as they were. `__init__` reads the record once and keeps each value under the attribute it had (`self.quick`,
`self.lwr`...), so no stage's code changes: that is fewer changed lines than reading `self.inputs.x` in the stages,
which read those attributes in about ninety places, and the tests that set one (`b.enable = ...`) still do.

The state the stages fill (about fifty attributes, from the project's document to the finished manifest) is now named
in `__init__`, grouped by the stage that fills it, with a comment each. Eight reads that went through `getattr` or
`hasattr` with a default (`stage_kept`, `picture_png`, `moves_landings`, `_landing_moves`, `shelled`, `variant`,
`work`, `unpacked_work`) read the attribute: each starts at the value the default gave (`_landing_moves` at None, its
memo filled on the first ask). Nothing a Build does changes.

The callers make the record: `main`, the tests' helpers and their other Builds
([test_build.py](../../tools/editor/tests/test_build.py), [test_export_choice.py](../../tools/editor/tests/test_export_choice.py)),
[build_outputs.py](../../tools/editor/tests/build_outputs.py) and the 39 example generators in
[examples](../../tools/editor/examples) that build. The test of a pinned command line reads the record's fields where
it read the arguments. [ARCHITECTURE.md](../../ARCHITECTURE.md) says how the Build is given its inputs.

Checked: `moved_code.py` on build.py against the stage's start: 65 of its 67 functions the same, six of them after the
eight `getattr`/`hasattr` reads were substituted, and `Build.__init__` and `main` differing as above; the compile
recorder (1,091 calls of 369 tests) and the ten Builds (`build_outputs.py`, quick and baked) the same as at the start;
the editor suite.
