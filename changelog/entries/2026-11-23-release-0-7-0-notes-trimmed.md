### Release 0.7.0's notes: four items taken out

At the user's word ("remove these"), after the notes were shown in full. Four lines are taken out of
[0.7.0.md](../../tools/release/notes/0.7.0.md):

- Upgrading: the note that a map pack exported by 0.6.0 or earlier names folders of the computer that made it.
- New features: how a drawn wall in a tile row plays, and which tiles a drawn floor is floor on.
- Changes: Play in game under names of its own, and every map holding its baked lighting inside it.

The notes are not inside the zip or the installer, so neither is built again: the SHA-256s stand. The guide's New in
0.7.0 table and the README's list, which are inside them, still name a drawn wall's play and the play names.

Checked: `python tools/run_tests.py repo release`. Not published (ask first).
