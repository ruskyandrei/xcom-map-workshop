# EXP-04: Place one object and check its gameplay effect

Status (3 November 2026, 21:15): **passed.** The block is visible, blocks movement and gives high cover. The control (`patch_bar` only) is optional and not done.

## Question

Can we add one new object to a level, as a uniquely named streamed patch, and have the game treat it as real
terrain? That means it is visible, it blocks movement and it gives cover.

EXP-03 couldn't tell whether `patch_bar` itself changes anything. So this test adds an object that can't be missed,
in an open spot.

## What was built

- **Source.** `patch_exp04.udk` in the authoring UDK (`UDKGame\Content\Maps\patches`). It is a copy of `patch_bar.udk`
  with two actors added from `<lab>\exp04\exp04-add.t3d` by `MAP IMPORTADD`:
  - `XComLevelActor_900`:
    - mesh `CoverPatch.High2x2`, the same high-cover block `patch_bar` uses, but visible (no `bHidden`);
    - `CoverForce_High`, `COLLIDE_BlockAllButWeapons`;
    - Location (−2592, −960, 4), a 2×2-tile block on tile corners near the dumpsters.
  - `XComRebuildWorldDataVolume_900`:
    - a copy of volume 9 (a ±128 cube) at (−2592, −960, 16);
    - it makes the game rebuild tile, pathing and cover data under the block.
  - **The block went in twice (found later by `tools/patch` testing).** `udk_editor_cmd.ps1` posted both a key-down
    and a character for Enter, and the slow `MAP IMPORTADD` ran twice. That is the doubled "Cmd: MAP IMPORTADD" line
    in the log.
    - Both `patch_exp04.udk` and the deployed `patch_exp04.upk` hold two identical copies:
      - `XComLevelActor_900` and `XComLevelActor_0`;
      - `XComRebuildWorldDataVolume_900` and `XComRebuildWorldDataVolume_2`, whose components are still named
        `_900`.
    - The in-game result still stands, since the copies are in the same place.
    - The script now sends only the key-down, and `tools/patch/patchtool.ps1` fails a build whose import ran more
      than once.
  - The import logs "unresolved reference to Model'Model_900'". This is normal for T3D, where the brush is defined
    after the component that names it. Select-all plus `EDIT COPY` lists both new actors after the import.
- **Cooked file.** PC cook, `CookedPC\Maps\patches\patch_exp04.udk` (69,501 bytes). The cook ends with the known
  harmless `HQSound_MCMusic` error (see EXP-01).
- **Deployed:**
  - `XEW\XComGame\CookedPCConsole\patch_exp04.upk`;
  - in the lab `DefaultMaps.ini`, the EXP03 first-mission entry (line 36) streams `patch_exp04` instead of
    `patch_bar`. Backup: `<lab>\snapshots\exp03\DefaultMaps.ini.pre-exp04`.

## Driving the editor without the GUI

- **`tools/lab/udk_editor_cmd.ps1`** types commands into the editor's command box. It now finds the box by walking
  the native windows: the Edit inside the lowest ComboBox. UI Automation often sees none of the editor's controls
  right after start-up.
- **`tools/lab/udk_editor_saveas.ps1`** saves the open map:
  - It sends File > Save As (menu id 6384), or uses a Save dialog that's already open.
  - It fills the file name and presses Save, then Yes on Confirm Save As (a button found by its text, since its id
    is 0).
- **Things that do not save:**
  - `MAP SAVE` and `OBJ SAVEPACKAGE` from the command box.
  - Save Current Level (6367) only opens the same Save As dialog for a map not yet saved in this session, and that
    can take 20 s or more to appear.
- **Save time.** The save itself took about 21 s ("Save=21.25" in the log).

## In-game result (look 1, 21:10, screenshot `<lab>\exp04\look1.png`)

- **Visible: yes.** A dark, untextured box about 2 tiles long stands in front of the dumpsters. `CoverPatch.High2x2`
  is made to be hidden, so its plain material is no surprise.
- **High cover: yes.**
  - With the cursor at (−2545, −817, 64), the tile just south of the block, two solid high-cover shields face it.
  - Outlined high-cover shields also show along the block's west side.
- **Blocks movement: yes (look 2, `look2.png`).**
  - The cursor at (−2545, −913, 64.7), a tile inside the footprint, shows `PathActionEmpty: True`, so there is no
    path to it.
  - The move-range outline runs right around the block.
  - Seen from the other side, the box is 2×2 tiles with cover shields on every side.

**Conclusion:** an object added as a new, uniquely named streamed patch works as real terrain. It is visible, it
blocks movement and it gives high cover. The game rebuilt the tile data for it, because the patch carries a
`XComRebuildWorldDataVolume` over the new block.

## In-game check (plan)

1. Start a new campaign in the lab copy. The first mission is URB_Bar via route 3.
2. Turn on `ShowCursorLoc` and `ToggleFOW`, then put the camera on (−2592, −960); the block covers the tiles from
   x −2688 to −2496 and y −1056 to −864.
3. Say "look" for each of these:
   - the block is visible;
   - a soldier can't path through it;
   - a soldier next to it gets a high-cover shield.
4. Control: the same spot with `patch_bar` streamed instead (`snapshots\exp03\DefaultMaps.ini.route3`).
