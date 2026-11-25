# EXP-53: each kind of mission played on a map as the game has it

Date: 15 November 2026. Status: **run 15 November**, all seven runs played by hand under LWR (see
[Result](#result)). Plan:
mission-types-plan.md, section 6 (and O-1, O-2, O-4 in section 7).
Finding: F-105 (which record a battle gets).

## What it checks

Play in game now plays the mission the header's Mission picker shows (Part A). A map opened with no project plays its
own record for that mission: nothing is installed for the map's first record; any other gets a copy of its record
ahead of the map's own while the game runs (O-1), taken out when the game closes. Nothing of the editor's edits is in
these runs: only the path from the picker to the battle.

The extra commands of Part A2 (the content options `?Meld=1`, `?CapturePoints=1`, `?RadarArrays=1`; a terror site's
civilians; a UFO's type; a council mission's type) are written but left out of plays until these runs show them
working. A run that tries them needs the editor started with them:
`python tools/viewer/viewer.py serve --try-mission-lines` (in place of `xcom_editor.cmd`, so on port 8768; stop it and
start `xcom_editor.cmd` again after). The play window's line under the mission names what a play goes without.

## Setup

- In the lab copy, as every run. XCOM closed. Maps opened from the map browser, **no project open**.
- Each run: pick the mission in the header (or in the play window's select), **Play in game**, let the battle start,
  look at the first turn, move a soldier or two, quit. Game maps' **Undo everything** after the last run (or after
  any run that leaves something behind).
- Claude reads `Launch.log` after each run (the mission handler's state changes, the mutators' lines); the part by
  hand is a start and a look. No run saves (a battle started this way can't be saved).

## Runs

| Run | Map, mission | What it adds | Look for |
| --- | --- | --- | --- |
| 1 | `URB_StreetHurricane`, Council bomb (its second record: the copy ahead of the map's own, O-1) | the bomb kind; O-1 | the timer and the objective show; a power node can be switched off; LWR's bomb mutator logs "enabled" |
| 2 | `URB_PoliceStation`, Data recovery | the capture points (O-2: with and without `--try-mission-lines`) | the operative at the encoder; the capture points and objectives; EXALT drops in |
| 3 | `URB_LiquorStore`, Covert extraction | radar arrays (O-2) | the operative, the radar arrays, the evac |
| 4 | `URB_PierA`, Council rescue | a council kind | the VIP; the drop-ins when the squad moves |
| 5 | a crashed small scout's map, Crashed UFO | a UFO kind (with `--try-mission-lines`: the ship type) | the UFO's pods; Meld |
| 6 | `URB_Bar_Terror`, Terror (its only record: nothing installed) | terror (O-4) | first without the civilians' line: does it load? (**answered 15 November**: no, it hangs at the loading screen, F-107, seen on `URB_StreetHurricane_Terror`.) Then with it: civilians stand and have looks (**passed 15 November**, the `hurr+` variant's Terror record with `--try-mission-lines`: it loaded and played; the line is now in every terror play) |
| 7 | an alien base, the Temple Ship, base defence, EXALT HQ, a Slingshot map | the rest | does each start, and does its script begin? Each becomes "works" or "not on this path" |

Runs 1 to 4 play a record that is not their map's first, so each also tries O-1. None blocks the rest.

## After the runs

Each kind's state in `tools/viewer/missions.py` (`KINDS`: works, untried, no) follows what was seen, and an A2 line
that worked moves into plays (its kind's state to `works`). The play window's lines follow the table. Results go into
the findings register and this note.

[EXP-54](EXP-54-added-missions.md) (a cleared map played as each added kind: a bomb, a terror site, a crashed UFO
with a UFO building) and [EXP-55](EXP-55-moved-capture-point.md) (a data recovery with a capture point moved, into
another room of the police station) have their projects, builds and marked shots.

## Result

Played by hand on 15 November 2026, 01:43 to 02:07, with the editor started with `--try-mission-lines` (so with
the open line's options and the UFO type's line). Everything looked fine except the EXALT
missions. Each run's `Launch.log` names the record the battle got, so each play got the record picked; runs 1 to 4
played records that aren't their map's first, so **O-1 works** (the copy ahead of the map's own).

| Run | Played | Result |
| --- | --- | --- |
| 1 | `URB_StreetHurricane`, Council bomb | **Passed.** LWR's mutator: "BOMB MAP, NO ADJUSTMENT REQUIRED". |
| 2 | `URB_PoliceStation`, Data recovery | **Hangs** at "Mission Briefing: Please Wait" with "SAVING..." (screenshot from the run): Long War's save and reload of every EXALT battle, which can't finish here (F-109, F-89). The capture points' and radar arrays' packages loaded with the map. |
| 3 | `URB_LiquorStore`, Covert extraction | **Hangs** as run 2 (F-109). The radar arrays' package loaded. |
| 4 | `URB_PierA`, Council rescue | **Passed.** |
| 5 | `CSmallScout_Quagmire`, Crashed UFO | **Passed**, but no command pod (the Outsider) in the UFO: a test battle has no commander (F-110). LWR found the UFO and picked a commander spawn point in it. Meld's package loaded. |
| 6 | Terror | **Passed** earlier the same night (F-107). |
| 7 | Base defence (`EWI_HQAssault`), EXALT HQ (`EWI_ExaltHQAssault`), alien base (`AlienBase01`), Confounding Light (`DLC1_2_CnfndLight`) | Base defence, the alien base and Confounding Light **passed**; the alien base without its Sectoid Commander (F-110). EXALT HQ **hangs** as run 2 (F-109). The Temple Ship wasn't played. |

- **O-2 answered:** the open line's options load their packages (`CapturePointResources`, `RadarArrayResources`,
  `MeldResources`). They stay out of standard plays: every kind played works without them, and as standard they
  would change every abduction's start, which no run tried.
- **O-3:** the UFO type's line was in run 5, which worked; whether it set anything the log doesn't show. It stays
  untried, as does the council type's (not played: the Chryssalid Hive and Portent).
- **In `missions.py`:** council bomb, council rescue, crashed UFO, base defence and alien base are `works`; data
  recovery, covert extraction and the EXALT raid are `hangs` (new: "Hangs at the start under Long War", with F-109's
  sentence); the story missions note that Confounding Light works. Landed UFO, council assault and extraction, the
  Temple Ship and the rest of the story maps stay untried.
