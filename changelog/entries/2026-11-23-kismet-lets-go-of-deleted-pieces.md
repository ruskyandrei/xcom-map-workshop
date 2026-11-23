### The Build takes deleted pieces out of the map's Kismet

The user, of the reported boat's Build window (a cleared map, its red rows about the hive's script): "Everything was
deleted, I don't care about these scripts doing anything, why can't we just delete them too?"

- **The Build empties the map's Kismet references to every piece the project deletes**
  ([kismet_cut.py](../../tools/bake/kismet_cut.py), run after the hides in
  [native_copy.py](../../tools/bake/native_copy.py)): a variable's object, an event's originator or an op's own
  reference set to None, an object list losing the entry, and an event left with no originator switched off (as the
  clear does for the triggers it takes out). What reads the references is the export's own walk
  (`scene_metadata.kismet_walk`); the written map is read back (`verify`) and the manifest records it (`kismetCuts`).
  On the boat: 14 deleted props let go of, 53 references emptied.
- **The compiler lists them** (the spec's `kismetCuts`, through [native_edit.py](../../tools/editor/native_edit.py)) and
  says a deleted piece the script names in a note ([compiler.py](../../tools/editor/compiler.py) `kismet_named`): the
  script then acts on nothing in its place, and a copy of the piece is like any other. A moved piece keeps its warning
  (its copy misses the script); a deleted one the script waits on keeps it on a map as it is, and is a note on a cleared
  one. A spawn point the script names still stays (a spawn list left empty could break the spawn if the script ran),
  said in a note on a cleared map ([spawn_edits.py](../../tools/editor/spawn_edits.py)). The boat's Build now shows no
  red rows.
- [ARCHITECTURE.md](../../ARCHITECTURE.md) and F-63 in the [findings register](../../research/findings-register.md)
  say so.

Checked: [test_kismet_cut.py](../../tools/bake/tests/test_kismet_cut.py) (URB_Bar's grounded Skyranger, drop zone and
a trigger volume let go of, the event switched off, everything else the Kismet holds kept, read back);
[test_compiler.py](../../tools/editor/tests/test_compiler.py) (the lane, the notes, a moved piece, a waited-on piece on a
map as it is and a cleared one, the kept spawn point on a cleared map); the lane test of
[test_native_copy.py](../../tools/bake/tests/test_native_copy.py); every suite. In the game (hidden run, the lab copy):
the boat built quick with the cut loads and plays two full turn cycles with aliens (the alien turn runs one of the
emptied actions), and the log names no Kismet action or variable after the load.
