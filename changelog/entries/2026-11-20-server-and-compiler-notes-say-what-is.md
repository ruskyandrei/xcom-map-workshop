### The server's and the compiler's own notes say what the code does; a queue's stop told only once saved

Review finding 64, the docstrings and comments of the server and the editor's Python, and the build queue bug one of
them hid.

- **The build queue's stop** ([buildqueue.py](../../tools/viewer/buildqueue.py)): its comment said the queue's build
  is told to stop "once the change is saved", but it was told before the save, so a stop that couldn't be saved left
  the queue put back as running while its build had been stopped. Now `_stopping` only notes the attempt, and the
  request (or Cancel in the build window) tells the builds runner after the save; one that can't be saved leaves the
  queue and its build running, as the queue then says. When the server closes, the build is stopped even if the
  queue can't be saved.
- **[compiler.py](../../tools/editor/compiler.py)**: it reads schema 1 to 4 (was "1 to 3"); the off-grid note no
  longer says the move is untested in the game; a record the compiler can't build is left out and named while an
  error stops the build (it said every such record was an error); lens flares build for every project since EXP-71
  and come from other maps too (it said they waited for their game check).
- **[projects.py](../../tools/viewer/projects.py)**: schema versions 1 to 4 open and a save writes 4 (it said another
  version is refused and there is no migration).
- **[installs.py](../../tools/viewer/installs.py)**: it names the two traces of the lab's deploy tools it knows (it
  said it knows nothing of the lab).
- **[viewer.py](../../tools/viewer/viewer.py)**: the module says what it is (not "Local original-map viewer"); the
  export route's comment is above the export route, and the prefab test route has its own; a port in use says to
  restart with `xcom_editor.cmd restart`, not Ctrl+C.
- Five modules' headers name their plans in `private/plans/done/` where they are now (gamedata, scene_metadata,
  spawnrules, squadrecords, squads).

Checked: [test_buildqueue.py](../../tools/viewer/tests/test_buildqueue.py) (a stop that can't be saved tells the
build nothing; saved, it does), the editor suite.
