### The wall audit records each wall's yaw: the game has no turned walls

The fracturing walls' audit now records each placed wall's yaw, and for one turned off the quarter turns its columns'
world boxes, to find the game's own rule for a wall at a free angle (the custom geometry improvements plan, 4.6). Run
over every map the install lists: 644 placed walls, all on quarter turns, so there is no such rule to take (F-145, the
findings register); a game run decides.

- [frac-wall-audit.py](../../research/evidence/frac-wall-audit.py): `yaw` per placed wall, `columnBoxes` for turned
  ones, the summary's `turnedWalls`.
- [findings-register.md](../../research/findings-register.md): F-145.

Checked: the audit run whole (no game file written).
