### Copies sized to what they read, played (EXP-91: F-151 verified); a quicksave crash on the reported map in both builds (F-156, KB-17)

The reported city project built with and without the smaller built maps change, played in hidden runs on the lab copy
([EXP-91](../../research/experiments/EXP-91-smaller-built-maps.md)): the map with the change loads, its copies look as
before near and at the far zoom, and the battle holds 275 MiB less in textures (220 against 495 MiB) and about
300 MiB less private memory. [F-151](../../research/findings-register.md) is verified.

A quicksave crashes the game on that map in both builds, in the checkpoint's serialisation, while the game's own
CLrgScout_City saves and loads in the same setup: [F-156](../../research/findings-register.md), open, and
[KNOWN-BUGS.md](../../KNOWN-BUGS.md) KB-17.

The [game-test skill](../../.claude/skills/game-test/SKILL.md) says that every session command takes `--game` while
another copy is the one Steam runs (else they read that copy's log), and that staging then goes through
`lab_install.install` with the lab copy named: the command-line tools stage into the folder Steam runs and take any
copy with the marker for the lab copy.

Checked: the runs' logs, `ListTextures` lists and shots, read for this note; the repo suite. Known gaps: the save
crash's cause; whether other built maps crash on a quicksave.
