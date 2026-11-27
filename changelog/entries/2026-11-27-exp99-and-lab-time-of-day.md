### EXP-99 played, and the lab's staging carries a package's time of day

The game run of stage T-S3 (the time of day built without a bake) passed in the lab copy: the Build's day light, the sky
light on the soldiers, a save and load, and a turned light's direction on moving things all show in the game, while
the baked shadows stay the old light's until T-S4's baker traces them. F-200 is marked verified, and F-184's account of
URB_Bar's floor sheen is marked not settled (the sheen fades in the day Builds, so it is not a fixed texture).

The run found one gap in the lab's tools: staging a package in the lab copy made the test slot's record from the base
map's own, so a time-of-day package played with the map's old time (Night on Bar). The slot's record now takes the
package's `TimeOfDay` (its manifest's `config.timeOfDay`). The editor's Play in game, installs and map packs already
carried it.

- Where: [EXP-99](../../research/experiments/EXP-99-time-of-day-without-a-bake.md) (new),
  [findings-register.md](../../research/findings-register.md) (F-200, F-184),
  [deploy_fixture.py](../../tools/bake/deploy_fixture.py) (`plan_maps` and `deploy` take `time_of_day`),
  [lab_install.py](../../tools/lab/lab_install.py) (passes the manifest's).
- Checked: the game run itself (the note); [test_deploy.py](../../tools/bake/tests/test_deploy.py): the slot's record
  takes Day and Night when given, and the base map's time when not; the EXP-99 package's manifest names Day.
- Known gaps: none known.
