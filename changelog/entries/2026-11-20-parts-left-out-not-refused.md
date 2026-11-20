### A project whose only change is its missions or its picture builds; a part the compiler can't read is left out, not a refusal

Review finding 39.

- **Missions and picture are changes.** [build.py](../../tools/editor/build.py)'s "the project changes nothing" test
  (now `Build.has_work`) counted no missions list and no map picture, so a project that only narrowed its missions, or
  only gave its map a picture (the LWR 3 map packs' use), was refused. Both count now; such a project builds the map
  unchanged with them, its lighting kept.
- **One bad part no longer refuses the whole project.** [compiler.py](../../tools/editor/compiler.py) `leave_out`
  puts a row in the report's `leftOut` (the Build's window and manifest show it) and the rest builds:
  - an area-light binding it can't use, or a bindings value that is no list (the light follows the export's
    association);
  - a malformed group, or a groups value that is no list (it doesn't break together); a group's nesting is a note
    (`group-nesting`), since nothing of it reaches the game;
  - a building record it can't read or whose id an earlier one has, or a value that is no list
    (`building_records`: the groups and the floors a copy stands in read the same records);
  - a map size it can't build (`stage`: the map keeps its own; the Build's shell stage then reads nothing of it);
  - a spawn rule it doesn't know (the drop-ins as the install has them);
  - `cleared` or `clearKeepsOutside` that is not true or false (not cleared; the clear takes out what lies outside);
  - a landing zone it can't read or whose id an earlier one has (the rest are the variant's; a value that is no list,
    or whose zones are all left out, is as no list, so the base map's lines are copied);
  - a missions entry the Build can't write (`missions_kept`; a value that is no list, an empty list or one with no
    entry it can write is as no list: every record). The report's `missions` is the list the Build writes records
    for.
  Still refused, as nothing can be built from them: the schema, the source, a source that doesn't match, the output
  names, an export without the light data or the tile grid the edit needs.
- **A map picture that can't be written is a note**, where it failed the build after its whole bake. The picture is
  looked up once as the build starts (`Build.find_picture`); missing or unwritable, the map is built without one and
  the manifest's `pictureNote` says why.
- The rule is written in [editor-contracts.md](../../research/editor-contracts.md) ("What refuses a build"), with the
  rows for nesting, landing zones, missions and the spawn rule changed to match.
- Checked: [test_compiler.py](../../tools/editor/tests/test_compiler.py)'s tests of each part now check the part is
  left out and the report good (a bad zone among good ones, a bad missions entry among good ones, one bad building
  among good ones); [test_build.py](../../tools/editor/tests/test_build.py) builds a missions-only and a picture-only
  project, writes the compiler's missions list, reads no `stage` the compiler left out, and keeps a bake whose
  picture fails. The editor suite passes.
