### The Builds check gains an input whose only edit is a larger grid

[build_outputs.py](../../tools/editor/tests/build_outputs.py) recorded no Build that sends its map to the relight
alone, on the copy the growing writer names ([build.py](../../tools/editor/build.py) `named_base`,
[package_grow.py](../../tools/upk/package_grow.py)): an edit only a patch or a larger grid makes (follow-up 4.3). A new
input, `bar-grid`, is URB_Bar grown to 56 by 43 tiles and nothing else, made by a new generator,
[grid_bar_project.py](../../tools/editor/examples/grid_bar_project.py). Its baked Build's record holds the relight's
command on the named copy and that copy's SHA-256, so a change to the growing writer or to `named_base` shows. The
tool's docstring and [ARCHITECTURE.md](../../ARCHITECTURE.md) section 5 name the inputs without a count.

A real baked Build of such a project stops in the relight
([KNOWN-BUGS.md](../../KNOWN-BUGS.md) KB-2, T-37): the tool records the relight's command and does not run it, so the
input records that route as it is. KB-2 is not fixed here (the follow-ups plan's decision D7).

Checked: `--list --only bar-grid` shows it (compiled, no warning; its native edit holds the map's carried effects
alone); two records of it are the same; a whole record (eleven inputs, 117 s, other agents running) against the start
commit's record (in a scratch copy of 0012083, 116 s) and against the follow-ups' baseline differs only in `bar-grid`,
recorded on the new side only.
