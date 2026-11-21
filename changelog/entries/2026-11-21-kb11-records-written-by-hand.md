### A Replace build takes out a map record written by hand with spaces around "=" (KB-11)

A record of `DefaultMaps.ini` written by hand as `Name = "URB_Bar"` (the game reads it so) was found by the map list
and the export, which allow blanks around `=`, but not by the install, whose reader did not: installing a Build that
replaces the map added the editor's records and left that one live, so the game could still load the original.

[mapsini.py](../../tools/viewer/mapsini.py), the install's reader and writer of a record's fields, now reads a field
as the game and the map list do (decision D5 of the follow-ups plan: the tolerant way everywhere): `field`,
`unquoted` and `set_field` allow blanks around `=`, and an unquoted value may hold digits as well as letters and
underscores (the installs' landed and crashed UFO records write `ShipType=10`; the map list read those already).
`set_field` writes the field it sets without blanks, as the game's records are. Everything that reads a record
through mapsini reads such a record now:

- the install ([installs.py](../../tools/viewer/installs.py)): a map's records (`base_records`), the records a Replace
  comments out (`replaced_records`), a record's rotation and mission;
- the Build ([build.py](../../tools/editor/build.py)), which since the commit before writes its records through
  mapsini: it finds the same records of the base map as the install in the same order (so a Build's records stand
  for the install's: `config.recordMissions`), and writes its own copy of a hand-written one, where it left it out
  before;
- the library's donor maps ([library.py](../../tools/viewer/library.py)), whose record names now come from
  `mapsini.field` in place of a pattern of their own.

What a user sees: such a record is commented out by a Replace install like the map's other records, and put back as
it was when the install is taken out; a Build of the map has a record for its mission. Records written as the game's
are read as before (the three installs hold none with blanks around `=`), and no Build's output changes.

Checked, each test failing before the change: [test_manager.py](../../tools/viewer/tests/test_manager.py) installs a
Build in Replace mode on an install whose Bar terror record is written `Name = "URB_Bar"` and
`MissionType = eMission_TerrorSite`: the three records of Bar are commented out (two before), the variant has a
record for each mission, and a reset leaves the files byte for byte; [test_build.py](../../tools/editor/tests/test_build.py)
has the Build and the install find the same records, a hand-written one among them, and the Build write its copy;
the new [test_mapsini.py](../../tools/viewer/tests/test_mapsini.py) reads and sets fields with blanks around `=` and
`ShipType=10`, and reads and writes a line of text as its bytes (that second test passes on the commit before too).
The editor suite (378 tests), the viewer's install, play, manager, pack, map list, output names, library and squad
tests (170; the 10 game-script tests skipped while a lab copy of XCOM ran) and the bake suite's deploy tests pass.
KB-11 leaves [KNOWN-BUGS.md](../../KNOWN-BUGS.md).

Left as it was: the stream names in a record (`MapName="..."`) are still read without blanks around `=`, everywhere
the same way (mapsini's `slot_streams` and the readers that follow it).
