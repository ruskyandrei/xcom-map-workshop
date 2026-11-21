### A map pack installed in Replace mode switches off a record written with blanks around its '='

KB-11's twin for map packs: the PowerShell a map pack carries for players
([pack_scripts.py](../../tools/viewer/pack_scripts.py), run by the pack's Install.cmd and Uninstall.cmd) found a
DefaultMaps.ini record's `Name` and `DisplayName` only when written `Name="..."`, so a pack installed in Replace mode
left a base map's record written by hand as `Name = "URB_Bar"` in use beside the pack's map (the game reads such a
record, and the editor's own install switches it off since KB-11's fix). The script's patterns now allow blanks around
`=`, as [mapsini.py](../../tools/viewer/mapsini.py) reads a field: the base map's records it switches off or puts
its own after, the pack's own records it checks for, and the DisplayName a pack's map switches off by.

Checked: the new test in [test_pack_scripts.py](../../tools/viewer/tests/test_pack_scripts.py) runs a Replace pack's
Install.cmd on a game whose Bar record is written with blanks around both fields (failed before: the record stayed
in use): the record is commented out, Bar's records the pack's maps have none for stay in use, and Uninstall.cmd
puts the file back byte for byte; the viewer's pack script, manager and pack export tests pass (XCOM was not running:
none skipped).
