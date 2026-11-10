# XCOM Map Workshop (preview)

A map editor for **XCOM: Enemy Within**, made for **Long War Rebalance**. It opens one of the game's maps in your
browser, lets you move, turn, delete and copy its pieces and lights, and builds the result into a new map, a
*variant*, with its lighting baked, that the game plays like its own. **Play in game** starts the game straight in a
battle on your variant, with no campaign to start and nothing of the game's own changed.

This is an early preview for smaller edits to existing maps. Some edits don't build yet, and projects saved with it
may not open in a later version.

This page holds the releases. The editor's source isn't public yet.

## Download

Get the newest version from **[Releases](../../releases/latest)**:

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

Open an issue on this page's **[Issues](../../issues)** tab. Say which version you have (it is in the editor's **?**
menu). After a build, **Save a bug report** in the build window makes a zip of the project and the build's logs:
attach it, with what you did and what you saw (a screenshot helps).

## Licence

The editor is under the MIT licence ([LICENSE](LICENSE)). It bundles Python, numpy, SciPy, Pillow, embreex and
three.js, each under its own licence (`THIRD-PARTY-NOTICES.txt` in each release).

XCOM Map Workshop is a fan-made tool, not affiliated with or endorsed by Firaxis Games or 2K. XCOM is their trademark.
