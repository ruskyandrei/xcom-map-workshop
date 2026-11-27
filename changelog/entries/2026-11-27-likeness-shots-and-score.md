### The game-likeness measure: the same twelve views shot in the game and the editor, scored

Track H of the game-likeness plan (H1, H2): a lab tool that takes the same camera views in the game and in the
editor, puts them side by side and scores how far apart they are, so each later stage of the plan can say how much
closer it brought the editor.

- [likeness.py](../../tools/lab/likeness.py) (not shipped) with its shot list
  [likeness_shots.json](../../tools/lab/likeness_shots.json): three cameras on each of four maps (a night scout
  map, a day abduction, an urban night map, an alien base), each the game's overhead camera (target, yaw, pitch,
  distance, field of view). `steps` gives the hidden run's console steps, `editor` takes the editor's shots on a
  test server (the floors control on the ground floor, as the game cuts roofs near what the camera looks at),
  `sheet` and `overlay` put pairs side by side and edge over edge, `score` blurs both pictures to 32 by 18 cells and
  gives the mean CIELAB difference with its lightness and hue parts.
- The page's test hooks gain `grabView` ([test_api.js](../../tools/viewer/web/test_api.js),
  [app.js](../../tools/viewer/web/app.js), recorded in
  [viewer_api_names.json](../../tools/viewer/tests/viewer_api_names.json)): the view as the Map picture takes it,
  without the gizmo, grid and markers.
- Measured in the game (a hidden run on each map, the camera read back from `XComCamera CameraCache`): the commands
  set the target, distance, pitch and field of view as given, and the yaw turned by 138.6 degrees, the same on all
  four maps (the shot list's `yawOffset`); `UIToggleVisibility` hides the interface but for the version label, which
  the score masks; one `ToggleFOW` lifts the fog of war. Overlaid, the Bar's buildings line up edge for edge.
- Baseline scores (mean over twelve views): 24.6 in the Neutral look, 18.0 in the Map lighting mode.
- Checked: [test_likeness.py](../../tools/lab/tests/test_likeness.py) (a picture against itself scores 0, a tinted
  copy its tint's difference, other sizes refused, masked cells left out, the camera's place and field of view, the
  game's steps, the shot list).
- Known gaps: the pictures and scores are kept in `private/` (not committed); one view of the Bar has the squad in
  a corner, masked.
