### The copy tool's build reads and writes its state, and joins its steps

Review finding 51, refactor stage B4, after its seven cuts: `build`'s remaining lines copied the state's fields into
locals before each step and back after it, and kept its results at the end with `BuildState.keep`.

- [native_copy.py](../../tools/bake/native_copy.py): `build`'s lines read the inputs and results from the state and
  write each result to its field where they make it (`st.made`, `st.hidden`, `st.effect_record`...), so the copying
  lines (26 statements) and the `keep` call at the end go: it kept every result under the field it already had.
  What `build` alone uses stays local (the map read, `p`, and its growing writer, `g`; the lanes' clones and deletes
  before they are joined; the manifest). `build` is now the light edits, the steps in their order (`clone_copies`,
  the cover blocks, `fracturing_copies`, the break groups and the hides, the effects' lanes, the vans' buildings,
  `wall_columns`, `edit_buildings`, `edits_in_place`, `floors_and_cursors`, `write_and_verify`) and the record.
- `BuildState.keep` goes; the fields it made by first use are named in `BuildState` with the step that fills them
  (`groups`, `children` and `hidden_buildings`, which `build` makes; `sections` and `copy_members`, which
  `manifest_parts` keeps for the relight command).

Checked: `build`'s syntax tree is the one before with each of its locals of the state renamed to the state's field
(`state` to `light_state`), the copying statements and the `keep` call taken out, and one statement left half a
copy made plain (`st.g = g`), and nothing else (a scratch check at the syntax tree, which also refuses a renamed
loop variable); `moved_code.py` on every other function of the file: the same; no name left undefined; the ten
Builds equal to the code before; the bake tests of native copies, made walls, buildings, flags, the clear and
effects.
