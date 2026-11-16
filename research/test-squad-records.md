# The test squad's records: what the game does with a squad written into the profile

16 November 2026. The test squad plan's stage Q0, the part read from the scripts (the plan is private). Read-only:
the decompiled XComGame scripts (`<lab>\reference\XComGame-decompiled`, LWR's), LWR's tactical mutator
(`RebalanceMutator`, decompiled from `LWRebalance.u` in the lab's reference copy), and the install's own data
(`XComGame.upk`'s enums: [script_enums.py](../tools/upk/script_enums.py); `DefaultGameCore.ini` and the localisation:
[gamedata.py](../tools/viewer/gamedata.py)). Nothing was run in the game for this note; the runs that check it are
EXP-64's. The rules the editor follows are in [squadrecords.py](../tools/viewer/squadrecords.py); findings register
F-115.

## 1. The path

`XComTacticalGRI.InitBattle`, started from the shell (a console `open`: F-72), calls `XGBattle.SetProfileSettings`
and `Start`. `XGBattle_SP.InitDescription` builds the battle's description and its unit content from the profile's
`m_aSoldiers` (`XGBattleDesc.BuildUnitContentFromEnums`: the pawn from the armour, the first large item, the pistol,
the first small item and the gender), and `InitPlayers` calls `XGPlayer.LoadSquad` with the soldiers, the landing's
spawn points and those pawn types. For each record `LoadSquad` makes an `XGCharacter_Soldier` (SHIVs too), sets its
`TSoldier` and `TCharacter` as written, spawns the unit, adds `aStatModifiers`, sets the appearance (soldier
characters only) and applies the inventory (`XGLoadoutMgr.ApplyInventory`), then lets LWR's mutator set the item
charges (`LWRItemCharges`). `XGUnit.Init` adds the character's `aStats` as the unit's stats.

## 2. What each field does

| Field | On this path |
| --- | --- |
| `kChar.iType` | 2 (`eChar_Soldier`): the soldier and MEC loadout, appearance applied; 3 (`eChar_Tank`): the tank loadout. 0 would rebuild the character from the config by pawn type. |
| `kChar.aStats` | the base stats, used as written. Armour, weapons and items add theirs every turn (`LoadoutChanged_UpdateModifiers`, `GetInventoryStatModifiers`: the armour's bonus, LWR's per-item balance rows, the weapon's, each item's weight), so the record holds no armour bonus. LWR keeps codes in `aStats[5]` and `aStats[15]`: left at 0. |
| `kChar.aAbilities`, `aProperties` | counts, as `XGTacticalGameCore.BuildCharacter` makes them: each of the config row's eight abilities and six properties is counted, zeros included (`aAbilities[0]=7` is seven empty slots; `aAbilities[27]` is take cover). Scripts read them as booleans (`> 0`, index 0 skipped); the properties are read by character type from the config, not from the record. |
| `kChar.aTraversals` | the row's traversal flags, at their `ETraversalType` entries (jump up is 11, wall climb 10, break wall 13). Read natively by pathing. |
| `kChar.aUpgrades` | the perks: `HasUpgrade` is `aUpgrades[i] > 0` (perk 10 at 2 counts as off). 1 is an owned perk. LWR keeps more in some entries (section 5). |
| `kChar.eClass` | the class's handling: 6 (`eSC_Mec`) the MEC loadout and MEC rules; class perks and experience. |
| `kChar.strName` | the name shown for a SHIV. |
| `kChar.kInventory` | the loadout (section 3); `iArmor` also gives the body (section 4). |
| `kSoldier.kClass.eType` | the class label of the HUD, and LWR's class (its mutator's `GetUnitClass`, for a rank above 0): 1 to 4 are the four base classes (as `ESoldierClass`), the two-digit codes LWR's subclasses. |
| `kSoldier.iRank` | names, the unit flag, experience and morale; no stats. |
| `kSoldier.kAppearance` | applied to soldier characters only; `iGender` picks the male or female body. |
| `aStatModifiers` | added to the stats. `iHPAfterCombat` is not read; `iUnitLoadoutID` only by multiplayer. |

## 3. The loadout

- **Soldiers and MECs** (`ConvertTInventoryToSoldierLoadout`): an armour with the grapple property gives the grapple
  (item 38) on its own; `iPistol` goes on the right thigh whatever it is (the developer squad's heavy carries its
  machine gun there and its rocket launcher as its large item). A soldier's large items: the first in the main
  place, the second in the second, the rest dropped. A MEC's large items each go to the place their item's class
  names (`m_eEquipLocation`: the kinetic strike module and the flamethrower have places of their own; a gun takes the
  right arm), all equipped, the first in hand. Small items: a backpack item (`eWP_Backpack`) to the backpack, the
  others to the left thigh, chest and belt, the fourth and later to the backpack, which holds five. The armour's
  small-slot count is never checked here.
- **SHIVs** (`ConvertTInventoryToTankLoadout`): the first large item alone. Small items give their stat bonuses (the
  stats read `kInventory`) but no item to use.
- **Custom items**: only the psi amp and two alien items are read; the psi amp is added on its own to a psionic unit.

## 4. The body

`XGBattleDesc.MapSoldierToPawn` picks the pawn from `iArmor` alone: LWR's soldier armours (by number 57 to 68, 159,
160, 182, each with a male and a female body), the three SHIV chassis (113 to 115; 115 the hover SHIV's), the MEC
suits (145, 148, 191, 193 to 195, 210) and the base augments (192). Any other armour gives pawn 0, no unit is
spawned, and the soldier is missing from the battle without an error. A MEC needs both its class (`eSC_Mec`, with
`iType` 2) and a MEC suit; a SHIV is `iType` 3 in a chassis.

## 5. What LWR adds

- **Charges.** `LWRItemCharges` counts frag and acid grenades by the items carried, but gives a battle scanner and a
  smoke grenade nothing of their own: scanners get `aUpgrades[8] >> 1` charges (plus one when bit 1, the perk, is
  set), a smoke grenade one charge when `aUpgrades[44] >> 1` is set. A record without those values carries a
  scanner or smoke grenade with no charges, and the ability is hidden. The editor writes twice the scanners carried
  into entry 8 and 2 into entry 44 for a smoke grenade, as the tactical code reads them; how LWR's strategy layer
  writes them is not in the scripts read.
- **MECs**: their frag grenades, alien grenades and medikits are set to 0 charges; a flamethrower gets 2.
- **More in perk entries**: officer and squad-leader bits (`&2`), a Foundry bitfield in entry 123, states set in battle.
  The editor writes 1 for a chosen perk and touches no other entry.
- **One SHIV a turn** (`DeactivateAllShivsButOne`): unless second-wave option 28 (Robot Overlords) is on, once one
  SHIV acts the others lose their actions for the turn. The 2-MEC limit is the strategy layer's only.

## 6. The squad's size

`LoadSquad` takes as many records as are written (the squad holds 128). The spawn points are the landing's six; unit
7 and on take point `I % 6`, moved one tile (96 units) back along its rotation and snapped to the nearest valid place.
The landing needs six player spawn points. The editor keeps to eight; the prefab test's reserved tiles take a tile
round every point, so units 7 and 8 stay clear of the prefab.

## 7. What is native, and what EXP-64 checks

Not visible in the scripts: how the targeting builds squadsight from `aUpgrades[3]`, the abilities built from armour
(flight), the armour's stat bonus, pathing's reading of the traversals, and `IsOptionEnabled` (whether Robot
Overlords is on for a console battle). The plan's runtime checks (EXP-64) cover those, the eight-unit line through
the game's own parser, and the charges above.

## 8. Plain Enemy Within and Long War without Rebalance

No script of either was read: the editor writes soldiers only there, in the base game's own armours (by name: LWR's
`MapSoldierToPawn` keeps a case for each beside its own), at most six, and the base character from each install's
own config row.
