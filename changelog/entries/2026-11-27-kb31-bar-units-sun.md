### KB-31: on URB_Bar given another time of day, the sun does not shade the soldiers

A known bug, left open: on URB_Bar with the time of day set by a project, soldiers are not darker in a building's
shadow than in the sun, and in some sessions take no light from the sun at all; the map itself is lit right. It is not
the Build's shadows: Bar built with no bake and the moon's own direction does the same, while URB_CommercialStreet
shades its soldiers (F-203, EXP-100's follow-up runs). A follow-up plan reads the game's light environment code.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-31), [findings-register.md](../../research/findings-register.md)
  (F-203).
- Checked: the register's and the experiment's evidence; the repo suite.
- Known gaps: the cause is not settled.
