# EXP-30: the campaign's first map in the editor (Act1_IntroLevel)

Date: 10 November 2026. Testers reported that Act1_IntroLevel, which they took for the map of the campaign's first
mission, was missing from the map browser. The user asked why, then to add it; once it was clear that LWR's first
mission plays another map (below), the user chose to keep it and make it playable.

## Why it was missing

The map browser lists the maps the install's `DefaultMaps.ini` records name, live records only
(`tools/viewer/maplist.py`). LWR keeps both of Act1_IntroLevel's records commented out:

- `;Maps=( ... Name="Act1_IntroLevel", DisplayName="Helo Crash (Abduction) |4", MissionType=eMission_Abduction ...`,
  streaming `CIN_DropshipIntros`;
- `;Maps=( ... Name="Act1_IntroLevel", DisplayName="IntroLevel Tutorial 1 (Basic Training)", MissionType=eMission_Special ...`,
  streaming `Act1_IntroLevel_Anim`, `Act1_IntroLevel_Script`, `CIN_DropshipIntros_Intro` and `Soldier2Spotted`.

The campaign still plays the map: `XComGame.upk` names `Act1_IntroLevel`, `Act1_IntroLevel_Anim` and
`Act1_IntroLevel_Script` itself, and `DefaultEngine.ini` loads the map's content under "Tutorial maps". The base game's
EU `DefaultMaps.ini` has the Basic Training record live; Enemy Within reads the `XEW` one. LWR's
`DefaultMiniMods.ini` lists the map in `AbductionMapRules`, but with no live record it never comes up as an abduction.

## What changed (offline)

- The editor takes the commented-out abduction record as the map's (`maplist.SWITCHED_OFF`, `maplist.records`): the
  map browser lists it as "Basic Training (tutorial map)" under Abduction, the exporter reads its missions, and a
  variant's record (Build, Play in game) is a live copy of it. The tutorial's record is not taken (it streams the
  tutorial's script). The other maps whose records are all commented out stay out: Long War's EU maps (URB_Museum,
  URB_Museum_Euro, URB_Demolition, which only the base game ships) and URB_GasStation, whose record streams
  `EU2EW_Textures`.
- The map exported cleanly (export 18: 527 pieces, 153 lights, 22 diagnostics, all material approximations) and
  opens in the editor.
- The first Build on it, the project `EXP-30 intro map police car deleted` (the police car
  `XComDestructibleActor_54` and its glass `XComFracLevelActor_3` deleted, variant `Act1_IntroLe_Exp30_d57c`), stopped
  for want of a volume to clone a rebuild volume from: F-77. With the fix it built in full (lighting baked: 45
  components written, 7 shadow maps); the two pieces' tiles are rebuilt by volumes cloned from
  `LightmassImportanceVolume_1`.
- `CIN_DropshipIntros` has no landing for Act1_IntroLevel (`intro_copy.py` made no copy): a name it doesn't know falls
  through to `CIN_DS_Stop` (F-45), so neither the map nor its variant should get a Skyranger landing. The map has no
  landing zones in `DefaultLZMutator.ini`, so the squad should start on the map's own start points.

## LWR's first mission is not this map

EXP-03 found that a new campaign's first mission is hard-coded: `XGGeoscape.TakeFirstMission` calls `DetermineMap`,
which picks the record whose DisplayName is `URB_CommercialAlley_EWI (Commercial Alley Redux) |0`. So under LWR the
first mission plays URB_CommercialAlley_EWI, which the map browser lists already (Commercial Alley Redux).
Act1_IntroLevel is the tutorial's map (Basic Training); its own Kismet is the tutorial's wiring: on load it finds four
squad members by the tutorial's names (`Unit01` to `Unit04`), turns panic off and sets `SkipMovie`, and it waits on
tutorial events (`MissionControl`, `SkipThisMap`, `Soldier2Spotted`, `KillDelta3`, `CIN_IntroFinished`).

## Runs

To play, in the LWR install the editor plays in, from the editor (Play in game):

1. **The map alone** (map browser: Basic Training (tutorial map), Play in game). Nothing is installed; the game opens
   the map by name with no record (`GetCurrentMapMetaData` finds none, EXP-29). Does a battle start, with a squad and
   aliens, and does the tutorial's script stay out of it?
2. **The EXP-30 project** (Load: `EXP-30 intro map police car deleted`, Play in game). Its record is the live copy of
   the abduction record. Does the battle start, is the police car gone (marked shots:
   overview (`EXP-30-run2-overview.png`), close-up (`EXP-30-run2-car.png`); `EXP-30-run2-shots.json`), and can
   soldiers stand and move where it stood (F-77's rebuild volumes)?
3. **The map alone again**, once Play in game puts a live copy of the abduction record in for it (F-78).

**Run 1 (12:35, the map alone): the game crashed.** The user: it "opened for 1s but then the game crashed right
away". In the lab copy, then switched in under the game's folder name. `Launch.log`: `LoadMap: Act1_IntroLevel`, no
streams but the game's own `CIN_Sectoid`, `CIN_Soldier` and `CIN_MEC`, no landing zones for the map (LWR's mutator
used the map's six `XComSpawnPoint`s around (-673, -240)), the squad of six and four sectoid pods spawned by 7.1 s,
then nothing for 4.3 s and `Critical error` at 11.48 s (addresses 0xafca98, 0x954118 and 0x981a99 in XComEW.exe;
dump `unreal-v8917-2026.11.10-12.35.10.dmp`). The address appears in no other log here. Not known yet: whether it is
the missing record (`GetCurrentMapMetaData` finds none) or the tutorial's Kismet running without the tutorial.

The user chose then to keep the map and make it playable (the label became "Basic Training (tutorial map)").

**Run 2 (12:42, the project): passed.** The user: "works. car is gone", with two shots: the street with the other
police car standing and no car where the deleted one stood, soldiers on the road beside it. "I don't know if I can path
all the way where the car was, there seems to be a limit to the playing area." `Launch.log`: `LoadMap:
Act1_IntroLe_Exp30_d57c`, the record's `CIN_DropshipIntros` streamed, `m_bTacticalIntroDone` 1.6 s after the map loaded
(no landing: the intro has no case for the map, F-45), `DoWorldDataRebuild`, a normal exit after 2 min 15 s.
- So run 1's crash was the missing record, not the tutorial's Kismet, which ran here too (the variant keeps it): F-78.
  With a record the intro streams and ends at once; with none the battle never got past it.
- The pathing limit: the map's tactical grid is 62 by 19 tiles (LWR's spawn mutator), and the car's tiles are rows
  16 to 18 (`native_copy.py`'s rebuild report), the grid's last rows; the boundary line in the user's shot runs along
  that spot. Standing where the car stood is not shown either way (F-77 stays Fixed).

Run 3 not played.
