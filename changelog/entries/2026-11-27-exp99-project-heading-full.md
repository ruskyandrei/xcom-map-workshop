### EXP-99's project takes a heading and builds with baking

[exp99_project.py](../../tools/editor/examples/exp99_project.py) makes URB_Bar's time of day as the Map settings
window's time bar does. It now also takes `--heading` (the dial's side in degrees: the sun brought round to a new side)
and `--full` (a Build with baking, where a turned sun's shadows are traced again). EXP-100 plays such a Build.

- Where: [exp99_project.py](../../tools/editor/examples/exp99_project.py).
- Checked: compiled with `--time 08:00 --heading 223`: the sun 20.7 degrees up travelling toward game +X (Bar's moon
  stands 80.7 degrees up toward -X, +Y), `directionChanged` true, no warnings.
- Known gaps: none known.
