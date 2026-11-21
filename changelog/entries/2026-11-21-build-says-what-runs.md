### The Build says what runs before each tool, and the server reads that line

The build window's line under a running step ("Patch and cook…", "Copying and relighting…", "Making the edit in the
map…", "Relighting…") was worked out by the server from the command line the Build echoes before a tool
([builds.py](../../tools/viewer/builds.py) looked for the tool's file name and `--bake` in it), and its test fed a
hand-written echo, so a change to the echo would have dropped the label unseen (follow-ups item 6.4).
[build.py](../../tools/editor/build.py) now starts every tool through `Build.tool`, which first prints
`running: <label>` (`running:` alone for the shell, the transplant and the intro and stream copies, whose steps say
enough in their own words), and the server reads that line. The fake Build of the viewer tests
([viewer_fixtures.py](../../tools/viewer/tests/viewer_fixtures.py)) prints the line too.
`missions.kind_of_export` ([missions.py](../../tools/viewer/missions.py)), which matched a display label and had no
caller but its test, is gone with its two assertions in [test_play.py](../../tools/viewer/tests/test_play.py).

Nothing changes: the same label shows for the same tools, and an empty line leaves the label as it is, as a command
line with no label did. Checked: the new test in [test_build.py](../../tools/editor/tests/test_build.py) runs a patched
baked Build, a quick one and a relight alone and finds each tool just after its line with its label, and holds that
build.py starts a tool nowhere but in `Build.tool`; `build_outputs.py` record against the start commit: equal; the
editor suite and the viewer's builds, build queue, prefab test and mission kinds tests pass.

Known gap: the page's [missions.js](../../tools/viewer/web/missions.js) still calls its `kindKey` the twin of
`missions.kind_of_export` in its heading comment.
