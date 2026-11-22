### Two bugs from a user's report recorded: terror civilians in the air, a black patch on a baked copy (F-157, F-158, KB-18, KB-19)

A user's map pack (a CLrgScout_City variant with its UFO deleted and an EXALT helipad in its place, built with
0.6.0 and baked) showed civilians starting in the air beside the helipad, and a dark patch on the floor by it. Both
were read offline; nothing in the tools changed.

- [findings-register.md](../../research/findings-register.md) F-157: the game places terror civilians on the map's
  stored cover points (within 960 units of a pod) in `InitPlayers`, before `DoWorldDataRebuild`; a Build leaves a
  deleted piece's tiles, floors and cover points, for that rebuild (`native_copy.hide_tiles`). The reported build
  keeps 75 cover points on the UFO's floors above the ground (z 64 by the helipad, z 414 to 451 on its roof) and 20
  under the helipad.
- F-158: the patch is the Build's copy of the map's own floor `XComLevelActor_526`; its black texels are those buried
  under a staircase where the original stands, and `relight.py` keeps the original's bake for a texel buried at
  either place. Two more such patches lie on the same copy by the map's east edge.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-18 and KB-19, with their workarounds.

Checked: read from the game's decompiled scripts (`XGBattle`, `XGBattle_SP`, `XGAIPlayer_Animal`), the built map's
tile data and lightmaps beside the base map's (`world_grid`, `native_copy.rebuild_order`, `lightmap_texels`). Not
played in the game.

Known gaps: neither is fixed; each finding names the fix to try.
