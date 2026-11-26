### KB-27 and F-171: the cause, LWR's UFO fog racing the mission-start save, and the start rebuild's part

The crash recorded as KB-27 is a race between the campaign's mission-start save, which writes the world data's
per-viewer sight maps on a worker thread, and LWR's UFO fog, which adds 76 viewers about 0.2 s after the save begins.
A pack map's large start-up rebuild (11,771 to 14,216 tiles against the game map's 1,386) keeps the save from
finishing first.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-27's cause and title) and
  [findings-register.md](../../research/findings-register.md) (F-171).
- Checked: a third crash with the pack built by 0.7.0; the three minidumps disassembled (`0x797D50` and its one
  caller `0xCF9660`, the per-viewer maps at +0x8124); the save, fog and rebuild times read from every campaign UFO
  mission in the logs, the game's own Deep Woods among them; hidden runs on the LWR v3 lab copy timing the start
  rebuild on both maps and on the variant with its volumes taken out; every built map's rebuild volumes measured
  against their boxes.
- Known gaps: the variant without volumes has not been tried from the campaign save; LWR's guard is theirs to make;
  the Build's smaller rebuilds are planned, not built.
