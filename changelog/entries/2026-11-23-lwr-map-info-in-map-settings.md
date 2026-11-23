### Map settings tell Long War Rebalance the largest abduction a map suits and keep Hold the Line off it

Long War Rebalance 3.00.00 beta 17 reads "map info" for a map, by its file name: `AlienDensity`, the largest
abduction the map suits (Light, Moderate, Heavy or Swarming; a larger abduction is moved to another map), and
`HoldTheLine`, where `No` keeps Hold the Line off the map. A map pack gives its own in `MapInfo=` lines, in its block
or on its card. The editor now sets both for a project, and a pack exported from it carries them.

- **The Map settings window** has a Long War Rebalance section under the background sound
  ([index.html](../../tools/viewer/web/index.html), [map_settings.js](../../tools/viewer/web/map_settings.js)):
  Largest abduction (Not set, or one of the four sizes) and "Keep Hold the Line off this map". Each change is one
  undo step, Reset all takes them back, and the header counts them ("Long War Rebalance map info set"). The section
  is not shown where the game set is plain Enemy Within and the project tells nothing. It is a section of its own so
  that what LWR reads later has a place.
- **The project** keeps them as `lwrMapInfo` (`{ alienDensity?, holdTheLine? }`), which makes project schema 6: the
  page, the server and the compiler read 1 to 6 and write 6, and an editor from before does not open a project saved
  by this one ([project.js](../../tools/viewer/web/project.js), [projects.py](../../tools/viewer/projects.py),
  [compiler.py](../../tools/editor/compiler.py)). The keys and their values are one table on each side
  ([missions.py](../../tools/viewer/missions.py) `MAP_INFO`, [missions.js](../../tools/viewer/web/missions.js)),
  pinned by `twin_constants.json`. The contract is in
  [editor-contracts.md](../../research/editor-contracts.md).
- **The compiler** reads it into its report ([mission_edits.py](../../tools/editor/mission_edits.py)
  `map_info_mark`); a key or value it doesn't know is left out whole (`lwr-map-info`) and the rest builds. Nothing in
  the map changes, so the spec is the same with or without it.
- **The Build** writes the variant's lines into the manifest's `config.mapInfo` and the package's README
  ([build.py](../../tools/editor/build.py)). A project whose one change is its map info builds, with the lighting
  unchanged.
- **A map pack's card** carries the lines in a `MapInfo` array ([pack_card.py](../../tools/upk/pack_card.py): parsed,
  written, read back; `info_warnings` names a key or value LWR doesn't know). The card is still format 1, and the
  array is written only when a map has a line, so every card without one is byte for byte what it was.
  [manager.py](../../tools/viewer/manager.py) puts the lines on the card and into `pack.json`, and both of the
  pack's READMEs say them in words.
- **A campaign install made by the editor** writes `DefaultMaps.ini`'s records alone. For a build with map info on a
  Long War Rebalance install it now says so in its warnings ([installs.py](../../tools/viewer/installs.py)).

Checked: new tests for the card (`test_map_info_lines_go_through_a_card` and two more in
[test_pack_card.py](../../tools/upk/tests/test_pack_card.py)), the compiler, the Build, the project store, the pack
export and the campaign install's warning, the twin table, and the page's rules
([missions_test.mjs](../../tools/viewer/tests/missions_test.mjs)). `python tools/run_tests.py viewer editor upk lab
repo node` passes. On a test server with URB_Bar: the section set, undone, redone, reset, saved and opened again
(schema 6); the saved project built with the real Build (its manifest and README hold the two lines, lighting
unchanged); a pack exported from it, whose card read back holds both lines beside its map and landing lines. The
browser smoke's `map-settings` check covers the section. Beta 17's script has the names the card writes (`MapInfo`,
`Key`, `Value`, in its XComMutator package), read from the package's name table.

Known gaps:

- Not seen in the game: no pack with map info has been loaded by beta 17 (`Mutate LWRMapTest Info <map>` would show
  the values it took).
- A campaign install made by the editor does not write the lines (they would go in the game's `DefaultMaps.ini`,
  section `[XComMutator.LWRMapInfo]`); only a pack carries them.
- The window does not show the value a replaced vanilla map has in the game's `DefaultMaps.ini`, which a map with
  nothing set takes in a pack that replaces it.
- A `Yes` for Hold the Line can only be written by hand in the project file; the window keeps it but can't set it.
- The user guide does not have the section yet.
