### F-143: what a fix for the cover block that outlives its made wall has to get round

[F-143](../../research/findings-register.md) (EXP-88: a cover block grouped with a made wall keeps its cover when
the wall goes) gains what the game's decompiled script says. An invincible block could succumb to the columns' clear
damage, but soldiers' projectiles, dying units, pushing pawns, the kinetic strike and destroyed props send the same
damage class, so the block could then go under ordinary fire while its wall stands. A fracturing wall cannot name the
block in `AffectedChildren` (only props carry it). The entry names a way round both (a collision-less hidden helper
prop listed in the wall's columns that names the block), not tried. No code changed.

Checked: the repo suite.
