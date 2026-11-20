# XCOM Map Workshop (preview)

A map editor for **XCOM: Enemy Within**, made for **Long War Rebalance**. It opens one of the game's maps in your
browser, lets you change it, and builds the result into a new map, a *variant*, that the game plays like its own.
Nothing of the game's own files is changed.

- **Edit a map's pieces and lights:** move, turn, delete and copy them, and add pieces from any other map.
- **Shape the map:** prefabs you save and reuse, buildings whose floors cut away, invisible cover blocks, landing
  zones, a larger grid, or a cleared map to build on.
- **Pick the missions** a map is used for and place their objects.
- **Build** bakes the lighting for where things now stand. **Play in game** starts a battle on your variant straight
  away, with no campaign to start.

This is an early preview. Some edits don't build yet, and projects saved with it may not open in a later version.

## Download

Get the newest version from **[Releases](https://github.com/ruskyandrei/xcom-map-workshop/releases/latest)**:

- `XCOM-Map-Workshop-<version>-Setup.exe`: the installer (recommended). It asks for your game folder and makes Start
  menu shortcuts.
- `XCOM-Map-Workshop-<version>.zip`: the same, to unpack anywhere and start with `XCOM Map Workshop.cmd`.

Each release lists what is new and the files' SHA-256 checksums.

**Windows may warn you.** The installer isn't code-signed, so Windows SmartScreen says "Windows protected your PC".
Choose **More info**, then **Run anyway**.

## What you need

- Windows 10 or 11, 64-bit, and a browser: Edge, Chrome or Firefox.
- XCOM: Enemy Within with Long War Rebalance. Plain Enemy Within works too.
- Some free disk space: the editor keeps a copy of each map you open (about 50 to 200 MB each).

The editor is developed and tested mainly with Long War Rebalance. It is meant to work with plain Enemy Within too,
but that is less tested: reports from plain Enemy Within, or any setup other than Long War Rebalance, are welcome
(see [Reporting a problem](#reporting-a-problem)).

Everything else comes with it: its own Python and the packages it needs. It needs no internet connection and no
Unreal tools, and it contains nothing from the game: it reads your own install.

## The guide

The **user guide** explains every control on marked pictures, walks through typical tasks, and says what the editor
can't do yet.

- **[Read it online](https://ruskyandrei.github.io/xcom-map-workshop/)**: the guide as it is in this repository,
  which can be ahead of the last release.
- Every release carries its own as **User Guide.html**: Setup offers to open it, and it is in the Start menu and in
  the editor's **?** menu.
- Its source is [tools/release/guide/guide.html](tools/release/guide/guide.html).
- [GETTING-STARTED.md](tools/release/GETTING-STARTED.md) covers setting up, building, playing and the known limits.
  A release carries it as its `README.md`.

## Reporting a problem

Open an issue on the **[Issues](https://github.com/ruskyandrei/xcom-map-workshop/issues)** tab. Say which version you
have (it is in the editor's **?** menu). After a build, **Save a bug report** in the build window makes a zip of the
project and the build's logs: attach it, with what you did and what you saw (a screenshot helps).

## This repository

It holds the editor's source, the tools around it and the research behind it. The source is here from the version
after 0.5.2; the tags up to v0.5.2 mark releases made before it was public.

| Folder | What it holds |
| --- | --- |
| `tools/viewer/` | The editor: the server, the exporter that reads the game's maps, the three.js page (`web/`), projects, prefabs and settings ([README](tools/viewer/README.md)). |
| `tools/editor/` | The compiler and the Build: a project into a variant package, the edit made in the map itself. |
| `tools/bake/` | Our lighting baker and the code that copies, moves and removes pieces inside a map. |
| `tools/upk/` | Readers and writers for the game's packages. |
| `tools/release/` | What makes a release: the installer and zip, the guide, the release notes. |
| `tools/lab/`, `tools/patch/`, `tools/re/`, `tools/udk/`, `unrealscript/` | The tools of the experiments: driving the game in a lab copy, patch maps made with the UDK, reading the game's executable. The editor's Build does not need them. |
| `tools/repo/` | Checks that keep the repository free of anything personal or private. |
| `research/` | What was found out about the game and how: the [findings register](research/findings-register.md), the experiments (`experiments/EXP-*.md`), the [native code notes](research/native-code-notes.md) and the first [research summary](research/mission-editor-research.md). |
| [CHANGELOG.md](CHANGELOG.md) | The change ledger's index: one month file per month in `changelog/`, newest first, and one file per change since the last release in `changelog/entries/`, each with how it was checked. |

No game files, or anything made from them, are in the repository. Neither are the source files of other modding
projects that the research read: [source-manifest.json](research/evidence/upstream/source-manifest.json) names where
each one is.

## Working from a clone

1. Python 3.12, then `pip install -r tools/viewer/requirements.txt` (numpy, SciPy, Pillow, embreex).
2. `python tools/viewer/setup_vendor.py` fetches the page's three.js, pinned and checked.
3. `python tools/viewer/viewer.py settings` shows the settings, which hold every folder the editor uses; set **game**
   to your Steam `common` folder or the game's own folder. `python tools/viewer/viewer.py doctor` checks them.
4. `xcom_editor.cmd` starts the editor on port 8768. A map is exported from your install the first time it is opened.

`python -B tools/run_tests.py` runs the test suites and prints each failure with its traceback; name suites to run
only those (`run_tests.py viewer editor`). The bake suite takes about six minutes, and the suites that read the
game's maps need an install.

`python tools/release/make_release.py` builds a release; the installer needs Inno Setup 6 or 7.

## Licence

The editor is under the MIT licence ([LICENSE](LICENSE)). It bundles Python, numpy, SciPy, Pillow, embreex and
three.js, each under its own licence (`THIRD-PARTY-NOTICES.txt` in each release).

XCOM Map Workshop is a fan-made tool, not affiliated with or endorsed by Firaxis Games or 2K. XCOM is their trademark.
