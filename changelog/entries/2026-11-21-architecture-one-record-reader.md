### ARCHITECTURE.md names mapsini as the one reader and writer of a DefaultMaps.ini record's fields

[ARCHITECTURE.md](../../ARCHITECTURE.md)'s table of where code goes says that a field of a `DefaultMaps.ini` record is
read and written by [mapsini.py](../../tools/viewer/mapsini.py) (on a line of bytes or of text, blanks around `=` read
as the game reads them) and a record's mission by `maplist.record_kind`, and that no other module writes a pattern
for a field; its note on `build.py`'s size no longer says the Build repeats mapsini's writer (the follow-ups' V3
stage took it out). Checked: the repo suite (44 tests).
