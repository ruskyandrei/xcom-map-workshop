### Keyword-only parameters where a swap would go unnoticed

Some of the server's functions took long lists of arguments by position, where two of the same kind could change
places without an error (follow-ups item 6.10: the queue's token and attempt id, a unit's armour and sidearm).

- [builds.py](../../tools/viewer/builds.py) `start_queued` takes everything after the document by name, and
  [buildqueue.py](../../tools/viewer/buildqueue.py), its caller, names them; `BuildRunner._start` takes its
  options after the document, the command and `quick` by name, as every caller gave them already.
- [area_light_bindings.py](../../tools/viewer/area_light_bindings.py) `candidate` takes its seven measurements by
  name after the piece and the light, and its caller names them.
- [squadrecords.py](../../tools/viewer/squadrecords.py) `_unit` takes a unit's fields by name; the six default
  squaddies (`DEFAULT_UNITS`) are records with named fields, and the unit templates and
  [test_squad_play.py](../../tools/viewer/tests/test_squad_play.py) name theirs.
- [play.py](../../tools/viewer/play.py) `Player.__init__` takes its options after the settings, the builds, the
  catalogue and the projects by name, and [effects_metadata.py](../../tools/viewer/effects_metadata.py) `describe`
  everything after the package, the export's call ([export.py](../../tools/viewer/export.py)) naming the four it gave
  by position. `viewer.Handler.__init__` took its options by name already (after `*args`). None is made a record.

Nothing changes. Checked: the default squad's document is the same (its SHA-256 before and after); the viewer's squad,
area light, effects metadata, effects library, build, build queue, play and prefab test tests pass (182 tests).
