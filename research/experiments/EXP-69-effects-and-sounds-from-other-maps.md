# EXP-69: effects and sounds of other maps

Date: 17 November 2026. The effects and sounds plan's game check after stage FX4 (its EXP-D, section 7.2), in one
project on URB_Bar, under Long War (the lab copy). Plain EW is not played in this run. Effects and sounds of other
maps waited for this run (the compiler's `FOREIGN_FAMILIES` didn't list them); the Build made them all the same.
**Run 1 passed: the compiler's `FOREIGN_FAMILIES` lists effects and sounds since.**

## What the offline checks settled

Read back from the built map with a fresh reader, as export 28 reads a map (`URB_Bar_X69`, quick build; a full build
gives the same map: effects and sounds change no baked light), so the run doesn't need to show them:
- each of the six donor actors was staged once, outside the level's actor list, with what it needs (141 objects;
  every brought object's class and archetype its donor's, over five stagings of the same edit), and each copy is an
  actor of its own, listed, with its own component (an effect its own light environment where it is lit; a sound its
  own cue and node, or the game's cue where the cue is a shared asset);
- the two fires are two clones of one staged actor; the headlight beam's particle system is Bar's own (Bar has
  `Fog_Cones.HeadLight_Beam_Cheap`: 745 bytes brought, the actor alone);
- the hyperwave beacon plays the game's `SoundAmbience.HyperWaveBeaconCue`, reach 500 to 1,250 from the cue; the
  fountain's reach (100 to 2,500) still comes from its fountain prefab's archetype, brought with it; every wave is
  playable (the editor's Wave preview plays each from its own map);
- one build staged the fountain with another map's class for its node, so it had nothing to play: a transplanter fault
  older than this stage ([F-121](../findings-register.md), fixed before this build).

What only the game can show: that each plays and sounds as it does in its own map: the lit moths take the light where
they fly, mesh particles (the moths' wings, the fire's chunks) draw, a system Bar already has shines as Bar's own do,
a simple sound, a shared cue and a sound whose reach comes from an archetype are heard, and two copies of one fire
burn on their own.

## The project

`EXP-69 effects and sounds from other maps` (URB_Bar, [exp69_project.py](../../tools/editor/examples/exp69_project.py),
in the editor's project store), a quick build. It compiles with no warning and no note. Marked shots:
`EXP-69-street.png`, `EXP-69-fires.png`, `EXP-69-fountain.png` ([EXP-69-shots.json](EXP-69-shots.json)).

| No. | What | From | Where | The prediction |
| --- | --- | --- | --- | --- |
| 1 | moths (`P_Moths_Wandering`: lit, mesh particles), which Bar doesn't have | CAbductor_Cliffside, `Emitter_46` | over the row of parked cars nearest the road, 200 up | moths wander there, lit like what is round them |
| 2, 3 | a fire (`P_Fire_Mid_No_Chunks`: mesh and sprite particles), which Bar doesn't have, twice | CLrgScout_ForestTrench, `Emitter_11` | the lane between the parked cars | two fires, each burning on its own |
| 4 | a headlight beam (`HeadLight_Beam_Cheap`), a system Bar has | URB_MilitaryAmmo, `Emitter_104` | by the police car | a beam of light, as the bar's floodlights' |
| 5 | an air-conditioning unit's hum (a simple sound: its own cue and node), a wave Bar doesn't have | Act2_Pier, `AmbientSoundSimple_0` | the car park's corner by the road, at the other end from the police car | heard within about 1,250 of it |
| 6 | a hyperwave beacon (a shared cue: the game's asset), a wave Bar doesn't have | AlienBase01, `AmbientSound_11` | the car park's edge by the road's pavement | heard within about 1,250 of it |
| 7 | a fountain's splashing (its reach from its fountain prefab's archetype), a wave Bar doesn't have | URB_Boulevard, `AmbientSoundSimple_1` | the street behind the bar, by the heap of rubbish | heard within about 2,500 of it |

## Run 1

What the run adds over the offline checks (Play in game from the editor, on the project):
1. **The effects (1 to 4):** moths flying at 1, fires burning at 2 and 3 (flames and the chunks they throw), a beam
   of light at 4. Any of them missing, drawn as a grey or chequered square, or at the map's own places of its home
   map?
2. **The sounds (5, 6, 7):** with the camera over each in turn (the listener question EXP-68 left open: whether the
   game hears from the camera or from the soldiers), the hum at 5, the beacon's pulse at 6, the fountain at 7, each
   fading away from it. If one is silent, does it sound with a soldier standing beside it?
3. **Save and reload** once: all of them as before.
4. Anything odd: a crash on loading, an effect playing twice, a sound heard everywhere.

## Result

**Run 1 passed** (17 November 2026, played by hand). Every effect played and
every sound sounded as predicted, and the save and reload changed nothing; nothing odd was reported. So effects and
ambient sounds brought from other maps play as in their own map: a lit one, one with mesh particles, one whose
system the map has already, two copies of one, a simple sound with its own cue, a shared cue and a sound whose reach
is its archetype's. The compiler's `FOREIGN_FAMILIES` lists `effect` and `sound` since, so the library marks them
placeable.

Not told apart in this run: where the game's listener is (the camera or the soldiers). The report gave no silent
sound, so the soldier question didn't come up; EXP-E still needs it for its reach check.
