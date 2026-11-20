### The look measurers ship in the release

A Build measures a made piece's donor afresh when the looks' catalogue lacks its look at the look's measurer version
([looks.py](../../tools/bake/looks.py) `resolve`). It reached the measurer through `importlib` by its name, which the
release's list of modules ([make_release.py](../../tools/release/make_release.py) `modules`, read from the imports)
cannot see: `wall_measure`, `slab_measure` and `ground_measure` were not in the zip, so in a release that case
stopped the Build on a missing module instead of measuring the donor. `looks.measurer` now imports each by name, so
all three ship. [wall_measure.py](../../tools/bake/wall_measure.py) no longer reaches the lab: its `install_package`
(used by the wall-look audit's research script) reads the settings' install, not the lab's path helper, and
`tools/lab` is off its path, so nothing shipped imports the lab.

Found by the refactor's stage 0 (the structure test's work over what ships); not met in a release build.
Checked: a new release test (`test_the_look_measurers_ship`) gives each measurer the looks name in the module list,
and failed before (none of the three was in it); the release and repo suites pass (the structure test included:
`wall_measure.py` stays at its ceiling); the bake suite's looks, measurers and catalogues tests pass;
`install_package('URB_Bar')` opens the settings' install's package.
