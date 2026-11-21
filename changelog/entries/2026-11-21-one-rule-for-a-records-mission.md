### One rule for a DefaultMaps.ini record's mission, and one for the record a play or an added kind starts from

A record's mission was worked out twice from its MissionType and CouncilType: the map list's `mission_of` (with its
labels) and the mission kinds' `kind_key` (with `KINDS`' labels), and the export called both on one record
(follow-ups item 6.3). [maplist.py](../../tools/viewer/maplist.py)'s new `record_kind` gives a record's mission type
and council type, and `mission_of` and [missions.py](../../tools/viewer/missions.py)'s `kind_key` both read it.

The Build's `template_record` ([build.py](../../tools/editor/build.py)), the base record an added kind of mission is
made from, wrote the rule that [mapsini.py](../../tools/viewer/mapsini.py)'s `slot_record` writes for the record a
play takes when no mission is named (its abduction, else its first that is no council mission, else its first), with
a text test of its own for the abduction; it now calls `slot_record`.

Nothing changes. Checked: the new test in [test_maplist.py](../../tools/viewer/tests/test_maplist.py) holds the map
list's labels and groups against `missions.KINDS`' for every kind (the two sets of kinds and of council types the
same, each kind's record read back to its key), so a label changed on one side fails; the sweep of the three
installs' `DefaultMaps.ini` (every line and record, and each record with blanks around every `=`) gives the same
missions, kinds, play set-ups and added records as before the one reader; the template record is the same record by
the old test and by `slot_record` for every map of the three installs (97, 97 and 103 maps, as written and with
blanks); the editor suite (378 tests) and the viewer's map list, play, manager and mapsini tests pass.
