### The lighting samples' reader moved into lighting_records.py

Stage T-S0 of the game-likeness plan (the sun plan's S0), its first step: the reader of a Level's lighting samples for
moving things (its precomputed light volume, with the mark on each sample the dominant light does not reach) moves
out of the research census into the readers the Build uses, so that a later step of the baker may write the mark.
A move only: the function is the one it was.

- Where: `probe_volume` from [audit_lighting.py](../../tools/upk/audit_lighting.py) into
  [lighting_records.py](../../tools/upk/lighting_records.py); the census imports it from there.
- Checked: `tools/repo/moved_code.py` (probe_volume the same); new
  [test_lighting_records.py](../../tools/upk/tests/test_lighting_records.py): a volume read from made-up Level bytes
  (its place, its samples and how many are marked, the nearest samples to a point), a Level ending otherwise or with
  no volume refused, and the install's URB_Bar (1,743 samples, 222 marked, as the census of 6 November 2026 read);
  the `upk` and `repo` suites.
