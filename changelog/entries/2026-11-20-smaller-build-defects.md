### Smaller build defects: an effect's values, a volume's delete, the family help, the quick build's light text, a bug report's file list

Review finding 44, five of its items.

- **An effect's values are built only with its record.** [compiler.py](../../tools/editor/compiler.py)
  `effect_override` put an effect's or a sound's values in the edit before it checked the record's pose and its follow
  rule, so a record reported left out for either still had its values built. They now go in once the record is known
  to build.
- **A volume's delete is left out, as its move and copy are.** A delete of a class with no family went straight to a
  hide, so a hand-edited delete of the level volume's mesh would have taken the map's tile data out with it. It is now
  the left-out row `not-a-piece` (`Compiler.not_a_piece`, shared with the move and copy refusal). The page cannot make
  one: its delete and Clear map skip hidden pieces, and every level volume's mesh is hidden.
- **`--family` help.** [build.py](../../tools/editor/build.py)'s usage line, notes and help, and the help of
  `viewer.py serve --family` ([viewer.py](../../tools/viewer/viewer.py), the help string only), named families the
  argument now refuses: its choices are the families still switched off, which today is only `other`.
- **A quick build's README says plainly what its lights do.** `QUICK_LIGHTS` said the result was "still to be
  confirmed (EXP-26 run 2)" and "not yet known"; it now says what is made and what is not baked, and the test that
  pinned the old words checks the plain ones.
- **A bug report's file list names what the zip holds.** [builds.py](../../tools/viewer/builds.py) `report` listed
  every candidate file, those over the 32 MB limit too; it now lists what was written, names the ones left out
  (`leftOut`, in the answer and in the zip's `report.json`), and takes its temporary file away if writing fails.
- Checked: [test_compiler_effects.py](../../tools/editor/tests/test_compiler_effects.py) (a record left out for a
  malformed pose and one for a pose on an effect that follows its piece build none of their values; failed before),
  [test_compiler_malformed.py](../../tools/editor/tests/test_compiler_malformed.py) (a volume's delete, move and copy
  are each left out, and nothing hides it), [test_build.py](../../tools/editor/tests/test_build.py) and
  [test_builds.py](../../tools/viewer/tests/test_builds.py) (a file over the limit is left out of the zip and of the
  list). The editor suite and the viewer's build tests pass.
- Left: `native_lights.py` still says in a note that whether the game lights an edited light live "is for EXP-26 run 2"
  (not a file of this change).
