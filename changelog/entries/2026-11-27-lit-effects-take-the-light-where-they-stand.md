### Lit effects take the light where they stand

Stage E2 of the game-likeness plan: an effect whose material is lit (its program gives a colour the light multiplies,
stage E1) is lit by the light the view draws where the effect stands, as the game lights it by its light environment
there, in place of plain white. The fog was already drawn on every likeness (C2).

- **The light at a place** (`light_rules.js` `lightAt`, pure): the sky light's upper and lower colours by the normal's
  height (three's hemisphere light), the sun by its cosine, and each point and spot light by its cosine, UE3's falloff
  (1 - (d/R)^2)^F and its cone, as the lit pieces' shader takes them; no shadow. `lighting.js`' `lightAt(at, normal)`
  gives it for the view as it stands: the Neutral look's light, the map's (its sun and sky light as the time of day
  sets them, and every point and spot light the look draws, static ones too, as a light environment takes them), Solo's.
- **The likeness** (`effects_preview.js`): `lit` where an emitter's program gives a colour, and `setLight`, which puts
  the light on its lit materials; `effects_wiring.js` sets it each frame for each lit likeness in the picture, for a
  surface facing the camera, as a sprite does; `describe()` gives each emitter's light.
- Where: [light_rules.js](../../tools/viewer/web/light_rules.js), [lighting.js](../../tools/viewer/web/lighting.js),
  [effects_preview.js](../../tools/viewer/web/effects_preview.js), [effects_wiring.js](../../tools/viewer/web/effects_wiring.js),
  [ARCHITECTURE.md](../../ARCHITECTURE.md).
- Checked: [light_at_test.mjs](../../tools/viewer/tests/light_at_test.mjs) (the sky by the normal's height, the sun by its
  cosine, a point light's falloff and a spot light's cone, all three together); the `likeness` browser check on URB_Bar
  (a lit likeness's light changes with the look); on AlienBase01 (188 lit emitters placed: its lit smoke, rocks and
  vapour) a lit likeness takes (0.52, 0.57, 0.59) in the Neutral look and (0.10, 0.07, 0.11) in the Game look, its local
  lights only (the base is underground, no sun). Track H's likeness (stage e2): all twelve 6.93 as at e1 (AlienBase01
  13.17 to 13.14; the shots hold few lit emitters). Frames on AlienBase01 (perf_probe.py, headless, about 940
  particles): the likenesses by their roles 4.3 ms, by their programs and lit 4.4 (the computer busier than at E1).
- Gaps: no shadow on a lit effect (a lit smoke under a roof takes the sun); one light for a whole effect, at its place;
  a mesh particle faces the camera as a sprite does for its light.
