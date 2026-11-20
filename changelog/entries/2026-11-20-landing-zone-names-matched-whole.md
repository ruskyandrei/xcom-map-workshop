### A landing zone's mission name is matched whole; the page and the server agree on every zone case

Review finding 27. `spawns.valid_zone` checked a zone's `missionType` and `councilType` with `^...$`. In Python `$`
also matches before a final line break, so `eMission_Abduction` followed by a line break passed, and `write_line`
would have split the install's LZArray line in two. Only a hand-edited or foreign project file could hold one: the
page refuses it.

- [spawns.py](../../tools/viewer/spawns.py) matches the names whole (`fullmatch`). The compiler's `ACTOR_NAME`
  ([compiler.py](../../tools/editor/compiler.py)) ends in `\Z` for the same reason.
- The two validators now agree that a field given is one of its kind and null is no value of any of them.
  `alternate: null` was valid on the server and refused on the page. `kind: null` was the other way round. Both are
  refused now ([spawns.py](../../tools/viewer/spawns.py), [project.js](../../tools/viewer/web/project.js)).
  `validLandingZone` now always answers true or false.
- [zone_cases.json](../../tools/viewer/tests/zone_cases.json) holds 34 zones with the answer each should get.
  [test_spawns.py](../../tools/viewer/tests/test_spawns.py) runs them through `valid_zone` and
  [clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs) through `validLandingZone`. No saved project is
  affected: the page never writes null for a zone's field.
