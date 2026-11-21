### One reader of a DefaultMaps.ini record's fields: the map list and the mission kinds read through mapsini

A record's fields were read in three places, written three times: [maplist.py](../../tools/viewer/maplist.py)'s
`field` and `unquoted`, [missions.py](../../tools/viewer/missions.py)'s `_unquoted` and `_quoted`, and
[mapsini.py](../../tools/viewer/mapsini.py)'s (follow-ups item 6.3). With mapsini reading a record as the other two
did (the commit before), theirs are gone: the map list, the mission kinds (a record's kind, a play's UFO type and map
family), and the export, the output names and the install that used `maplist.field`
([export.py](../../tools/viewer/export.py), [outputnames.py](../../tools/viewer/outputnames.py),
[installs.py](../../tools/viewer/installs.py)) read through `mapsini.field` and `unquoted`. `missions._set`, which
sets a field of an added kind's record, sets through `mapsini.set_field` (and adds the field before the closing
bracket where the record has none, as before). The readers of the streams a record names that copied
`mapsini.slot_streams`' pattern (the export's, the output names' two, the library's donors') call it.

Nothing changes: the answers are the same. A record's kind still reads from a line of bytes or of text (mapsini reads
either). The one difference is in what no record holds: the map list's patterns matched any Unicode letter or blank
in a line of text, mapsini's match a line of text as its bytes would (the installs' records are ASCII).

Checked: a sweep of every line of the three installs' `DefaultMaps.ini` (678, 680 and 700 lines and records, each
record also with blanks put around every `=`) through the map list's, the mission kinds' and the streams' readers, a
record's mission and kind, a play's set-up and an added kind's record: the same answers on the commit before and on
this one. The exports of URB_Bar and URB_StreetHurricane (whose second record is a council bomb) are byte for byte
the same before and after. The viewer's map list, play, manager, output names, install and mapsini tests pass (the
map list's test reads a display name through mapsini now).

A field regular expression for a `Maps=(...)` record is left nowhere in the shipped code outside mapsini.py (`grep` of
tools/viewer, tools/editor, tools/bake and tools/upk for patterns of `Name=`, `DisplayName=`, `MissionType=`,
`CouncilType=`, `bInRotation=`, `ShipType=`, `MapFamily=` and `MapName=`) but the Build's template record's
abduction test, which the next commit takes. Left as they are: the map pack's install script, which runs in
PowerShell on a player's computer and matches `Name="..."` and `DisplayName="..."` itself
([pack_scripts.py](../../tools/viewer/pack_scripts.py)); the lab's and the package audits' readers
(tools/upk/audit_*.py, tools/lab); the release's readme check
([readme_install_check.py](../../tools/release/readme_install_check.py)); and the Build's and the install's swap of
an intro's name in a record's streams (a text replace of `MapName="<intro>"`).
