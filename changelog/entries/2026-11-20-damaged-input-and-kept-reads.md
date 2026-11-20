### One unreadable record no longer ends a map's export, and the server's smaller reads say why and are not kept failed

Review findings 50 (the items for the server, the exporter and the package readers) and 31 (area lights at export,
the compiler's message, the script defaults).

- **Damaged packages**: [lzo1x](../../tools/upk/lzo1x.py) raises `ValueError` for a block cut short (it raised
  `IndexError`, which no guard expected) and for one that gives another length than its table says.
  [export.py](../../tools/viewer/export.py)'s per-piece guards (components, textures, particle meshes, piece flags,
  streamed packages) catch one set of errors (`UNREADABLE`), and the readers that were outside any guard (buildings,
  lights and their metadata, area lights, landings, effect carriers, script defaults, effects and their drawings,
  cursor volumes, the level's records) go through `Exporter.guarded`: a failure is a diagnostic and an empty answer,
  not the end of the whole export. A damaged or modded install would end it; valid game files never did.
- **`Package.cls`** names an import's own class ([package.py](../../tools/viewer/package.py)); a negative index read
  an unrelated export's class through the list's wrap. 0 is 'None', and a reference outside both tables a
  `FormatError`.
- **`upkinfo.load`** ([upkinfo.py](../../tools/upk/upkinfo.py)) takes `raw` as an argument instead of reading
  `--raw` from whatever program's command line it runs in, puts its folder on `sys.path` once when it loads instead of
  at every compressed package (the server's path grew as it ran), and checks a whole-compressed package's blocks and
  total.
- **`viewer.py export`** defaults to `--scope map` ([viewer.py](../../tools/viewer/viewer.py)): the old default, the
  piece study, worked on URB_Bar only and died with a bare `KeyError` on any other map.
- **A level's actor list** has one reader ([scene_metadata.level_list](../../tools/viewer/scene_metadata.py), which
  [effects_metadata](../../tools/viewer/effects_metadata.py)'s now calls) and one answer when it can't be read: every
  actor counts as listed. Before, the effects carried by pieces took "none listed" while the effects' own records took
  "all listed", so one scene.json disagreed with itself; the spawn points' records still say `listed: null` (not read).
- **The build queue's file of another version** ([buildqueue.py](../../tools/viewer/buildqueue.py) `_load`) is told by
  its `schemaVersion`, not by the words of the error: a newer editor's queue is left for it, and an older one is now
  restored from the last good copy.
- **scene.json** is written compact (the largest was 15.6 MB indented against 8.3 MB), with the previews and
  `scenes.json`; the map's SHA-256 is worked out once per export (the folder's name and the scene's source both take
  it). The export's version is unchanged.
- **Costs on each use**: the setup dialog's doctor starts PowerShell once per pwsh file, not at every opening
  ([settings.py](../../tools/viewer/settings.py); a failed start is not kept), and each pack zip in Map packs is read
  once per size and time ([packs.py](../../tools/viewer/packs.py)), not at every `packs.json`.
- **Area lights at export** (31): when `area_light_bindings` can't be imported, the export's diagnostics say why
  (source `area lights`), and the compiler's refusal ([compiler.light_metadata_problem](../../tools/editor/compiler.py))
  quotes it and says that exporting again gives the same until the editor's Python packages are mended, then how to
  export again. Before, it said only to export again, which could not help.
- **Script defaults** (31): [piece_flags.ScriptDefaults](../../tools/viewer/piece_flags.py) no longer keeps a failed
  read (a script package missing or held for a moment) as the answer for the server's life; it reads again next time.
- Checked: [test_bad_input.py](../../tools/upk/tests/test_bad_input.py) (new) cuts an LZO block at every length, gives
  a wrong length and a match before the start, and loads three damaged whole-compressed packages with and without
  `--raw` on the command line, with `sys.path` unchanged. [test_damaged_inputs.py](../../tools/viewer/tests/test_damaged_inputs.py)
  (new) exports a small package with four readers failing and the matcher missing (diagnostics, empty answers, the
  compiler's words), checks `Package.cls`, the level list's one answer, the script defaults read again, PowerShell
  started once and again for a changed file or after a failure, and a pack zip opened once and again when it changes.
  [test_buildqueue.py](../../tools/viewer/tests/test_buildqueue.py) restores an older queue file from its copy and
  leaves a newer one with a copy there. The viewer, upk, editor and bake suites pass.
