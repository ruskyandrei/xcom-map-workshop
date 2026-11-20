### A play's saves are put apart from a campaign's without losing either, and a stopped restore can be run again

Review finding 1. After a play, [playsaves.restore](../../tools/viewer/playsaves.py) moves a play's save off a slot it
wrote over and puts the campaign's save back from its copy. Two ways lost a save:

- With one occupied slot (or when the play wrote the highest of contiguous slots), the slot the play's save moved to
  was its own, and the copy going back then overwrote the play's save. The fresh slot is now worked out from every
  slot in use, the play's own and the copied ones included, and never names a file that is there.
- A restore that stopped part-way (a failed copy, a stopped server) and was run again went only by the slots still
  there, skipped the empty one and deleted the copies. Restoring is now driven by the copies as well: a copied
  save whose slot is empty goes back through a temporary file (not a `save<N>` name, so the game never lists it),
  checked against the hash recorded when it was copied, and a copy is deleted only once its slot holds its bytes. A
  copy that is not the save copied is kept and said so (`left`, also in
  [installs.restore_saves](../../tools/viewer/installs.py)' `lastSaves`).

A copied save whose slot is empty at the end of a play is put back even when the play did not empty it (a campaign
save deleted from the game's menu during the play comes back): keeping a campaign's save is the safer mistake.

Checked: [test_playsaves.py](../../tools/viewer/tests/test_playsaves.py) runs one slot, contiguous slots (the play on
the lowest and the highest) and gaps, then a restore stopped before and after each of its moves and copies, run again,
and compares both saves byte for byte. The first review's two cases fail on the old code. The play tests' save test
passes as before.
