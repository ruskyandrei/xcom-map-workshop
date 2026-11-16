"""A scratch game folder for the test squad's tests: the few enum entries, config rows and localised names the squad
reads, at the positions LWR has them (the six squaddies' items, the SHIV, the MEC, the armours and items of the
plan's section 2), and nothing else of the game. Its XComGame.upk is a stand-in: `enums()` patches
script_enums.cached to give the entries below for it."""
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from gamedata import script_enums      # the module gamedata reads the enums with (tools/upk)

ITEMS = {0: 'eItem_NONE', 2: 'eItem_Pistol', 3: 'eItem_AssaultRifle', 4: 'eItem_Shotgun', 5: 'eItem_LMG',
         6: 'eItem_SniperRifle', 7: 'eItem_RocketLauncher', 22: 'eItem_MecKineticArm', 23: 'eItem_MecFlameThrower',
         28: 'eItem_Chaingun', 37: 'eItem_PsiAmp', 38: 'eItem_Grapple', 57: 'eItem_END_WEAPONS',
         59: 'eItem_ArmorKevlar', 60: 'eItem_ArmorCarapace', 61: 'eItem_ArmorSkeleton', 63: 'eItem_ArmorArchangel',
         69: 'eItem_Medikit', 81: 'eItem_FragGrenade', 82: 'eItem_SmokeGrenade', 86: 'eItem_GasGrenade',
         87: 'eItem_NeedleGrenade', 97: 'eItem_BattleScanner', 109: 'eItem_ShivMinigun', 113: 'eItem_SHIVDeck_I',
         115: 'eItem_SHIVDeck_III', 120: 'eItem_PlasmaLightRifle_Muton', 193: 'eItem_MecArmor1',
         227: 'eItem_MecArmor1_Flamethrower', 255: 'eItem_MAX'}
CHARACTERS = ['eChar_None', 'eChar_Civilian', 'eChar_Soldier', 'eChar_Tank', 'eChar_Sectoid', 'eChar_MAX']
CLASSES = ['eSC_None', 'eSC_Sniper', 'eSC_HeavyWeapons', 'eSC_Support', 'eSC_Assault', 'eSC_Psi', 'eSC_Mec',
           'eSC_Psi_0', 'eSC_Psi_12', 'eSC_Psi_12', 'eSC_MAX']
PERKS = {0: 'ePerk_None', 3: 'ePerk_SquadSight', 5: 'ePerk_Sprinter', 8: 'ePerk_BattleScanner', 9: 'ePerk_Poisoned',
         44: 'ePerk_SmokeBomb', 172: 'ePerk_MAX'}
ABILITIES = {0: 'eAbility_NONE', 27: 'eAbility_TakeCover', 30: 'eAbility_Fly', 40: 'eAbility_ShotStandard', 96: 'eAbility_MAX'}
CHAR_PROPERTIES = ['eCP_None', 'eCP_Climb', 'eCP_Flight', 'eCP_Robotic', 'eCP_MeleeOnly', 'eCP_Hardened',
                   'eCP_CanGainXP', 'eCP_AirEvade', 'eCP_NoCover', 'eCP_PoisonImmunity', 'eCP_LargeUnit',
                   'eCP_Poisonous', 'eCP_DeathExplosion', 'eCP_DoubleOverwatch', 'eCP_MAX']
STATS = ['eStat_HP', 'eStat_Offense', 'eStat_Defense', 'eStat_Mobility', 'eStat_Strength', 'eStat_ShieldHP',
         'eStat_CouncilMedalAccrued', 'eStat_Will', 'eStat_AppliedSuppression', 'eStat_LowCoverBonus',
         'eStat_SightRadius', 'eStat_WeaponRange', 'eStat_Damage', 'eStat_CriticalShot', 'eStat_CriticalWoundChance',
         'eStat_CriticalWoundsReceived', 'eStat_CloseCombat', 'eStat_FlightFuel', 'eStat_Reaction', 'eStat_MAX']
TRAVERSALS = ['eTraversal_None', 'eTraversal_Normal', 'eTraversal_ClimbOver', 'eTraversal_ClimbOnto',
              'eTraversal_ClimbLadder', 'eTraversal_DropDown', 'eTraversal_Grapple', 'eTraversal_Landing',
              'eTraversal_BreakWindow', 'eTraversal_KickDoor', 'eTraversal_WallClimb', 'eTraversal_JumpUp',
              'eTraversal_Ramp', 'eTraversal_BreakWall', 'eTraversal_Unreachable', 'eTraversal_MAX']
ARMOR_PROPERTIES = ['eAP_None', 'eAP_Tank', 'eAP_Grapple', 'eAP_Psi', 'eAP_LightWeaponLimited_DEPRECATED',
                    'eAP_BackpackLimited_DEPRECATED', 'eAP_AirEvade', 'eAP_FireImmunity', 'eAP_PoisonImmunity',
                    'eAP_MEC', 'eAP_MAX']
WEAPON_PROPERTIES = ['eWP_None', 'eWP_Secondary', 'eWP_Pistol', 'eWP_AnyClass', 'eWP_Support', 'eWP_Rifle',
                     'eWP_Assault', 'eWP_Sniper', 'eWP_Heavy', 'eWP_Explosive', 'eWP_UnlimitedAmmo', 'eWP_Overheats',
                     'eWP_Psionic', 'eWP_Melee', 'eWP_Integrated', 'eWP_Encumber', 'eWP_MoveLimited', 'eWP_Backpack',
                     'eWP_NoReload', 'eWP_CantReact', 'eWP_Mec', 'eWP_MAX']
SIZES = ['eItemSize_Small', 'eItemSize_Large', 'eItemSize_Armor', 'eItemSize_MAX']
COUNTRIES = {0: 'eCountry_USA', 7: 'eCountry_India', 9: 'eCountry_Italy', 15: 'eCountry_Canada',
             21: 'eCountry_Mexico', 35: 'eCountry_Belgium', 36: 'eCountry_Belgium_1', 131: 'eCountry_MAX'}


def spread(found, length, stem):
    return [found.get(i, f'{stem}_Slot{i}') for i in range(length)]


def enum_records():
    lists = dict(EItemType=spread(ITEMS, 256, 'eItem'), ECharacter=CHARACTERS, ESoldierClass=CLASSES,
                 EPerkType=spread(PERKS, 173, 'ePerk'), EAbility=spread(ABILITIES, 97, 'eAbility'),
                 ECharacterProperty=CHAR_PROPERTIES, ECharacterStat=STATS, ETraversalType=TRAVERSALS,
                 EArmorProperty=ARMOR_PROPERTIES, EWeaponProperty=WEAPON_PROPERTIES, EItemSize=SIZES,
                 ECountry=spread(COUNTRIES, 132, 'eCountry'))
    out = {}
    for name, entries in lists.items():
        twice = sorted({e for e in entries if entries.count(e) > 1})
        out[name] = dict(path=f'XGGameData.{name}', entries=entries, ambiguous=twice)
    return out


def _abilities(*names):
    names = list(names) + ['0'] * (8 - len(names))
    return ', '.join(f'ABILITIES[{i}]={n}' for i, n in enumerate(names))


def _props(key, length, *names):
    names = list(names) + ['0'] * (length - len(names))
    return ', '.join(f'{key}[{i}]={n}' for i, n in enumerate(names))


def _traversals(ladder=True, grapple=True, window=True):
    flags = dict(Normal=True, ClimbOver=True, ClimbOnto=True, ClimbLadder=ladder, DropDown=True, Grapple=grapple,
                 Landing=True, BreakWindow=window, KickDoor=True, JumpUp=False, WallClimb=False, BreakWall=False)
    return ', '.join(f'bCanUse_eTraversal_{k}={v}' for k, v in flags.items())


CHARACTER_ROWS = [
    'Characters=( strName="", iType=eChar_Soldier, HP=6, Offense=65, Defense=0, Mobility=14, SightRadius=27, Will=30, '
    f'ShieldHP=0, CritHitChance=0, CritWoundChance=0, FlightFuel=0, Reaction=0, {_abilities("eAbility_TakeCover")}, '
    f'{_props("Properties", 6, "eCP_CanGainXP")}, {_traversals()}, kInventory=( iArmor=eItem_NONE, iPistol=eItem_NONE, '
    'iNumLargeItems=0 ), eClass=eSC_None, bHasPsiGift=False, fBioElectricParticleScale=1 )    ',
    'Characters=( strName="", iType=eChar_Tank, HP=12, Offense=55, Defense=0, Mobility=14, SightRadius=27, Will=0, '
    f'ShieldHP=0, CritHitChance=0, CritWoundChance=0, FlightFuel=0, Reaction=0, {_abilities()}, '
    f'{_props("Properties", 6, "eCP_Robotic", "eCP_Hardened")}, {_traversals(ladder=False, grapple=False, window=False)}, '
    'eClass=eSC_None, bHasPsiGift=False, fBioElectricParticleScale=1 )',
]


def armour(item, hp, defence, large, small, mobility=0, fuel=0, abilities=(), props=()):
    ab = list(abilities) + ['0'] * (4 - len(abilities))
    return (f'Armors=( {", ".join(f"ABILITIES[{i}]={a}" for i, a in enumerate(ab))}, {_props("Properties", 4, *props)}, '
            f'strName="", iType={item}, iHPBonus={hp}, iDefenseBonus={defence}, iFlightFuel={fuel}, iWillBonus=0, '
            f'iLargeItems={large}, iSmallItems={small}, iMobilityBonus={mobility} )  ;a comment, (with) "quotes"')


def weapon(item, size, *props):
    return (f'Weapons=( strName="", iType={item}, ABILITIES[0]=eAbility_ShotStandard, {_props("Properties", 6, *props)}, '
            f'iDamage=3, iEnvironmentDamage=15, iRange=30, iReactionRange=30, iReactionAngle=200, iRadius=0, '
            f'iCritical=10, iOffenseBonus=0, iSuppression=403, iSize={size}, iHPBonus=0, iWillBonus=0 ); a comment')


ARMOUR_ROWS = [
    armour(57, 3, 5, 1, 2, mobility=2),
    armour('eItem_ArmorKevlar', 5, 0, 1, 2),
    armour('eItem_ArmorCarapace', 7, 0, 1, 2, mobility=-1),
    armour('eItem_ArmorSkeleton', 9, 15, 1, 2, mobility=3, props=('eAP_Grapple',)),
    armour('eItem_ArmorArchangel', 19, 0, 1, 3, mobility=-1, fuel=12, abilities=('eAbility_Fly',),
           props=('eAP_FireImmunity', 'eAP_AirEvade')),
    armour('eItem_SHIVDeck_I', 8, 25, 0, 2, props=('eAP_Tank', 'eAP_FireImmunity')),
    armour('eItem_SHIVDeck_III', 20, 25, 0, 4, fuel=14, abilities=('eAbility_Fly',),
           props=('eAP_Tank', 'eAP_FireImmunity', 'eAP_AirEvade')),
    armour('eItem_MecArmor1', 15, 30, 1, 2, props=('eAP_MEC', 'eAP_PoisonImmunity', 'eAP_FireImmunity')),
]
WEAPON_ROWS = [
    weapon('eItem_AssaultRifle', 'eItemSize_Large', 'eWP_AnyClass'),
    weapon('eItem_Shotgun', 'eItemSize_Large', 'eWP_Assault', 'eWP_Rifle'),
    weapon('eItem_LMG', 'eItemSize_Large', 'eWP_Support'),
    weapon('eItem_SniperRifle', 'eItemSize_Large', 'eWP_Sniper', 'eWP_MoveLimited'),
    weapon('eItem_RocketLauncher', 'eItemSize_Large', 'eWP_Explosive', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Heavy'),
    weapon('eItem_Pistol', 'eItemSize_Small', 'eWP_Pistol'),
    weapon('eItem_Chaingun', 'eItemSize_Large', 'eWP_Mec'),
    weapon('eItem_ShivMinigun', 'eItemSize_Large', 'eWP_Integrated'),
    weapon('eItem_MecFlameThrower', 'eItemSize_Large', 'eWP_Mec', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Encumber'),
    weapon('eItem_MecKineticArm', 'eItemSize_Large', 'eWP_Mec', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Encumber'),
    weapon('eItem_FragGrenade', 'eItemSize_Small', 'eWP_AnyClass', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Explosive', 'eWP_Encumber'),
    weapon('eItem_NeedleGrenade', 'eItemSize_Small', 'eWP_AnyClass', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Explosive', 'eWP_Encumber'),
    weapon('eItem_SmokeGrenade', 'eItemSize_Small', 'eWP_AnyClass', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Encumber'),
    weapon('eItem_GasGrenade', 'eItemSize_Small', 'eWP_Anyclass', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Encumber'),
    weapon('eItem_BattleScanner', 'eItemSize_Small', 'eWP_Overheats', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Encumber'),
    weapon('eItem_Medikit', 'eItemSize_Small', 'eWP_AnyClass', 'eWP_Secondary', 'eWP_NoReload', 'eWP_Backpack', 'eWP_Encumber'),
    weapon('eItem_Grapple', 'eItemSize_Small', 'eWP_Integrated', 'eWP_Secondary', 'eWP_Encumber'),
    weapon('eItem_PsiAmp', 'eItemSize_Small', 'eWP_Integrated', 'eWP_Secondary', 'eWP_Encumber'),
    weapon('eItem_PlasmaLightRifle_Muton', 'eItemSize_Large', 'eWP_Rifle'),
]
COSTED = ['eItem_AssaultRifle', 'eItem_Shotgun', 'eItem_LMG', 'eItem_SniperRifle', 'eItem_RocketLauncher', 'eItem_Pistol',
          'eItem_Chaingun', 'eItem_ShivMinigun', 'eItem_MecFlameThrower', 'eItem_MecKineticArm', 'eItem_FragGrenade',
          'eItem_NeedleGrenade', 'eItem_SmokeGrenade', 'eItem_GasGrenade', 'eItem_BattleScanner', 'eItem_Medikit',
          '57', 'eItem_ArmorKevlar', 'eItem_ArmorCarapace', 'eItem_ArmorSkeleton', 'eItem_ArmorArchangel',
          'eItem_SHIVDeck_I', 'eItem_SHIVDeck_III', 'eItem_MecArmor1']


def core_ini():
    lines = ['[XComGame.XGTacticalGameCore]', '; the base characters'] + CHARACTER_ROWS + ARMOUR_ROWS
    lines += ['[XComGame.XComPerkManager]', 'Something=1', '[XComGame.XGTacticalGameCore]'] + WEAPON_ROWS
    lines += [f'ItemBalance_Normal=(eItem={item}, iCash=10, iElerium=0, iAlloys=0, iTime=-1, iEng=-1)' for item in COSTED]
    return '\r\n'.join(lines) + '\r\n'


ITEM_LABELS = {'eItem_Pistol': 'Pistol', 'eItem_AssaultRifle': 'Assault Rifle', 'eItem_Shotgun': 'Shotgun',
               'eItem_LMG': 'Light Machine Gun', 'eItem_SniperRifle': 'Sniper Rifle',
               'eItem_RocketLauncher': 'Rocket Launcher', '57': 'Tactical Vest', 'eItem_ArmorKevlar': 'Tactical Armor',
               'eItem_ArmorCarapace': 'Carapace Armor', 'eItem_ArmorSkeleton': 'Corsair Armor',
               'eItem_ArmorArchangel': 'Archangel Armor', 'eItem_SHIVDeck_I': 'SHIV Chassis',
               'eItem_SHIVDeck_III': 'Hover SHIV Chassis', 'eItem_MecArmor1': 'MEC1 \'Paladin\'',
               'eItem_Chaingun': 'Minigun', 'eItem_ShivMinigun': 'Autocannon', 'eItem_MecFlameThrower': 'Flamethrower',
               'eItem_MecKineticArm': 'Kinetic Strike Module', 'eItem_FragGrenade': 'HE Grenade',
               'eItem_NeedleGrenade': 'AP Grenade', 'eItem_SmokeGrenade': 'Smoke Grenade',
               'eItem_GasGrenade': 'Acid Grenade', 'eItem_BattleScanner': 'Battle Scanner', 'eItem_Medikit': 'Medikit',
               'eItem_PlasmaLightRifle_Muton': 'Muton Light Plasma Rifle'}


def game_int(language='INT'):
    lines = ['[XComPerkManager]', 'm_strPassiveTitle[ePerk_SquadSight]="Squadsight"',
             'm_strBonusTitle[ePerk_Sprinter]="Sprinter"', 'm_strPassiveTitle[ePerk_Poisoned]="Poisoned"',
             '[XGTacticalGameCoreNativeBase]'] + [f'm_aRankNames[{i}]="Rank {i}"' for i in range(8)]
    lines += ['[XGTacticalGameCore]', 'm_aSoldierClassNames[eSC_None]="Rookie"', 'm_aSoldierClassNames[eSC_Sniper]="Sniper"',
              'm_aSoldierClassNames[eSC_HeavyWeapons]="Heavy"', 'm_aSoldierClassNames[eSC_Support]="Support"',
              'm_aSoldierClassNames[eSC_Assault]="Assault"', 'm_aSoldierClassNames[eSC_Psi]="Psi"',
              'm_aSoldierClassNames[eSC_Mec]="MEC Trooper"',
              '[XLocalizedData]'] + [f'm_aItemNames[{k}]="{v}"' for k, v in ITEM_LABELS.items()]
    lines += ['m_aCharacterName[eChar_Soldier]="Soldier"', 'm_aCharacterName[eChar_Tank]="SHIV"']
    return '\n'.join(lines) + '\n'


def strategy_int():
    return ('[XGLocalizedData]\nCountryNames[eCountry_USA]="United States"\nCountryNames[eCountry_India]="India"\n'
            'CountryNames[eCountry_Italy]="Italy"\nCountryNames[eCountry_Canada]="Canada"\n'
            'CountryNames[eCountry_Mexico]="Mexico"\nCountryNames[eCountry_Belgium]="Belgium"\n')


def make_game(root, kind='lwr', utf16=True, markers=True):
    """A scratch game folder under `root` (kind: lwr, longwar or ew, by the config files settings.game_kind reads; with
    markers False those files are left as they are: the squad's files added to a play test's game folder)."""
    game = Path(root)
    xew = game / 'XEW' / 'XComGame'
    (xew / 'CookedPCConsole').mkdir(parents=True, exist_ok=True)
    (xew / 'CookedPCConsole' / 'XComGame.upk').write_bytes(b'stand-in for the script package')
    config = xew / 'Config'
    config.mkdir(parents=True, exist_ok=True)
    (config / 'DefaultGameCore.ini').write_text(core_ini(), encoding='cp1252', newline='')
    (config / 'DefaultEngine.ini').write_text('[Engine.Engine]\nLanguage=INT\n', encoding='ascii', newline='')
    if markers and kind == 'lwr': (config / 'DefaultLWRebalance.ini').write_text('[x]\n', encoding='ascii')
    if markers and kind in ('lwr', 'longwar'): (config / 'DefaultLZMutator.ini').write_text('[x]\n', encoding='ascii')
    loc = xew / 'Localization' / 'INT'
    loc.mkdir(parents=True, exist_ok=True)
    (loc / 'XComGame.int').write_text(game_int(), encoding='cp1252', newline='\n')
    (loc / 'XComStrategyGame.int').write_text(strategy_int(), encoding='utf-16' if utf16 else 'cp1252', newline='\n')
    (xew.parent / 'Binaries').mkdir(parents=True, exist_ok=True)
    return game


@contextmanager
def enums(records=None):
    """script_enums.cached gives the fixture's entries for any package while the context is open."""
    records = records or enum_records()
    with mock.patch.object(script_enums, 'cached', lambda path, folder: records):
        yield records
