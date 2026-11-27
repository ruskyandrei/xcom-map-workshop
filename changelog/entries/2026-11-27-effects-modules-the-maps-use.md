### Effects follow the particle modules the maps use

Stage E4 of the game-likeness plan: the likeness follows the modules its simulator left out, in the order the maps
use them (over the lab copy's 97 maps, by placed emitters: Orbit 3,312 on 81 maps, the event generator 1,473 and event
receivers 620, SpawnPerUnit 430, the location emitters 391, AttractorPoint 107, SizeMultiplyVelocity 66, KillBox 8).
Export 49, draw version 7 (research/editor-contracts.md section 8).

- **One emitter's particles start, place and end another's** (`effects_sim.js` `linkEmitters`, `deliverEvents`): an
  event generator sends an event as a particle is born or dies, and a receiver of its type and name spawns its count
  where it happened, with the sender's speed by its share where it says (the crows land, take off and fly; their body
  and head start from the landing's events), or ends its particles (a kill receiver); a location emitter's particles
  are born at a live particle of the emitter it names, a direct one's kept at the particle of their place. An emitter
  that only sends events is stepped and draws nothing (its record `kind: events`, its `why` kept); one that only
  another's event starts is drawn now.
- **Orbits**: each particle is drawn at its place plus each orbit's offset turned by its turn and turning rate (the
  embers swirl); the chain modes are all taken as adding.
- **Attractor points, size by speed, kill boxes**, and **spawning by the distance the effect moved** (a drag, a copy on
  the cursor; nothing while it stands, as in the game).
- **The export** (`effects_draw.py`): those modules followed (`FOLLOWED`); each drawn emitter's `name`; a module's
  struct property read field by field; an event generator's `Events` (`generator_events`).
- Where: [effects_draw.py](../../tools/viewer/effects_draw.py), [export.py](../../tools/viewer/export.py),
  [effects_sim.js](../../tools/viewer/web/effects_sim.js), [effects_preview.js](../../tools/viewer/web/effects_preview.js),
  [editor-contracts.md](../../research/editor-contracts.md), the [findings register](../../research/findings-register.md) (F-222).
- Checked: [effects_sim_test.mjs](../../tools/viewer/tests/effects_sim_test.mjs) (an event's spawn where it happened
  with an inherited speed, an event of another name ignored, a location emitter and a direct one, an orbit's turned
  offset, an attractor's pull, size by speed, a kill box, spawning by distance); [test_effects_draw.py](../../tools/viewer/tests/test_effects_draw.py)
  (URB_Bar: an orbit followed with its options, emitters named, events read, an event-only emitter's record); the
  `likeness`, `effects` and `api-names` browser checks on URB_Bar and CSmallScout_DirtRoad; headless, the crows'
  body and head each spawned by the landing's event and the embers' 281 orbiting particles drawn by their program, no
  console errors. Track H's likeness (stage e4): all twelve 6.85 (CSmallScout_DirtRoad 4.90 to 4.81). Frames
  (perf_probe.py, headless): AlienBase01 Neutral 2.2 ms, Game 3.6 (about 920 particles); CSmallScout_DirtRoad 2.5 and
  4.0 (about 2,100).
- Gaps: VelocityMag (555 placed) and SizeByDistance (35) are XCOM's own modules, whose rules are not read: left out, as
  before. Ribbons, beams and trails are not drawn: no map places a beam or a trail, and one (EWI_ChryssalidHive) two
  ribbons. An event's frequency and first or last time only are not followed (every birth or death sends it).
