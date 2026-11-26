### KB-27: the game's own Deep Woods crashed the same way, so the race is LWR's on any UFO map

KB-27 was a pack map's crash; the same campaign save then crashed on the game's own `CLrgScout_DeepWoods` with no pack
installed, by the same fault path, after starting once the night before. The entry now says the race is LWR's on any
UFO crash site and that a built map with a large start-up rebuild makes it certain; its workaround adds launching
again on the game's map.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-27) and [findings-register.md](../../research/findings-register.md)
  (F-171).
- Checked: the crash's log (no map pack, 1,528 tiles queued, the fog 0.22 s after the save began) and its minidump
  (memcpy <- 0x8DE863 <- 0x797D69 <- 0xCF986C, as the pack map's).
- Known gaps: the fix is LWR's; the Build's smaller start rebuilds are planned, not built.
