### KB-27 and F-171: a 0.6.0 pack map that crashes a campaign's crashed-UFO mission start

A reported crash recorded, cause not found: a Crashed Raider mission on a 0.6.0 pack's `RaiderDeepWoodsFixed` crashes
the game from an LWR 3.00.00 beta 17 campaign, and starts on the game's own map with the pack taken out.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-27, with the workaround: take the pack out for that mission) and
  [findings-register.md](../../research/findings-register.md) (F-171).
- Checked: the crash logs and the two minidumps read (same engine function, a worker thread, after the checkpoint
  saves and LWR's UFO fog); the map's tiles read offline for F-156 (none) and its rebuild volume against the pack's
  other maps; hidden runs on the LWR v3 lab copy opening the mission directly on both maps (no crash, the variant
  twice); the campaign save with the pack out started the mission.
- Known gaps: not reproduced outside the campaign, and no build of the map from a later version tried.
