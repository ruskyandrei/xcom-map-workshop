# EXP-68: effects and sounds moved, copied and deleted

Date: 17 November 2026. The effects and sounds plan's game check after stage FX3 (its EXP-C, section 7.2), in one
project on URB_Bar, under Long War (the lab copy). Plain EW is not played in this run. The editor's `effect` and
`sound` families stay off until this run passes; this build enables them.

## What the offline checks settled

Read back from the built map with a fresh reader (`URB_Bar_X68`, quick build; the map's SHA-256 starts
`a3ae5a73457c`), so the run doesn't need to show them:
- every moved effect and sound has its new Location and Rotation in its own export, listed in the level as before;
  the deleted ones (`Emitter_19`, `AmbientSoundSimple_3`) are out of the level's actor list, their exports kept;
- the copies are actors of their own (`Emitter_79` to `_81`, `AmbientSoundSimple_5`), listed, each with its own
  component; the music's copy has its own cue and node (`AmbientSoundSimple_5.SoundCue_3`), and the original's cue is
  untouched; the originals they copy are byte for byte as they were;
- the bar's floor lists (`XComBuildingVolume_0`, `m_aCachedEmitters`): floor 2 (index 1) lists `Emitter_13`, `_37`,
  `_4` and `_45` (the moved `Emitter_14` left), and floor 3 (index 2, the roof) lists the roof copy (`Emitter_81`);
- the claw machine's lights (`Emitter_10`) stay at (331, 1190, 20) where the machine is moved;
- Clear map (with and without the scenery outside kept, its landing moved, an effect moved and copied): the effects
  and sounds left in the level are exactly those the editor's view keeps (9 and 17 of 76); an effects-only project
  built with the lighting baked takes the no-relight path (seconds, no lighting cache). The grounded Skyranger's dust
  stays behind when the landing moves: [F-119](../findings-register.md), open, so the landing is left out here;
- the mixed group (a piece and an effect locked together) is the page's alone: the Build gets plain moves.

What only the game can show: that the game plays each one where its export now puts it and only there, that a copy
plays on its own, that a delete stays deleted when the map's script acts on the effect, that being in a floor's list
is all the cutaway needs (the run's main question), where the game's listener is for ambient sounds, and that the
claw machine's lights don't ride on the machine at run time.

## The project

`EXP-68 effects and sounds` (URB_Bar, [exp68_project.py](../../tools/editor/examples/exp68_project.py), in the
editor's project store), a quick build (`URB_Bar_X68-20261117-151224`). It compiles with two warnings, both expected
(the map's script names the two rat effects), and notes for the floors (`Emitter_14` leaves floor 2's cutaway, the
roof copy joins floor 3's) and the claw machine's lights. Marked shots: `EXP-68-front.png`, `EXP-68-taxi.png`,
`EXP-68-back-wall.png`, `EXP-68-claw.png`, `EXP-68-rats.png`, `EXP-68-sounds.png` ([EXP-68-shots.json](EXP-68-shots.json)).

| No. | What | Where | The prediction |
| --- | --- | --- | --- |
| 1 | the taxi's exhaust steam (`Emitter_16`, Steam_Small) moved and turned a quarter | the pavement in front of the bar, by its front door | it puffs there, turned; nothing at the taxi (A) |
| 2, 3 | two copies of it (`Emitter_79`, `_80`) | beside 1 on the pavement | each puffs on its own |
| 4 | one of the five floodlight beams on the bar's back wall (`Emitter_14`) moved further from the wall | behind the bar | drawn whether the roof is cut away or not |
| b | the other beams (`Emitter_13`, `_37`, `_45`; `_4` round the corner), untouched | the back wall | as the map has them: hidden while the roof is cut away |
| 5 | a third copy of the steam (`Emitter_81`) on the bar's roof | the roof, by the air conditioners | hidden while the roof is cut away, shown with it |
| 6 | rats (`Emitter_18`), which the script sets off when a unit walks into its trigger (T0), moved two tiles | the alley beyond the bar's west end, the far corner from the landing | walking into T0 sets them off at their new place |
| 7 | rats (`Emitter_19`) with their own trigger (T1), deleted | the alley on the landing's side of the west end | walking into T1 sets off nothing |
| 8 | the bar's music (`AmbientSoundSimple_2`, reach about 1000) moved out of the bar | near the landing, by the Skyranger | heard from the start; silent inside the bar (M) |
| 9 | a copy of the music (`AmbientSoundSimple_5`) | by the orange SUV in the far car park, out of the squad's earshot | heard only near it |
| 10 | the taxi's engine idle (`AmbientSoundSimple_3`), deleted | the taxi | silent |
| 11, 12 | the claw machine moved two tiles along the back wall inside the bar; its lights kept where it stood | inside the bar | the machine unlit at its new place, its lights glowing where it was |

## Run 1

What the run adds over the offline checks (Play in game from the editor, on the project; Enable saving for step 7):
1. **Steam (1, 2, 3, A):** three puffs on the pavement in front of the bar, 1 turned against 2 and 3; none at the
   taxi's back.
2. **The cutaway (4, b, 5):** with a soldier outside, the beams and the roof's puff all show. Move a soldier inside
   the bar so the roof is cut away: 4 still drawn, the other beams and 5 gone. Out again: all back.
3. **The script (6, 7):** if a soldier can get there, walk into T0: rats scramble at 6's new place (two tiles from
   where the map has them). Walk into T1: no rats.
4. **Sounds (8, 9, 10, M):** the music near the landing from the start. Then, without moving the soldiers, move the
   camera to 9 (the far car park): is the music heard there? (That says whether the game's listener follows the
   camera or the soldiers.) Inside the bar (M) and at the taxi (10): no music, no engine.
5. **The claw machine (11, 12):** inside the bar, the machine at its new place without its lights, the lights where
   it stood.
6. **Deleted stays deleted:** after a cutaway in and out, and after step 7's load, still no rats at 7 and no engine
   at 10.
7. **Save and reload** once, after the rest: the puffs, 4 and 5 as before, the music where it was moved.
8. Anything odd: a crash, an effect at the map's own place, one playing twice.

## Result

**Run 1 passed** (17 November 2026, played by the user under Long War). The user: "verified in game, almost all of it
works as expected", the one thing noticed being that after a reload the Skyranger was gone, its shadow left on the
ground. That is Long War's own doing, not the build's ([F-120](../findings-register.md), accepted):
- The lab game's log: on loading the battle, Long War's landing-zone mutator (`XComLZMutator.PostLevelLoaded`) picked
  one of the map's seven landings at random (entry 1, the squad's spawn points round (-1297, -1361)), and its
  `HideDropShip` hid and destroyed the map's grounded Skyranger (`XComLevelActor_138`), its lights (`Emitter_78`), its
  idle sound and its dust (`Emitter_0`), as it does on every Long War battle whatever landing it picks. The ship seen
  at the start was the intro's dropship (in the streamed `CIN_DropshipIntros_URB_Bar_X68`), parked where it landed.
- On the reload the travel names the intro stream but the game doesn't stream it (no `AddStreamingMap` for it, none of
  its actors in the checkpoint), and the mutator's `PostLoadSaveGame` runs `HideDropShip` again with the saved landing.
  So there is no Skyranger at all; its shadow is baked into the ground's lightmap.
- An unedited Long War map shows the same in the lab's log of 15 November (`URB_OfficePaper_EWI`, a play and a
  reload): the intro streamed on each new battle, not on the reload, and the mutator destroying the map's grounded
  Skyranger (`XComLevelActor_551`) each time.

What it settles for the editor (the user reported nothing else amiss): effects and sounds moved, turned, copied and
deleted play as the Build writes them, a copy on its own, a delete stays deleted through cutaways and a save and
reload, and a floor's list is all the cutaway needs. Not told apart in the report: whether the rats' triggers were
walked (step 3), and whether the music was heard with only the camera at its copy (step 4's question of where the
game's listener is), which EXP-E still needs. The `effect` and `sound` families build for every project from now on.
