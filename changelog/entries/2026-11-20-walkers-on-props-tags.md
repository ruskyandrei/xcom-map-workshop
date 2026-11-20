### The product's tagged-property walkers walk with props.tags (editor refactor, stage B1)

The walkers of tagged properties that ship in the release, each with a loop of its own (review finding 52), now walk
with [`props.tags`](../../tools/upk/props.py), the one bounded walk, and keep only what they do with each property.
One walker a commit; each was checked by a walk of every export of URB_Bar (14,051) and TempleShip (14,137) with the
walker before and after (names, kinds, sizes, offsets, values, refusals). A difference is listed under its walker.

- **native_spawns:** nothing to move. It has had no walk of its own since review findings 37 and 55: it sets values
  through `native_lights.set_property` and poses through `native_copy.set_pose`, both on `native_copy.Walker`, which
  walks with `props.tags`.
- **[map_frame.describe](../../tools/bake/map_frame.py)** (a texture's properties and native data): every export the
  same, its bool's size still the one its tag saves. One refusal reads otherwise: the dominant light's component,
  whose properties stand after its leading shadow map (describe reads only textures and does not skip it), is refused
  at the same place as a `ValueError` ("bad property name") where it was the viewer's `FormatError` ("Invalid FName");
  `locate`, its one caller, catches `ValueError`.

Checked: each walker's module's tests after its commit (map_frame's 11).
