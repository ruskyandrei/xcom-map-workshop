### KB-27: the fog-off workaround works in the campaign; the start rebuild's part is not settled

With LWR's UFO fog timer never started, the pack map's Crashed Raider mission, which had crashed four times out of
four, started in the Ironman campaign. That confirms the race as the cause. The same start's save took 0.16 s with
14,149 tiles queued, so the entry and the finding no longer say a big start rebuild slows the save; why the pack map
lost every time is left open.

- Where: [KNOWN-BUGS.md](../../KNOWN-BUGS.md) (KB-27) and [findings-register.md](../../research/findings-register.md)
  (F-171).
- Checked: the campaign's launch log (the pack map's mission start, the checkpoint finished at +2.65 s, no
  `LWRUFOFOG` viewers, the mission started).
- Known gaps: the fix is LWR's; why the pack map's starts lost the race every time.
