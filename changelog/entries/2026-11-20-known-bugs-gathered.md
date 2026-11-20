### The known bug register gathers the bugs recorded elsewhere, and two stale notes put right

The findings register, the experiment notes, the change ledger, the guides and release notes, the plans and the
code's comments were read for bugs recorded as known and not fixed; each candidate was checked against later fixes
and, where it could be, the code.

- **[KNOWN-BUGS.md](../../KNOWN-BUGS.md)** gains six entries:
  - KB-2: a baked Build of a map whose only change is a larger grid stops in the relight (T-37; `build.py`'s light
    stage still sends a resize alone to the relight);
  - KB-3: a moved or deleted piece leaves its separate light and decals behind (F-50, URB_Bar's fog pod);
  - KB-4: a pasted invisible floor wider than a tile sits by the ground under its first tile (Fit to ground mends it);
  - KB-5: a made ground Block a storey high can be climbed onto from its side (F-129);
  - KB-6: a soldier on a map roof that breaks away under them stays at roof height until ordered to move (T-47);
  - KB-7: a game started from a renamed copy of its exe is not seen as running (F-84).
- Left out after checking: a deleted ground plane's hole (F-46: EXP-78, through the Build, found it not walkable, as
  it should be); a stored 100-degree spot cone (the compiler builds it as 89.99); a replacing variant with no
  abduction (F-118, fixed); rooms whose walls were one actor (never in a release); a variant's export listing removed
  pieces (T-21: variants are not opened in the editor). Game and Long War limits stay in the known limits, and fixes
  not yet played in the findings register.
- **[tools/viewer/README.md](../../tools/viewer/README.md)**'s Current limits no longer says nothing reaches the game
  or that particles are not drawn, and points at the guide's known limits and the register; projects have their own
  folder.
- **[F-71](../../research/findings-register.md)** says what the Build warns now (`floor-headroom`, `slab-headroom`) and
  that its own case, a copy under one of the map's own pieces, is still not warned.
- Checked: the repo and release suites (links, nothing personal).
