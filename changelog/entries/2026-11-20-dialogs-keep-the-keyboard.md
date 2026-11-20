### Every dialog keeps the keyboard: Tab stays in it, the scene behind takes no keys, the focus comes back

Review finding 11. Tab left most dialogs while they stayed open. Behind Missions, Map picture, Clear map and Prepare,
Delete, Ctrl+Z, the tool keys, B, WASD and M still acted on the scene, and M opened the map browser on top. Missions
put the focus on its OK button even when OK was off, and Clear map didn't give the focus back when it closed.

- [modal.js](../../tools/viewer/web/modal.js) gives every `.modal` the same behaviour, put in once by
  [app.js](../../tools/viewer/web/app.js):
  - Tab and Shift+Tab go round the dialog's own controls, from the last back to the first.
  - A dialog that opens without taking the focus gets it on its first control.
  - When a dialog closes, the focus goes back to where it was opened from.
  - Each dialog keeps its own keys. The project manager's rows stay one Tab stop and the map browser's rows stay off
    the Tab ring (`tabOrder`).
- This replaces the three hand-written Tab wraps in [project_files.js](../../tools/viewer/web/project_files.js),
  [manager.js](../../tools/viewer/web/manager.js) and [map_browser.js](../../tools/viewer/web/map_browser.js).
- One `modalOpen()` test (any dialog shown, or the look picker) is used by the page's shortcut guard and by the M
  key, Game maps, Cache everything and the project manager. It replaces five lists kept by hand.
- [Missions](../../tools/viewer/web/missions_panel.js) puts the focus on OK only when OK can be used. Otherwise it goes
  to the first tick box that can be ticked.
- `window.viewer.showPrepare` opens the Prepare dialog for the checks.
- Checked: the new browser check `modals` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py), through
  `browser_smoke.py --only modals`) opens Clear map, Prepare, Map picture and Missions from the header's Map button.
  In each it presses Tab from the last control and Shift+Tab from the first, and goes all the way round. It presses
  Delete, M and W and checks that the picked piece, the map browser and the camera stay as they were. Then it presses
  Escape and checks that the focus is back on the Map button. It also opens Missions with no row ticked. The check
  fails on the page before this change.
