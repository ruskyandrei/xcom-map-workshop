### A diagonal cover tile written by the Build played in the game

Stage C3 of the diagonal cover plan, for D1's written tiles. Nothing in the tools changes.

- [findings-register.md](../../research/findings-register.md): F-149's game run of a written tile (CSmallScout_Farm,
  a barrel copied beside the corner (39, 12, 0)): soldiers on the corner read cover 50 with the diagonal bit, the
  written cover, four times; the saves hold the written data through the battle's start.

Checked: a hidden game run (LWR) and its two saves read with
[diagonal-cover.py](../../research/evidence/diagonal-cover.py).

Known gaps: whether units walk round the barrel was not read (an alien stood on the tile past it).
