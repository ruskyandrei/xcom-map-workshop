### The game folder's layout spelled in one place

Where an Enemy Within install keeps its files (`<game>/XEW/XComGame/CookedPCConsole` for its packages,
`<game>/XEW/XComGame/Config` for its config, `<game>/XComGame/CookedPCConsole` for the base game's packages) was
written out in about twenty places of the server, each with a helper of its own (follow-ups item 6.8).
[settings.py](../../tools/viewer/settings.py) now holds it: `ew_folder`, `game_cooked`, `game_config`,
`cooked_folders` (the EW packages, then the base game's) and `COOKED`, the folder's name, which a Build's package and
a map pack hold too. [installs.py](../../tools/viewer/installs.py) (`config`, `cooked`, the manifest's file names, a
lab file's backup folder), [library.py](../../tools/viewer/library.py) (`cooked_of`),
[gamedata.py](../../tools/viewer/gamedata.py), [viewer.py](../../tools/viewer/viewer.py),
[maplist.py](../../tools/viewer/maplist.py) (`package_of`), [export.py](../../tools/viewer/export.py)
(`stream_package`, the other reader that also looks in the base game's packages),
[manager.py](../../tools/viewer/manager.py) (a pack's zip), [gamelaunch.py](../../tools/viewer/gamelaunch.py),
[playsaves.py](../../tools/viewer/playsaves.py), [spawnrules.py](../../tools/viewer/spawnrules.py) and the editor's
[game_files.py](../../tools/editor/game_files.py) use them.

Nothing changes. Checked: the new [test_game_layout.py](../../tools/viewer/tests/test_game_layout.py) holds the
helpers' paths, finds a map in the EW packages before the base game's (`maplist.package_of`, `export.stream_package`,
a str or a path) and scans every module the release ships: CookedPCConsole in a string of code (no blank in it) is in
`settings.py` alone, words for the user aside; `build_outputs.py` record against the start commit: equal (11
inputs); the editor suite (379) and the viewer's map list, game data, library, streams, play saves, spawn rules,
launch, pack export and install recovery tests pass.

Known gap: the Build's own files still spell the folder in code, counted by the scan so none is added
(`build.py` 8: the base map's and the streams' paths through `lwr_file`, the package's folder and its manifest's
names; `prefab_stage.py` 1; `prefab_tests.py` 2). `Localization` and `SaveData` are found through `ew_folder`; the
install's `XEW\Binaries` and `XEW\Engine\Config` are still written where they are used.
