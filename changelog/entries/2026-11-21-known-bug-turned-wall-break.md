### Known bug KB-8: a made wall at a free angle breaks away from where it is hit

[KNOWN-BUGS.md](../../KNOWN-BUGS.md) gains KB-8: on the custom geometry branch a made wall turned off the quarter
turns broke in its middle, not where the grenade hit it (EXP-90 run 1, check 3; finding F-145 in the
[findings register](../../research/findings-register.md)). The likely cause is the fracture columns' rule, cut along
the wall's longer world axis rather than its own line; a fix and the same check again are left.

Checked: the run's pictures (the corner from above before and after the grenade) against its report; the `repo`
suite.
