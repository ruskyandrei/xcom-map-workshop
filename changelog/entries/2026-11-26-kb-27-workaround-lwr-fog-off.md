### KB-27: workarounds for an Ironman campaign

KB-27's workaround now says that an Ironman campaign always makes the mission-start save (the Autosave option only
governs other campaigns), and describes a copy of LWR's script package with the UFO fog's timer never started, so no
fog viewers are added and nothing races.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-27).
- Checked: `XComAutosaveMgr.AutosaveEnabled` read in the game's scripts (Ironman or the profile's Autosave); the
  patched package loads in the LWR v3 lab copy (a first try that returned at the function's first byte was refused at
  load, "Bad export index", because the loader parses every token), and a Crashed Raider mission on Deep Woods played
  to turn 2 with no `LWRUFOFOG` viewers and no new script warnings.
- Known gaps: not tried from a campaign's mission start, which no hidden run can reach.
