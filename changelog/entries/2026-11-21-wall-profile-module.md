### A made wall's profile work in a module of its own

The two functions that take height out of a measured wall look's outline (`storey_cut`, `lowered`) and their two
constants move, unchanged, out of the wall generator into a module of their own, where the made walls' free form
(the custom geometry improvements plan, stage 2) will resize a look's outline to a wall's faces and height. The wall
generator imports them, so it builds as before.

- [wall_profile.py](../../tools/bake/wall_profile.py) (new): `storey_cut`, `lowered`, `STOREY_HEIGHT`, `RUN_LEFT`.
- [frac_wall.py](../../tools/bake/frac_wall.py) imports them.

Checked: `tools/repo/moved_code.py` (both functions the same), `run_tests.py bake -k frac_wall -k made_split -k
wall_measure` (the old walls' hashes unchanged).
