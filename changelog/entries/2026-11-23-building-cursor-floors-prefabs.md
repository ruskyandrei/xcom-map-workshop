### Prefabs carry a building's cursor floors (prefab schema 5)

A prefab's building may carry `cursorFloors` as a project's does: the prefab store takes it (true or false) and raises
the prefab schema to 5 ([prefabs.py](../../tools/viewer/prefabs.py), [prefabs.js](../../tools/viewer/web/prefabs.js);
an editor of before it says such a prefab is newer rather than refusing the key), and
[editor-contracts.md](../../research/editor-contracts.md) says so. Saving a selection as a prefab and placing one
carry the tick (the page's side came with the Buildings view's tick).

Checked: [test_prefabs.py](../../tools/viewer/tests/test_prefabs.py) (the tick read, a tick that is not true or false
refused, schema 1 to 4 read and stored as 5); the browser check `cursor-floors` now saves the ticked building as a
prefab and pastes a copy of it, both keeping the tick; `projects`, `prefabs`, `documents` and `builder` on a test
server (their 500 answers are their own simulated failures); the viewer's prefab, project and twin-constant tests, the
node suite.
