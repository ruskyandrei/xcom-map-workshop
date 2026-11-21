### A prefab's check reads the compiler's families' tables of a record's values

[prefabs.py](../../tools/viewer/prefabs.py) kept its own copies of which values an effect's or a sound's record
carries (`EFFECT_VALUE_KEYS`) and a light's (`LIGHT_KEYS`), the same rule as the compiler's effects and lights
families with nothing tying them (follow-ups item 3.1). It now imports them from
[effect_edits.py](../../tools/editor/effect_edits.py) and [light_edits.py](../../tools/editor/light_edits.py)
(`paths.use('editor')`). No import cycle: neither family imports the prefab store. The server's start is unchanged
(it loads both families through the compiler already: `import viewer` 0.437 s before and after, the median of five
runs each, other agents working at the same time).

Nothing changes. Checked: a new test in [test_prefabs.py](../../tools/viewer/tests/test_prefabs.py) holds that the
prefab's tables are the families' own; the viewer's prefab, prefab builder and prefab test tests (44), the editor's
prefab stage tests and the repo suite pass.
