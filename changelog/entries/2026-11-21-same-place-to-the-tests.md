### A landing zone comparison only tests used moves to the tests

`spawns.same_place` (whether two landing zones are the same place and direction, within a slack) shipped in
[spawns.py](../../tools/viewer/spawns.py) though only [test_spawns.py](../../tools/viewer/tests/test_spawns.py) called
it (follow-ups item 6.11). It now lives in the viewer tests' shared helpers,
[viewer_fixtures.py](../../tools/viewer/tests/viewer_fixtures.py). The item's other shipped function that only a test
called, `missions.kind_of_export`, went with the Build's `running:` line; `prefab_tests.py` keeps its name (decision
D9: it is the Test in game feature, as its class, its route and its folder are called).

Nothing changes. Checked: the viewer's landing zone tests pass (16 tests).
