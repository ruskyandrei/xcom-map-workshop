### The editor's install steps ask only about the game of the install they change

The editor's install and Play in game steps, the lab installer and the deploy tool refused whenever any `XComEW.exe`
ran, so with the user playing one copy nothing could be staged into another (the lab copy) for a hidden run (T-52).
They now ask whether the game of the install they change is running, told by the folder of its exe; a game whose
exe's path can't be read still counts as running.

- [procs.py](../../tools/viewer/procs.py): `exe_path(pid)`, and `running(image, folder)` counts only processes whose
  exe lies in that folder.
- [installs.py](../../tools/viewer/installs.py) `game_running(game)` and its callers there, in
  [play.py](../../tools/viewer/play.py) (the watch for the game a play started) and
  [prefab_tests.py](../../tools/viewer/prefab_tests.py); [deploy_fixture.py](../../tools/bake/deploy_fixture.py) and
  [lab_install.py](../../tools/lab/lab_install.py) the same.
- The tests' stand-ins take the install; [test_install_recovery.py](../../tools/viewer/tests/test_install_recovery.py)
  checks the folder rule. T-52 in the [findings register](../../research/findings-register.md) and the game-test skill
  say so.

Checked: the `viewer` and `lab` suites, the bake suite's deploy and lab-install tests.
