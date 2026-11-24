### A building that stays lists no emitter a clear took out

Found reading the Build for the clear-by-parts plan's game runs: the building floors' lists of their emitters
(`m_aCachedEmitters`, which the cutaway hides and shows with the floor) dropped the effects the project deleted itself,
but not the emitters the clear took out of the level. A clear of every part takes the buildings too, so only a map's
building edited in place kept such names; a clear of the effects alone keeps every building, and each would have
listed emitters no longer in the level (URB_Bar's first building, five).

- The Build's floor lists now take the clear's emitters out with the deleted ones
  ([native_copy.py](../../tools/bake/native_copy.py) `floors_and_cursors`, read from clear_level's record).

Checked: [test_native_effects.py](../../tools/bake/tests/test_native_effects.py) (URB_Bar built with its effects alone
cleared: the buildings stay, no floor lists an emitter the clear took; the test fails without the fix); the Build
tests of the effects, the clear, the flags and the copies.
