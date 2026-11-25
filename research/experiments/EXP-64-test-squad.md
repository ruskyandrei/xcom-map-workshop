# EXP-64: the test squad in the game

Date: 16 November 2026. Status: **runs 1 to 4 passed** (16 November, the lab copy of LWR): every
check below was played by hand and passed; no shots were taken. The test squad plan's game checks: stage Q0's runtime probes
(what the game makes of the records the editor writes) and stage Q5's acceptance runs, together. Until now every
Play in game landed the same six soldiers written into the code (EXP-29 run 6); since stages Q1 to Q4 the squad is
the one saved in **Settings → Test squad setup…**, written from the install's own data. The scripts' reading is
[test-squad-records.md](../test-squad-records.md) and findings register F-115. This run adds only what the scripts
can't show: what the battle does with each record.

## What is known offline

- The default squad's text is the old six's, byte for byte, plus each soldier's class record
  (`kClass=(eType=n)`), which the old six left empty (test_squad_records). The old six's gear is LWR's Gauss tier
  (F-115): Gauss Assault Rifles, a Gauss Autorifle with a Recoilless Launcher, a Gauss Long Rifle.
- Each record is checked against the family's rules before any file is touched: the armour gives a body
  (`MapSoldierToPawn`'s list), a MEC's gun comes first, a SHIV has a gun, the names fit the command, at most eight
  units under LWR (test_squad_records, test_squad_play).
- LWR's charges: a battle scanner's are written as `aUpgrades[8] = 2 × count`, a smoke grenade's as
  `aUpgrades[44] = 2`; a MEC's frag grenades get none (scripts, test-squad-records.md section 6).
- Units 7 and 8 land one tile behind landing points 1 and 2; the prefab test's reserved tiles cover that tile
  (test_prefab_stage).
- The squads below make squad texts of 4,102 (six) and 6,470 (eight) characters, against the old six's 4,755
  (before the class records).

## The squads

Two shared squad files, imported with **Import…** in the setup and then saved (Save), each checked playable against
the LWR install on 16 November:

[EXP-64-six.xcomsquad.json](EXP-64-six.xcomsquad.json), the plan's six; one warning (only one SHIV acts each turn) and
the grenadier's backpack warning:

| Unit | Kind | Armour | Gear | What it probes |
| --- | --- | --- | --- | --- |
| Tracks | SHIV | SHIV Chassis | Autocannon | a SHIV's body, gun and moves; no ladders |
| Hover | SHIV | Hover SHIV Chassis | Autocannon | the hover chassis takes off and lands |
| Iron Fist | MEC trooper | MEC1 'Paladin' | Minigun, Kinetic Strike Module, Flamethrower | both modules there and working, the flamethrower's 2 charges |
| Gren Hook | Support | Corsair Armor (grapple) | Pistol, Assault Rifle; Battle Scanner, HE, Smoke, Acid Grenade | the grapple onto a roof; the scanner's and smoke's charges; the fourth item in the backpack |
| Sky Wing | Tactical | Archangel Armor | Pistol, Assault Rifle; HE Grenade | flight from the armour |
| Long Eye | Marksman | Tactical Armor | Pistol, Sniper Rifle; HE Grenade; Squadsight | a shot at an alien only another unit sees |

[EXP-64-eight.xcomsquad.json](EXP-64-eight.xcomsquad.json): the default six and two more soldiers (a support with a
medikit, a tactical with a shotgun), for the seventh and eighth landing places.

## Run 1 (passed): the default six

In the lab copy. **Reset to default** and Save in the setup (or no squad saved yet), then Play in game on a map,
played by hand with F9 shots; the unit info screen shows each unit's stats and perks.
1. Six soldiers with bodies, named as before (Tom Alpha … Sam Foxtrot), each with its class label in the HUD
   (Tactical, Support, Weapons, Marksman) where the old plays showed a rookie's.
2. The weapons read as the panel names them (Gauss Assault Rifle, Gauss Autorifle, Recoilless Launcher, Gauss Long
   Rifle, Shotgun). The heavy fires the autorifle and the launcher.
3. A unit's stats are its base stats plus its armour's and weapons' bonuses, once (the unit info screen against the
   panel's base stats and the armour's line).

## Run 2 (passed): the six

Import EXP-64-six, Save, Play in game on a map with a roof the grapple can reach near the landing.
1. All six land with bodies, names and gear as listed; the MEC shows the MEC class, the SHIVs none.
2. Tracks moves and fires and offers no ladder climb; Hover takes off and lands. Once one SHIV has acted, the other
   waits for the next turn (LWR's rule; the editor leaves the game's options alone).
3. Iron Fist has both the kinetic strike and the flamethrower; each works (the strike's damage to cover, the
   flamethrower's two uses).
4. Gren Hook grapples onto the roof. The battle scanner, HE, smoke and acid grenades are each usable; the scanner
   shows its charges (one per scanner), smoke one. Note where the fourth item went (the backpack) and whether the
   interface offers all four.
5. Sky Wing takes off and lands.
6. Long Eye fires at an alien beyond its own sight that another unit sees.

## Run 3 (passed): eight units

Import EXP-64-eight, Save.
1. Play in game on a map: units 7 and 8 land one tile behind landing points 1 and 2, on open tiles, not inside
   anything.
2. A prefab test (**Test in game…** in the prefab builder) with the eight: the same, inside the stage's landing room.

## Run 4 (passed): save and load

With the six, a play with **Enable saving** on: save in the battle, load the save, and check that names, gear, charges
(the scanner's, the flamethrower's) and Squadsight are still there. After leaving the game, the editor has put back
the game's `XComContent.ini` as it was.

## Not covered

Plain Enemy Within and Long War without Rebalance hold soldiers only, six at most, from the same records; no plain EW
install is here to play them, so their squads are not in this run.

Pass: each check as written. A fail is a finding (F-115 or a new one) with the shot and the record's text.
