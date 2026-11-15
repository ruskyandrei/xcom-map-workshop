# EXP-54: a cleared map played as each added kind of mission

Date: 15 November 2026. Status: **prepared, not run.** Plan:
mission-types-plan.md, Part D and section 6 (O-5 in section 7). Earlier:
[EXP-51](EXP-51-cleared-bar.md) (the cleared Bar this project copies, played and passed),
[EXP-53](EXP-53-mission-kinds.md) (each kind on a map as the game has it).

## What it checks

A project can give a map a kind of mission its base map has no record of (Part D: an added kind). The Build writes a
record for it, made from the base map's abduction record with the kind's mission type, council type, ship and a
display name of its own, and Play in game installs it. None of the added kinds has been played. This run plays the
three that need something of the map:
- **a council bomb**: the record streams `URB_Slaughterhouse_Stream`, and Long War's bomb mutator should put the
  bomb and its power nodes on this map (the Build's note `mission-bomb`);
- **a terror site**: civilians should spawn, with their looks (the civilians' line, working since EXP-53 run 6);
- **a crashed small scout** on a map with a UFO building: Long War's pod mutator should find the building whose
  volume carries `IsUfo` and pick its commander spawn point in it (O-5). No commander comes in a test battle
  (F-110, EXP-53 run 5), so the log's lines say whether it worked.

## What is built (offline)

The project **EXP-54 added missions**, saved in the editor's store, is built by
`python -B tools/editor/examples/exp54_project.py <scratch folder> --store`. It is a quick build (the lighting not
baked), 8 seconds, giving `URB_Bar_X54`, the project's last build in the editor's builds folder.

- **EXP-51's cleared Bar** as it was played: 964 pieces deleted, two landing zones on fields of Bar's own floor
  pieces, the shed of `URB_ResearchOutpost` as a building made from nothing.
- **The shed is the project's UFO building** (its kind `ufo`), so its building volume carries `IsUfo`.
- **Missions**: a council bomb, a terror site and a crashed UFO (small scout), none of Bar's own. The Build wrote
  three records, all `URB_Bar_X54`, out of rotation:
  - `URB_Bar_X54 (EXP-54 added missions, Terror)`: `eMission_TerrorSite`;
  - `URB_Bar_X54_Bomb (EXP-54 added missions, Council bomb)`: `eMission_Special`, `eFCMType_Bomb`, streaming
    `URB_Slaughterhouse_Stream`;
  - `URB_Bar_X54 (EXP-54 added missions, Crashed UFO)`: `eMission_Crash`, `eShip_UFOSmallScout`.
  - A play finds its record by the mission's kind, so their order in the file doesn't matter.
- The compiler warns of a crate in the shed over two floor tiles (`floor-headroom`, as in EXP-51) and that zone 2
  is Long War's only (`landing-lwr-only`).

Picture `EXP-54-overview.png` (not in the repository): overview.

Picture `EXP-54-shed.png` (not in the repository): the shed.

## What to look at

Open the project **EXP-54 added missions** in the editor (the main editor, port 8768). Pick the mission in the
header's Mission picker (the three are marked "added"), then **Play in game**, or click a zone and **Land here** to
land there (it plays the picked mission too). The game must be closed first. Claude
reads `Launch.log` after each run.

**Under LWR** (the lab copy), one battle each:
1. **Council bomb**:
   - Long War's bomb mutator logs that it is enabled.
   - The bomb and its power nodes stand somewhere on this map, on floor (mark 4: there is floor only in the two
     fields and the shed, so where they go is part of the question).
   - The timer and the objective show; a power node can be switched off.
2. **Terror**:
   - Civilians spawn, with looks, on floor (the battle leaves the loading screen).
   - The civilians' counter shows.
3. **Crashed UFO**:
   - The battle starts.
   - Claude reads the log: LWR's pod mutator "found UFO" with the shed's box and picked its commander spawn point
     in the shed (mark 3). No commander pod comes (F-110).
   - What else the mission asks for on a map with no UFO in it (the ship's power source, its loot) and whether the
     battle can be won.
4. On any of them, anything odd: a crash on loading, the squad somewhere else, a hang.

Not looked at in these runs:
- plain Enemy Within (no squad is set for it yet; under it the bomb would stand where Slaughterhouse has it);
- baked lighting (quick build);
- a landed UFO (the same record with `eMission_LandedUFO`) and other ships.

## Result

Not run yet.
