# XCOM Map Workshop (preview)

A map editor for **XCOM: Enemy Within**, made for **Long War Rebalance**. It opens one of the game's maps in your
browser, lets you move, turn, delete and copy its pieces and lights, and builds the result into a new map, a
*variant*, with its lighting baked, that the game plays like its own. **Play in game** starts the game straight in a
battle on your variant, with no campaign to start and nothing of the game's own changed.

This is an early preview for smaller edits to existing maps. Some edits don't build yet, and projects saved with it
may not open in a later version.

This repository holds the editor's source, the research behind it and the releases. The source is here from the
version after 0.5.2: the tags up to v0.5.2 mark releases made before it was public.

## Download

Get the newest version from **[Releases](https://github.com/ruskyandrei/xcom-map-workshop/releases/latest)**:

- `XCOM-Map-Workshop-<version>-Setup.exe`: the installer (recommended). It asks for your game folder and makes Start
  menu shortcuts.
- `XCOM-Map-Workshop-<version>.zip`: the same, to unpack anywhere and start with `XCOM Map Workshop.cmd`.

Each release lists the files' SHA-256 checksums.

**Windows may warn you.** The installer isn't code-signed, so Windows SmartScreen says "Windows protected your PC".
Choose **More info**, then **Run anyway**.

## What you need

- Windows 10 or 11, 64-bit, and a browser: Edge, Chrome or Firefox.
- XCOM: Enemy Within with Long War Rebalance. Plain Enemy Within should work too, but it hasn't been tried.
- Some free disk space: the editor keeps a copy of each map you open (about 50 to 200 MB each).

Everything else comes with it: its own Python and the packages it needs. It needs no internet connection and no
Unreal tools, and it contains nothing from the game: it reads your own install.

## Getting started

Each release has **User Guide.html**: every control explained with pictures, typical tasks, and what the editor can't
do yet. Setup offers to open it, and it is in the Start menu and in the editor's **?** menu. `README.md` beside it
covers setting up, building, playing and the known limits.

## Reporting a problem

Open an issue on this page's **[Issues](https://github.com/ruskyandrei/xcom-map-workshop/issues)** tab. Say which version you have (it is in the editor's **?**
menu). After a build, **Save a bug report** in the build window makes a zip of the project and the build's logs:
attach it, with what you did and what you saw (a screenshot helps).

## The source

The editor places objects in tactical maps, remixes a map's layout, and
later will set up missions that play in the normal campaign.
Everything runs as streamed patch maps and script actors loaded with the game's own maps. The game's files are never
changed in the real install, only in a lab copy.

The next-stage viewer and editor implementation plan turns the map
experiments into a staged plan for an accurate 3D viewer, patch previews and WYSIWYG editing.
The first coding milestone was the first editor: projects based on original maps,
full-axis transforms, clipboard/palette tools, and variant packages (map files plus config lines) for LWR modders.
Its Build now bakes an edit's lighting with our own baker.
**What's next, in order (7 November 2026):** the rest of the lighting work, steps L1–L7 in the
baker design's section 13,
then removing UDK from builds altogether, milestones U0–U8 of the
UDK-removal plan.
Step L6, lights in the editor (plan), is built (9 November 2026): the editor
shows, edits, copies and adds a map's lights, and the Build makes the edits for every project. The user switched them
on after run 1 of [EXP-26](research/experiments/EXP-26-lights.md) (a full build on URB_Bar); its runs 2 to 6 are to
come, and issues are fixed as they are found.
Fracturing pieces (walls, storey floors, roof slabs) and physics props build too since 9 November 2026, switched on
before a game run of them; run 1 of [EXP-28](research/experiments/EXP-28-fracturing-physics.md) passed the same day
on URB_Bar (a wall copied with its doors, a counter section moved, a wall deleted).
Frameless alien doors and opacity fade actors such as the small scout's energy field build with their native classes.
The first [working viewer preview](tools/viewer/README.md) now opens URB_Bar's original static/fractured scene with
textures, the map's own lights (rendered dynamically), selection and an inspector.
It also provides building-floor cutaway and experimental previews of the EXP-07 remix and EXP-08 blank layout.
Skeletal doors/props render in their reference poses, and previews compose inherited patch content with optional
hidden-helper inspection.
Pieces can be moved and rotated in the view to try out a layout; nothing is saved yet.
Double-click [xcom_editor.cmd](xcom_editor.cmd) to open the editor: it starts the main server on port 8768, or restarts
it if it is running, so it always serves the latest exports and code. (A release starts it with its own
`XCOM Map Workshop.cmd`.)

An early version for some of the modding community (smaller edits to LWR's maps, and plain Enemy Within's as a
best guess) is being prepared: what is left is in the preview release checklist.
`python tools/release/make_release.py` builds the release: a Windows installer and a portable zip, everything bundled
(the installer needs Inno Setup 6 or 7 on the machine that builds it; see `tools/release/`). Each version's installer and
zip are published as a GitHub release of this repository, and testers report problems in its Issues.

The editor's [user guide](tools/release/guide/guide.html) is one HTML page: every control explained on marked
screenshots, typical tasks, and what the editor can't do yet. Open it in a browser from the repository; a release
carries it as `User Guide.html`, and the editor's **?** menu links to it.

Changes are recorded as they go in, in the [change ledger](CHANGELOG.md).

## Layout

| Folder | What it holds |
| --- | --- |
| `research/` | Notes, experiments (`experiments/EXP-*.md`), the [findings register](research/findings-register.md) and the [native code notes](research/native-code-notes.md). Start with [`mission-editor-research.md`](research/mission-editor-research.md). |
| `tools/patch/` | `patchtool.ps1`: turns a JSON spec into a cooked streaming patch map and deploys it to the lab copy ([README](tools/patch/README.md)). |
| `tools/upk/` | Python readers for the game's packages: inventory, layout pictures, decompression, `seed_tiles.py` for the baked tile data, and `package_edit.py` for fixed-size edits in any compressed chunk; `schema.py`, `typed_props.py` and `native_fields.py`, which find every name, object reference and bulk-data offset of an export (the game's property types read from its script packages, and the native layouts of the classes that keep numbers there). |
| `tools/bake/` | Groundwork for our own lighting baker (design): lightmap statistics, the lighting field locator, test maps from fixed-size lighting edits, and their lab deploy/restore; UDK Lightmass calibration (scene writer, base map, unattended hidden bake, reader); EW's lightmap codec (`lightmap_encode.py`), a DXT1 encoder, per-texel geometry of a component's lightmap, and `relight.py`, which relights components from the map's own lights, with soft shadows traced by Embree (`shadows.py`), emissive surfaces' area lights and one bounce of indirect light (`bounce.py`, `albedo.py`); the dominant light's shadow maps (`shadowmaps.py`); new exports in a map by the growing writer (`grow_fixture.py`, gate C6), and placed pieces copied as new actors of the map (`native_copy.py`, any number of them, destructibles included: in the tiles, through seeds and a rebuild volume; with `--bake`, lit for where they stand); `transplant.py` brings a piece of another map and what it depends on into a map, renumbered and staged (plan; not yet used by the Build). `profile_build.py` says where a build's time went: its stages, the relight's phases and slowest pieces, the pieces kept from the last build (faster-bake plan). |
| `tools/viewer/` | The map viewer and editor: the exporter, the three.js page, projects, settings, and the editor's Build button (`builds.py`). `xcom_editor.cmd` starts the main server. |
| `tools/editor/` | The editor's compiler (`compiler.py`: a project into a patchtool spec) and its Build (`build.py`: a project into a variant package: the edit made in the map itself: copies as new actors, groups that break together linked there, hidden pieces taken out, the lighting baked; no patch or UDK for M1 projects; it installs nothing). |
| `tools/release/` | The release: `make_release.py` (the editor's modules, Python 3.12's embeddable package and its packages, three.js, the user guide and the licences, as a Windows installer made from `installer.iss` with Inno Setup, and as a portable zip), the launcher, the testers' getting-started README (`GETTING-STARTED.md`), the user guide (`guide/guide.html`, its screenshots in `guide/shots/` and `guide/take_shots.py`, which takes them), and `readme_install_check.py` (a build installed by its README alone). |
| `tools/re/` | Read-only helpers for the game's executable: PE reading, the native function map and disassembly. |
| `tools/lab/` | The lab copy: switching installs, driving the game and the UDK editor, the hidden desktop, F9 screenshots, and `lab_install.py`, which installs the editor's packages in the lab's test slot as they are built (the editor's Project menu does the same with Install as intro map). `save_tiles.py` reads what the game made of a map's tiles (floor, occupied) out of a tactical save, beside the map's baked ones. |
| `tools/udk/` | Helpers for the authoring UDK. |
| `unrealscript/XComMapEd/` | Our script package (copiers, hiders, spawners, walls, lights), compiled by the authoring UDK. |
| `tools/repo/` | The checks that keep the repository fit to be public: no folder of one computer, nothing from `private/`, no link that leads nowhere. |
| `private/` | Not in the repository (Git ignores it): what cannot be public. Our changes to LiQuiD911's XComGame stub classes (`private/unrealscript/XComGame-stubs.diff`), copies of other projects' source files, the plans (`private/plans/todo/` for the ones not built yet, `private/plans/done/` for the ones built or replaced) and pictures of experiments and checks (`private/shots/`). |

## Tests

`python -B tools/run_tests.py` runs the offline suites (viewer, editor, upk, bake, release, repo and the node tests) and
prints every failure with its traceback as each suite ends, so one run is enough to see what failed. Name suites to
run only those (`run_tests.py viewer editor`), and `-k <words>` for only the tests whose names hold them. The full
output of each suite is kept in `.scratch/tests/<date-time>/` (or `--log <folder>`). The bake suite takes about six
minutes. The browser smoke (`tools/viewer/tests/browser_smoke.py`) needs a test server and is run apart.

## Working from a clone

1. Python 3.12, then `pip install -r tools/viewer/requirements.txt` (numpy, SciPy, Pillow, embreex).
2. `python tools/viewer/setup_vendor.py` fetches the page's three.js, pinned and checked.
3. `python tools/viewer/viewer.py settings` shows the settings; set **game** to your Steam `common` folder or the
   game's own folder. `python tools/viewer/viewer.py doctor` checks them.
4. `xcom_editor.cmd` starts the editor on port 8768. A map is exported from your install the first time it is
   opened.

The suites that read the game's maps need an install and a cache; the others run without them.

## Setup this depends on (not in the repo)

- **The settings**: every folder below is a setting in `Documents\XCOM Map Workshop\settings.json`
  (`python tools/viewer/viewer.py settings` shows and sets them; `doctor` checks them). Nothing in the repository
  names a folder of one computer. Run from the repository, projects and builds default to that Documents folder; a
  release keeps them in its own folder.
- **The game**, XCOM: Enemy Within with Long War Rebalance, or plain Enemy Within as a best guess (the **game**
  setting, called **lwr** before 8 November 2026). The editor's Play in game installs into and starts the **install** setting's game,
  else that game install. Our lab also keeps a lab copy beside it: `tools/lab/switch_install.ps1`
  swaps the two installs, and the lab copy carries `XComLab-copy.txt`.
- **The authoring UDK** (the lab's experiments; the editor's Build no longer needs it): UDK 2011-09 with LiQuiD911's XComGame stubs ([iiiLiQuiDiii/UDK](https://github.com/iiiLiQuiDiii/UDK)),
  the **udk** setting.
  - `Development\Src\XComMapEd` there is a directory junction to `unrealscript/XComMapEd` in this repo, so the UDK
    builds from the files here.
  - The stubs have no licence, so neither they nor our changes to them are in the repository. Our changes are kept
    as a diff in `private/` (ignored by Git): after changing a stub in `Development\Src\XComGame\classes`, run
    `python tools/udk/save_stub_diff.py` to update it.
- **Python 3.12** with numpy, scipy and Pillow; the baker's shadows and bounce light also need `embreex`
  (`pip install embreex`, Embree 4 ray tracing).
- **The viewer cache** (the **cache** setting: exported maps) and, for our lab tools only, **work folders** under the
  **lab** setting's folder: builds, logs, screenshots, the lab's backups, the read-only executable copy and the native
  map. None of it is committed.

No game files, cooked packages, executables or anything decoded from them are committed (see `.gitignore`).
`research/evidence/upstream/source-manifest.json` names the source files of other XCOM modding projects that the
research read (repository, commit, address and SHA-256 each); the files themselves are not kept here.
Pictures of experiments are not kept either: a note says in words what a run showed, and a `*-shots.json` file beside
it holds the cameras and marks that [mark_shots.py](tools/viewer/mark_shots.py) makes the editor pictures from.

## Licence

The editor is under the MIT licence ([LICENSE](LICENSE)). It bundles Python, numpy, SciPy, Pillow, embreex and
three.js, each under its own licence (`THIRD-PARTY-NOTICES.txt` in each release).

XCOM Map Workshop is a fan-made tool, not affiliated with or endorsed by Firaxis Games or 2K. XCOM is their trademark.
