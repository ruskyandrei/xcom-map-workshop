### The light writer starts past the sun's shadow map of the level

A dominant directional light's component saves a counted array of 16-bit depths (its shadow map of the level) before
its properties. `native_lights.props_start` took the properties to start inside that array, so `set_property` could
not write the sun's colour or brightness (F-176). It now skips the array, as the viewer's reader does. Nothing wrote
the sun before; the time of day's Build (T-S2) will.

- Where: [native_lights.py](../../tools/bake/native_lights.py) (`props_start`),
  [audit_suns.py](../../tools/upk/audit_suns.py) (the write-back's wording).
- Checked: [test_native_lights.py](../../tools/bake/tests/test_native_lights.py): on URB_Bar's sun the start lies
  past the depths; Brightness written from it reads back, with the GUIDs and the depths kept.
- Known gaps: none known.
