### LWR 3.00.00 beta 18: the editor's map packs are not read (KB-28); KB-27 notes beta 18's fog change

LWR 3.00.00 beta 18 reads map packs only from `CookedPCConsole\LWRMapPacks\<pack>\XComLWRMapPacks.ini` and no longer
reads pack cards, so packs the editor exports (and its Install.cmd installs) do nothing there. The bug is registered
with its workaround (the pack's `pack.json` card lines written into that ini, the folder moved), and the finding
records what else beta 18 changes for us: one installer for the whole of Long War, a patched exe that the pack
folders need, and a new startup package in DefaultEngine.ini. KB-27 gains a line: beta 18's `LWRebalance.u` adds
what by its names is a wait for a save in progress before the UFO fog, and the fog-off copy no longer applies.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-28 added, KB-27 extended) and
  [findings-register.md](../../research/findings-register.md) (F-172).
- Checked: beta 18 installed into an empty stand-in and laid over the LWR v3 lab copy; a hidden run there showed
  "LWR v3.00.00 Beta 18" and read a 39-map pack moved into `LWRMapPacks` with its lines in an
  `XComLWRMapPacks.ini` (90 map lines, 43 pictures, 206 landing zones, none missing).
- Known gaps: the editor's pack export and Install.cmd are not changed yet; beta 18's fog wait is read from names
  only, not seen in a campaign.
