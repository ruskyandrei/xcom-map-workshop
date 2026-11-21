### A build's step no longer shows the last tool's label while a tool without one runs

When a baked Build's light stage failed on copies it had not been tried on and the Build tried again without them, the
build window went on showing "Copying and relighting…" while the transplant ran again: the server kept the last
tool's label until the next stage ended. The Build's empty `running:` line before such a tool (the shell, the
transplant, the intro and stream copies) now clears the label in [builds.py](../../tools/viewer/builds.py), so the
step shows its own words, as it does for those tools in every other build.

Checked: the new test in [test_builds.py](../../tools/viewer/tests/test_builds.py) (failed before: the label stayed)
reads a labelled line, a progress line, an empty line and another label; the viewer's builds and build queue tests
pass.
