# EXP-55: a data recovery with a capture point moved

Date: 15 November 2026. Status: **prepared; can't be played under LWR yet**: EXP-53 run 2 showed that a data
recovery started from the editor stops at Long War's "Mission Briefing: Please Wait" (F-109, waiting on F-89). Plan:
mission-types-plan.md, Part E and section 6 (and the risk under section 7:
Part E moves objects the Kismet names). Run after [EXP-53](EXP-53-mission-kinds.md) run 2 (Police Station's data
recovery as the game has it), which says whether the mission works on this path at all. Finding: F-108 (fixed on
the way).

## What it checks

A mission's own objects stream with its record, and Part E lets a project move them: the Build writes a copy of the
stream with the moved actors set in place (`stream_copy.py --moves`). The moved objects keep their names, so the
Kismet's references to them hold. But a script can also hold a place (a vector, a matinee), so this run plays a
mission with objectives and waves:
- does the capture point work at its new place: soldiers in its volume capture it;
- do the waves still come;
- is nothing left at the old place.

The plan has the point moved into a new building. This run moves it within the police station instead, into
another room on the same floor; a building added round it would be a second run.

## What is built (offline)

The project **EXP-55 moved capture point**, saved in the editor's store, is built by
`python -B tools/editor/examples/exp55_project.py <scratch folder> --store`. It is a quick build, 3 seconds, giving
`URB_PoliceS_X55`, the project's last build in the editor's builds folder.

- **Police Station's data recovery** (its third record, `eMission_CaptureAndHold`, streaming
  `URB_PoliceStation_CNH`) is the project's only mission. The variant's one record streams the variant's own copy of
  that stream.
- **Capture point 1 moved**: its group, the capture volume `XComCapturePointVolume_1` (7 by 6 tiles) and the encoder
  it captures (`XComCapturePointActor_0`), moved together by one tile along x and nine along y, at the same height:
  - the encoder from (-96, -1536, 80) to (0, -672, 80), keeping the quarter turn its archetype gives it;
  - the volume's box from x -480 to 192, y -1824 to -1248 to x -384 to 288, y -960 to -384.
  - The place is the nearest at least six tiles away, clear of the old place and of capture point 0, inside the
    police station (`XComBuildingVolume_2`), with floor at the encoder's floor height (80) under every tile of the
    volume. The old place was a room at a corner of the station; the new box takes in an office and the end of the
    room beside it (an inner wall crosses it).
- **The stream copy** `URB_PoliceStation_CNH_URB_PoliceS_X55`: the two actors moved, nothing taken out, the same 57
  actors listed.
- **The base map's tiles**: rebuilt under the encoder's old place and seeded and rebuilt under its new one (the
  encoder's mesh collides).
- **Unchanged**: capture point 0 (the transmitter, at (-1632, 1632) outside the station), the operative's spawn point, the
  rebuild volume the stream has at the old place, the waves' system, the landing.

Picture `EXP-55-moved.png` (not in the repository): the moved capture point.

Picture `EXP-55-overview.png` (not in the repository): overview.

## What to look at

Open the project **EXP-55 moved capture point** in the editor (the main editor, port 8768). The header shows Data
recovery (the project's only mission). **Play in game**. The game must be closed first. The main editor runs with
`--try-mission-lines` for now, so the play has the content options (`?CapturePoints=1` among them), which are still
untried (O-2, EXP-53 run 2). Claude reads `Launch.log` after the run.

**Under LWR** (the lab copy):
1. **The encoder** (mark 1) stands in the office past the room it was in, on the floor, turned as before.
2. **The capture**: soldiers in the dashed box capture it (the objective's counter moves); out of it, they don't.
3. **The waves**: EXALT drops in as the mission goes on.
4. **The old room** (mark 2): nothing to capture there, and nothing odd (no invisible wall or blocked tile where
   the encoder stood).
5. **Capture point 0** (the transmitter, overview mark 3) works as before.
6. Anything odd: a crash on loading, the objective missing, a hang.

Not looked at in this run:
- plain Enemy Within (no squad is set for it yet);
- baked lighting (quick build);
- the rebuild volume left at the old place (it rebuilds tiles where nothing now stands, which should do no harm).

## Result

Not run yet.
