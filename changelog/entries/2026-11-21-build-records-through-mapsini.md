### The Build writes its DefaultMaps.ini records through mapsini, the installer's writer (one writer of a record)

[build.py](../../tools/editor/build.py) held a text copy of [mapsini.py](../../tools/viewer/mapsini.py)'s record
writer (`field_re`, `set_field`, `add_stream`, follow-ups item 3.27). The three are gone: `config_lines` and the
records' helpers read and write a record through `mapsini.field`, `unquoted`, `set_field`, `add_stream` and
`slot_streams`, which now take a line of text as well as one of bytes and give a line back in the kind they were
given (a line of bytes is read as Latin-1, a character a byte, so it goes back byte for byte; the patterns match a
line of text as they match its bytes). The base map's records are found by `installs.same_map` on the record's Name
as `mapsini.field` reads it, as the install finds them, in place of a regular expression of the Build's own; the
intro a record streams is read by `slot_streams`; the template record's council test, the display names and the
`|n` ending read through `field` and `unquoted`. [missions.py](../../tools/viewer/missions.py)'s `added_record`
streams the bomb's stream with `mapsini.add_stream` itself, so the Build no longer passes its copy in.

What a Build writes is the same. Two things differ where no Build goes: `mapsini.add_stream` refuses a patch name that
is not a package name and a stream the record has already (the Build's copy did neither; a Build's patch is
`patch_<map>`, and an added bomb record streams the bomb's stream only where its template has none), and a refusal of
the writers (a base record without a Name or DisplayName to set) stops the Build with "a DefaultMaps.ini record can't
be written: record has no DisplayName" (`record_edits`) where it said "the record has no DisplayName".

Checked: the editor suite (377 tests, its config-line tests now writing their records with `mapsini`), and the
viewer's install, play, map list, output names and pack tests and the bake suite's deploy tests, which use mapsini's
writers on bytes; [build_outputs.py](../../tools/editor/tests/build_outputs.py)'s records on the commit before and on
this one are the same (11 inputs, quick and baked Builds, the config lines among them).
