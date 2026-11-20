### The Build's drop-and-retry of untried pieces agrees with its compile step

Review finding 40. When the transplant or the copy stage fails with copies the Build has not made before in the edit
(the compiler's `untried`), [build.py](../../tools/editor/build.py) `drop_untried` takes them out and runs the stages
again. Three things in it disagreed with the rest of the Build:

- **One "has work" test.** Its "nothing left" test left out mission objects' moves and hides and the spawn rule, which
  the compile step counts, so dropped copies beside a mission object's move failed with "nothing of the project can
  be built". Both now ask `Build.has_work` (which also counts the missions list and the map picture, finding 39).
- **What depends on a dropped piece goes with it.** The glow lights a dropped copy would copy, or a dropped move would
  move, are taken out of the edit's area-light operations, and a break group a dropped copy was in that can't break
  together without it (the compiler's rule: two breakable pieces, or one and a cover block, or a made wall with a prop
  or a block) has its number taken off what is left and its map pieces out of `breakOriginals`
  (`unlinked_groups`; the `leftout` stage lists them as `groupsUnlinked`). Before, the group stayed and named a copy
  that was not made.
- **A retry only for a failure about those pieces.** Only the untried copies the failure names (its message, or the
  last 40 lines of the failing tool's log, where a traceback ends: `untried_named`) are dropped, and only then are the
  stages run again; a failure that names none is the build's own and is said at once, without a second full bake. A
  second failure that names another untried copy drops it too, and the `leftout` stage lists every one dropped.
- Checked: [test_build.py](../../tools/editor/tests/test_build.py): a failure naming none is not run again; of two
  untried copies the named one goes first with its glow light and its group, the other with the second failure; a
  mission object's move left keeps the build going; the two existing drop-and-retry tests now fail the way `_run`
  does (a log that names the piece). The editor suite passes.
