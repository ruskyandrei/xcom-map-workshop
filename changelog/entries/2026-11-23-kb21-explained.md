### KB-21 explained (a meld container, not the Build); patch levels' rebuild volumes recorded as KB-22; KB-20 out

- **KB-21 is out of the register: it was not the editor.** EXP-95's lost corner (53, 40, 0) was reworked at the
  battle's start by a meld container Long War placed at random on tile (55, 39, 0): its `XComMeldSpawnMutator` puts the
  containers at random floor places, and each container queues the tiles of its place ± 144 across and ± 64 up as
  it spawns, which never writes diagonal cover back. Read from EXP-95's quicksave against the built map tile by tile
  (the tiles with a bit only a map's full build writes show the reworked set exactly: 61 of 607, every one taken by the
  volumes' boxes by F-150's rule bar this one, none of the 546 kept), the run's log (three rebuilds before the
  volumes', one as each container is applied) and the mutator's source. Findings register
  [F-162](../../research/findings-register.md), [EXP-95](../../research/experiments/EXP-95-diagonal-marks.md).
- The guide's in-game limits say that under Long War a meld canister next to a marked tile takes its diagonal cover
  for that mission, as a blast does.
- **KB-22 in** ([KNOWN-BUGS.md](../../KNOWN-BUGS.md)): the map's streamed patch levels (the farm's `patch_farm`) have
  rebuild volumes of their own that rework their tiles at every battle's start; the Build's reading of the rebuild
  (`native_copy.rebuild_order`, its docstring now says what it leaves out) and the export don't place them, so a mark
  inside one gets no cover and nothing warns. Left for a change of its own (the export's patch volumes, then the
  Build's reading and a warning).
- **KB-20 out**: the Build's finder is gone (diagonal cover only where a mark is), and the branch that took it out is
  merged with this. The plan moves to `private/plans/done`; the code's references to it say so.
- Checked: the full suites before the merge.
