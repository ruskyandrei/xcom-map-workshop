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
- **[inline_lighting](../../tools/bake/inline_lighting.py)** (`_tags`, a texture's tags with where each starts and
  ends, so that two can be taken out): every export the same; a refusal of `props.tags` is still an `InlineError`,
  in `props.tags`' words. Its name helper (`lighting_name`), used by nothing else, went with its loop. The dominant
  light's component is refused in other words ("bad property name at 4", where it named the bad index).
- **[light_factory](../../tools/bake/light_factory.py)** (`used_guids`, the GUIDs of the light components a Build
  added): `_walk`, a copy of `props.tags` without its bounds checks, is gone; `used_guids` walks with `props.tags`.
  Every export the same; the dominant light's component refused in `props.tags`' words.
- **[lightmap_fields.property_offsets](../../tools/bake/lightmap_fields.py)** (where each property's value lies, for
  the relight's writes): every export the same, refusals included (a refusal of `props.tags` is still the viewer's
  `FormatError`; the dominant light's component is refused by its class first, as before). Its now unused `Reader`
  import went.
- **[relight.lightmass_settings](../../tools/bake/relight.py)** (a light's, a piece's or the world's Lightmass
  settings): its walk read a name without its number, did not skip a byte property's enum name, checked no bound
  and stopped without a word where the closing None was missing; with `props.tags` such a struct is refused. Every
  export of both maps reads the same (316 settings on the Bar, 1,446 on TempleShip: no member has a number or is a
  byte property, and every struct is closed), so no output changes.
- **[pack_card](../../tools/upk/pack_card.py)** (`_properties`, a map pack card's properties): the walk is
  `props.tags`, each value still read and checked by the card's rules. A refusal of the walk is a `CardError` in its
  words, as one of an object whose size runs past the file's end. Its old walk read a byte property of a size other
  than 1 or 8 as one byte and went on from there, and took a name with a negative number; neither is in a card the
  writer makes. Cards read the same: the tests' cards, the install's 188 Maps lines and 453 LZArray lines each
  through a card, and the two cut cards refused alike; every export of both maps too (a card's reader refuses most of
  a map's properties, in the same words).

Checked: each walker's module's tests after its commit (map_frame's 11, inline_lighting's 5, light_factory's 22 and
native_lights' 30, the lighting fixture's 18 and native_fields' 12, relight's 28 and the Lightmass settings' 2,
pack_card's 27 and the card's users' in the lab (20) and viewer suites (pack export 5, damaged inputs 6)).
