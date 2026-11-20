### The map pack test's first-mission names come from the installer (editor refactor, stage B7)

[pack_test.py](../../tools/lab/pack_test.py), the lab's hands for the map pack game test (EXP-85), kept its own copy
of the two display names a new campaign's first mission asks for (`INTRO_SLOTS`: LWR's
`URB_CommercialAlley_EWI (Commercial Alley Redux) |0` and plain EW's, the same without ` |0`). Its `intro_record`
(the record the first-mission test card copies) now takes them from
[installs.py](../../tools/viewer/installs.py) `FIRST_MISSION`, the one home its notes already named, and the copy is
gone (review finding 55). The names are the same, so the test card is the same.

The refactor plan named `outputnames.INTROS` as the home. That table holds the intro cinematics a map streams
(`CIN_DropshipIntros` and the others), not display names: no record's display name is one of them, so the test card
could not have been made from it.

Checked: the lab suite. [test_pack_test.py](../../tools/lab/tests/test_pack_test.py) gains a test that the first
mission's record is found under each name `installs.FIRST_MISSIONS` lists, and not under another.
