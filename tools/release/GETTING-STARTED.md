# XCOM Map Workshop (preview)

A map editor for XCOM: Enemy Within. It opens one of the game's maps in your browser, lets you move, turn, delete
and copy its pieces, add pieces from the game's other maps, and builds the result into a new map, a variant, with
its lighting baked, that the game plays like its own. A map can also be cleared and built up again from pieces and
prefabs, with its own size, buildings and landing zones.

This is a preview: [What builds](#what-builds-in-this-preview) lists what the Build makes, and projects saved with
it may not open in a later version.

**The user guide** is `User Guide.html`, beside this file: every control explained with pictures, typical tasks,
and what the editor can't do yet. Setup offers to open it when it finishes; later it is in the Start menu
(**XCOM Map Workshop guide**) and in the editor's **?** menu.

## What you need

- Windows 10 or 11, 64-bit.
- XCOM: Enemy Within with **Long War Rebalance**. **Plain Enemy Within** works too.
- A browser: Edge, Chrome or Firefox.
- Some free disk space: the editor keeps each map you open (about 50 to 200 MB each) in
  `Documents\XCOM Map Workshop\cache`.

Everything else comes with it: its own Python, the packages it needs and the 3D library. You need no internet
connection and no Unreal tools.

## Setting it up

1. Run **XCOM-Map-Workshop-<version>-Setup.exe**.
   - The installer isn't signed yet. If Windows says "Windows protected your PC", choose **More info → Run anyway**.
   - **Upgrading:** close the editor's window first (and wait for a running build to finish). Setup replaces the
     editor's own files, which a running editor holds open; it asks you to close the editor if it is still running.
2. Follow its pages:
   1. **Licence:** the MIT licence.
   2. **Destination:** where to install the editor. By default it goes in your own user folder
      (`AppData\Local\Programs\XCOM Map Workshop`) and needs no administrator rights. Setup also offers to install
      for all users, in `Program Files`.
   3. **Your XCOM: Enemy Within game:** the game folder, the one that holds `XEW`, usually
      `...\steamapps\common\XCom-Enemy-Unknown`.
      - Setup fills it in when it finds the game in Steam; **Browse…** picks another.
      - It says whether that folder is Long War Rebalance or plain Enemy Within, and won't go on with a folder that
        isn't a game.
   4. **Shortcuts:** a desktop shortcut if you want one; there is always one in the Start menu.
   5. **Finish:** start the editor straight away and open the user guide, if you like.

   Setup writes the editor's settings to `Documents\XCOM Map Workshop\settings.json`. Nothing goes into the game.
   Your projects, builds and prefabs default to the editor's folder when it is writable. Existing libraries in
   Documents are kept available on upgrade. **Game install and checks…** shows the folders in use.
3. Start the editor from the Start menu (**XCOM Map Workshop**) or the desktop shortcut.
   - It opens in your browser at `http://127.0.0.1:8768/`.
   - Keep its window open while you work; close it to stop the editor.
   - The editor runs only on your computer: nothing is sent anywhere.

**Without the installer:** the release also comes as a zip.
- Unpack it anywhere and run **XCOM Map Workshop.cmd**.
- On its first start the editor asks for the game folder in the browser (the same choice as Setup's page).

To change the game folder later: Settings (the gear) → **Game install and checks…**. That dialog also lists the editor's
checks, if something seems wrong.

## New in this version

Each of these has its own section in the user guide, with pictures.

New in 0.7.0:
- **Walls, floors, roofs and ground at any size and angle**, sized by white handles, walls meeting in mitred
  corners, and a **Texture mapping** of your own on each surface.
- **The Snap setting governs every move, size and turn**, smooth with snap off. **Align to grid, level and game
  pose** (the piece panel's Align section, or the L key) replace Level snap and the recipe snap.
- **Diagonal cover** is shown in View options and kept by the Build.
- **Map settings…** (Map menu): the sun, moon and sky, and the map's background sound.
- **Clear map** takes the map's triggers out unless you keep them.

New in 0.6.0:
- **Walls, rooms, floors, roofs and ground of your own**, drawn from the Build menu on the Add button. The **look
  picker** gives them the look of any of the game's, and **Break** and **Repair** start the battle with damage.
- **Effects and sounds** (the Effects view) and **spawn points** (the Spawns view) are edited, and effects and
  sounds of other maps can be added.
- **Map picture…** (Map menu) sets the picture the game shows for your map.
- **Export map pack** makes a drop-in pack for Long War Rebalance 3: one folder, no file of the game changed.
- **The header's menus are sorted out:** Project and Map menus, Build and Play as buttons, the Game menu on Play's
  arrow, setup under Settings (the gear).

New in 0.5.3:
- **Piece flags** in the piece panel: Blocks walking, Gives cover, Blocks sight, Floor and Mouse picks it.
  **Select all of a kind** picks every piece with the same mesh.
- **Test squad setup** (Settings, the gear in the header): the squad every Play in game lands with; under Long War
  Rebalance up to eight soldiers, MEC troopers and SHIVs with their gear.
- **Build** in the project manager builds the ticked projects one after another while you go on editing. The
  manager is laid out again, and a map pack can carry the maps' editor projects.
- **Maps named after their project**, shown in Save, and **maps up to 256 tiles a side**.

New in 0.5.2:
- **Play in game plays the mission you pick** (the header's Mission picker), not always an abduction, and says how
  far that kind is known to work. **Missions…** (Map menu) chooses a project's missions and can add some.
- **A mission's objects** are marked in the view (View options, Mission objects), move with their group, and the
  Build warns when an edit takes the floor from under one.
- **Enable saving:** a test battle you can save and load; XCOM opens at its main menu and F5 starts the battle.
- **Cover blocks of any size**, sized by dragging their faces, and **blockers** (Cover None) that stop walking
  without giving cover.
- **Camera speed sliders** in View options and a **Pivot** button (C) for the selection's centre.

New in 0.5.1:
- **Cache everything…** (Settings, the gear) reads every piece of the game's maps ahead of use, and every map if asked,
  with a progress bar and Cancel.
- **30 levels:** maps, prefabs and the prefab test's stage go up to 30 levels high (18 before).
- **More is built:** a piece the Build can't make is left out and listed, and the rest is built; pieces of a kind
  the Build had not made before are built too. The prefab builder's **Problems** chip says what its test would say.
- **A faster editor:** large prefabs open in about a second, edits and pastes with many pieces are quicker, and slow
  steps show a bar.

New in 0.5.0:
- **Pieces from other maps:** the piece list's **All maps** lists every piece of every map in your install.
- **Prefabs:** a set of pieces, or a whole building, saved to place in any map and to pass on as a file.
- **Buildings:** the Buildings view (Shift+B) draws the floor boxes that make a roof hide and walls cut down in the
  game, for houses you put together and for the map's own.
- **Clear map** (Map menu) takes every piece off a map, to build a new one on its light and landing.
- **Map grid** (tool strip) resizes the play area with handles: larger and taller on any map, any size once cleared.
- **Landing zones** (Shift+Z): where the squad lands, moved, turned, added and deleted. **Land here** plays one.
- **Box select** (T), groups inside groups, and groups that hold lights and buildings.
- **Cover blocks that break:** a cover block grouped with a breakable piece, with **Break together in the game**
  ticked, goes when the piece is destroyed.
- **A copy by dragging:** hold Shift as you take a move handle.
- **Warnings, not refusals:** the Build now warns about most things that may behave oddly in the game and builds
  the map all the same. A ladder that isn't expected to climb no longer stops a build.

## Using prefabs

Open **Add a piece → Prefabs → New** for a blank prefab workspace, or save a selection from a map. Prefabs can
be edited, shared as JSON and placed in other maps. In the builder, **Prefab → Test in game** tests the current
workspace on a lit stage. When you open or place a prefab with missing pieces, the editor looks for the same
recipes in your install and warns about any it can't load. After scanning **All maps**, you can retry with
**Prefab → Find missing pieces** in the builder.

## Making a variant

1. **Choose a base map** (the Map button, or M). The map browser lists every map your install plays, by mission
   type. The first time you open a map, the editor reads it from the game, which takes about half a minute.
2. **Edit:**
   - **Select:** click a piece (Ctrl or Shift+click adds to the selection).
   - **Move or turn:** G moves, R rotates; drag the arrows or rings. With Snap at 96, cars, doors, ladders, vans
     and walls keep to whole tiles and quarter turns, where they build exactly.
   - **Delete:** the Delete key.
   - **Copy:** Ctrl+C, then Ctrl+V; click to place the copy. Or hold Shift as you take a move handle.
   - **Add:** P opens the piece list: this map's pieces, all maps' and your prefabs. Click one, then click in the view.
   - The **?** button lists every control, and links to the user guide.
3. **Save** your edits as a project (Ctrl+S, then give it a name). Until then they are only a trial. Under the name,
   the Save window shows the map's name in the game: your project's name as one word, at most 24 characters
   (`Commercial restaurant fix` builds as `CommercialRestaurantFix`), numbered when another project or map has it.
   It stays the same once saved; **Save as…** under a new name makes a new project with a name of its own.
4. **Build…** (Ctrl+B) opens a small panel, then saves the project and makes the variant.
   - **Bake the lighting** is off by default. The build then takes seconds, and pathing, cover and line of sight in
     the game are right, but the lighting around your changes isn't. Use it to try a layout in the game.
   - Tick it when the map looks the way you want. That build takes a few minutes for a small edit, while the editor
     relights the map around your changes.
   - The variant goes in the editor's `builds\<variant name>\` folder.
   - Its `README.txt` says what each file is and lists the config lines the game needs.
   - **Cancel the build** stops it; the last good build stays as it was.

## Playing it

Close XCOM first. Then:

- **Play** (in the header) starts XCOM **straight in a battle** on the open project's latest build: pick
  Enemy Within in the game's launcher (if yours still shows it), and the battle starts by itself with the test squad (below). There is no campaign
  to start, and nothing of the game's own is changed.
  - It opens the same panel as Build: **Build and play** builds first (Bake the lighting off by default), and
    **Play last build** plays the last build as it is, when that is of what is on screen.
  - A finished build's window has **Play in game** too: it plays the build just made.
  - It copies the build's files into the game and adds one line to `DefaultMaps.ini`: a record for the variant under
    its own name, out of the rotation (and, on Long War, the landing-zone lines).
  - It keeps a backup of each file it changes, in `<game folder>\XCOM Map Workshop\`.
  - The game is started through Steam, with nothing to set up there. The game folder must be the one Steam runs.
  - While you play, the game rewrites its `XComContent.ini` with the test squad in it. The editor keeps that file
    aside and puts it back when the game closes, so leave the editor open until then (if it was closed, the file goes
    back when the editor next starts).
- **Game maps… → Undo everything** (the Game menu, on Play's arrow) takes it all back out: the config files end as
  they were, byte for byte.

With a map open and no project, Play in game plays the original map, without edits, which is handy to compare; nothing
is installed for it (but a copy of the map record for Basic Training, the tutorial's map, whose records the game
keeps switched off).

The test battle is the mission the header's **Mission** picker shows (the play window can change it): the map's
landing for it, four pods of Sectoids and the test squad. It is not a campaign mission. It can't be saved unless you
tick **Enable saving** in the play window: XCOM then opens at its main menu and F5 starts the battle, which you can
save and load.

**Test squad setup…** (the Game menu, on Play's arrow) sets the squad every Play in game lands with: one to eight units, each with its kind (soldier, MEC trooper or SHIV), name, class, rank, look,
armour, weapons, items, perks and base stats, chosen from the install's own lists. Until you save one, it is six
squaddies. Errors (an armour with no body, a MEC without its gun) stop a play; warnings say what the game will do
with something odd. **Export…** and **Import…** share a squad as a `.xcomsquad.json` file. On plain Enemy Within and
Long War without Rebalance the squad holds soldiers only, six at most. The squad is kept in
`Documents\XCOM Map Workshop\test-squad.json`.

**Missions…** (Map menu) sets the missions a project is for: the base map's, and kinds a record alone can give
it (an abduction, a terror site, a bomb mission under Long War, a crashed or landed UFO with a UFO prefab placed). The
Build writes a record for each. A cleared map is asked **What is this map for?** when it is cleared.

**By hand:** copy the build's `CookedPCConsole` files into `XEW\XComGame\CookedPCConsole` of the game, and add the
config lines its `README.txt` lists. Getting a variant into the normal mission rotation is up to you: as built, its
records are out of rotation.

## What builds in this preview

- **Builds:**
  - moving, rotating, deleting and copying scenery, props, breakable props (windows among them) and collectibles
    (a copied UFO power core counts as loot);
  - the same for ladders, doors with a frame, cars and vans. Doors without a frame (UFO and alien doors) build
    too. A ladder climbs where its foot and its top meet floor; elsewhere it is built
    with a warning;
  - the same for fracturing walls, storey floors and roof slabs, and for physics props. A copied wall no longer breaks the pictures, shelves and neighbouring walls its original breaks, unless
    they are copied along with it in the same move. A copied floor can be walked on only where a soldier has room
    to stand: not under a duct or a low ceiling;
  - any piece can be placed freely with snap off. Ladders, doors, cars, vans, walls and floors are surest on their
    original's tile grid: tile snap (96 on the snap button) keeps them there, whole tiles and quarter turns from where
    the original stands. Off the grid they build, with a warning ("Off the grid" in the piece panel);
  - adding supported pieces from the current map or other maps, including pieces placed as prefabs;
  - cover blocks (invisible high or low cover) and invisible floors, on plain Enemy Within too;
  - buildings: floor boxes for a house you put together, and the map's own buildings moved, stretched, added to
    or deleted;
  - a cleared map, a larger or taller tile grid, and landing zones moved, turned, added or deleted;
  - lights: moving, turning, recolouring, deleting and copying the map's placed lights, changing their brightness,
    radius and cones, and adding a new point or spot light. A glowing piece (a lit sign, a machine's screen) takes
    its glow along when moved, copied or deleted;
  - walls, rooms, floors, roofs and ground of your own, drawn from the Build menu on the Add button, with any of the
    game's looks, openings and holes, and damage to start the battle with (**Break** and **Repair**);
  - effects, sounds and lens flares: the map's moved, copied, deleted and grouped with pieces, and effects and
    sounds of other maps added, with their values changed;
  - spawn points: pods, Meld points and drop-in points moved, added and deleted, and spawn rules;
  - a project's missions, its own map picture, and a Long War Rebalance 3 map pack of several projects;
  - a mission's own objects moved (not copied or deleted).
- **Shown for reference, not editable:** what a mission streams into the map besides its objects (LWR's patches).

## Known limits

- **Start a fresh mission after installing.** A tactical save from before the install ignores the new pieces' cover.
- **LWR's invisible cover stays put.** It doesn't move when the piece it covers moves. Untick "Hide patch helpers"
  to see it.
- **A mission's own objects can be moved, not copied or deleted.** Pick one's marker (hover the Normal view's button
  and tick **Spawn points and objectives**) and drag its arrows: it moves with its group, in the Build's own copy of the mission's stream. Under Long War the bomb and its power nodes go where its bomb rules put them anyway.
- **The squad may land on a new piece.** Keep copies off the soldier tiles, or move the landing zone (Shift+Z).
- **The editor's colours are approximate.** The game's lighting comes from the Build.
- **Light edits need Bake the lighting.** Without it, a build makes them in the map but doesn't bake them. A deleted
  or changed light's old pool stays on the floor and walls, and a new light has no pool of its own.
- **The test squad on plain Enemy Within** holds soldiers only (no MECs or SHIVs).
- **Projects may not open in the next version.** Keep your builds: those play regardless.

## Where things are

| What | Where |
| --- | --- |
| Settings | `Documents\XCOM Map Workshop\settings.json` |
| Projects | `<editor folder>\projects\` (one `.json` file each: share a project by sending it) |
| Prefabs | Beside projects by default (one `.json` file each) |
| Builds | `<editor folder>\builds\` |
| Opened maps | `Documents\XCOM Map Workshop\cache\` (safe to delete; maps are read again when opened) |
| Build logs | `<editor folder>\builds\.work\<variant>-<time>\logs\` |
| What Play in game installed | `<game folder>\XCOM Map Workshop\` (records and backups) |

The editor folder is where it is installed (by default `%LOCALAPPDATA%\Programs\XCOM Map Workshop`), or where you unpacked the zip.
Upgrading keeps your projects, builds and prefabs. The exceptions use `Documents\XCOM Map Workshop` instead:
- an install for all users (in Program Files, which the editor can't write to);
- projects, builds or a prefab library left in Documents by an earlier version.

`python\python.exe tools\viewer\viewer.py settings --prefabs <folder>`, run in the editor folder, sets a custom
prefab folder. Use `--projects` for projects or `--output` for builds. With the zip, unpack a new version over the
old folder, or move `projects`, `builds` and `prefabs` into the new one.

## Reporting a problem

Say which version you have: it is in the ? panel, in `VERSION.txt` and in each build's `manifest.json`.

After a build (or a failed or cancelled one), **Save a bug report** in the build window zips the project, the build's
manifest and logs into `<editor folder>\builds\<variant>-report.zip` and copies its path; click the path to see the
zip in Windows Explorer. Send that zip, with what you did and what you saw (a screenshot helps).

## Removing it

1. Run **Game maps… → Undo everything** (the Game menu, on Play's arrow) first, if you played or installed a project
   in the game.
2. Uninstall **XCOM Map Workshop** from Windows' Settings → Apps. It leaves your projects, builds and prefabs in the
   editor folder; delete that folder too if you don't need them. With the zip, delete its folder.
3. `Documents\XCOM Map Workshop` keeps the settings and the opened maps: delete it if you don't need them.

## Licence

The editor is under the MIT licence (`LICENSE.txt`). It bundles Python, numpy, SciPy, Pillow, embreex and three.js,
each under its own licence (`THIRD-PARTY-NOTICES.txt`). It contains nothing from the game: it reads your own install.
