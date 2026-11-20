### The compiler's spawn point edits recorded as fixtures

Review finding 23, its first step: before the compiler's spawn family moves out of the `Compiler` class, what it gives
for the existing fixtures is recorded, so the move can be compared against it.

[test_spawn_edit_fixtures.py](../../tools/editor/tests/test_spawn_edit_fixtures.py) builds 38 cases from the compiler
tests' spawn scene and records (the four spawn tests of
[test_compiler.py](../../tools/editor/tests/test_compiler.py), and a few more refusals and notes: a malformed
`spawn`, an unknown field on an override, a copy and a volume, a box the map already has, a volume copy with no id).
[spawn_edit_cases.json](../../tools/editor/tests/spawn_edit_cases.json) holds each case's inputs (the base scene once,
the keys each case's scene changes, the document, the families switched on or off) and what the compiler gave:

- whether the report is ok (a refused spawn record is left out and the build goes on);
- the native edit's `spawns` lane, the records the Build writes, in their order;
- the report's spawn entities and spawn counts;
- every error, warning, note and piece left out, in order.

`python -B tools/editor/tests/test_spawn_edit_fixtures.py --write` records them again after a deliberate change.

Checked: the new test passes on the compiler as it is (the editor suite).
