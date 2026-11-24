### KB-24 fixed: the lights a clear takes out leave the bake too

The user, of KB-24: "yes go ahead and try the fix". A clear of the lights takes out by their class the lights the
editor can't edit (on four maps, 39 that light only their own channels, baked into pieces), and the bake was never told:
their light stayed on the pieces that stay. Trying the fix found a second gap: a lights clear without light records
didn't relight at all.

- **The relight takes them away**: the Build passes every enabled static light the clear took out
  ([native_copy.py](../../tools/bake/native_copy.py) `cleared_lights`, `relight_command`) as a removed light, which
  the relight takes away as it does a deleted one; more than 100 go in a file
  ([relight.py](../../tools/bake/relight.py) `--remove-light-list`). Toggleable lights, lit live, and area lights,
  which go with their pieces, are not passed.
- **A lights clear relights** ([build.py](../../tools/editor/build.py) `clears_lights`): the Build no longer takes it for
  an edit that changes no light, which kept the original lightmaps when no light was deleted by a record.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-24 taken out. [F-166](../../research/findings-register.md) fixed, with the
  check.

Checked: [test_clear_level.py](../../tools/bake/tests/test_clear_level.py) (a lights clear of URB_SlaughterhouseA names
SpotLight_54 for the relight, no toggleable or area light; nothing for another part); URB_SlaughterhouseA built baked
with its lights cleared: all 139 baked lights taken away by the relight, 588 pieces relit in 82 s (before the second
fix: none, lighting unchanged); six of its pieces nearest SpotLight_54 relit with and without it taken away: the two it
lights most darker with it gone (median flat light 0.040 against 0.066, 0.076 against 0.090), the rest within 1%. The
editor and bake tests of the Build, the clear and the relight.

Known gaps: not seen in the game.
