"""The test squad as the game takes it: each family's loadout rules, the choices an install offers, the squad
resolved against them, and the m_aSoldiers text a play sets (private/plans/done/test-squad-plan.md, section 5.3).

A play writes the squad straight into XComOnlineProfileSettings.m_aSoldiers (gamelaunch.py, F-74): one
TTransferSoldier per unit, in the text form `getall` prints. Long War Rebalance's scripts were read for what this
path does with each field (research/test-squad-records.md says where); the rules below are what they showed:
- a unit's character is written whole: the base character the install's config row gives (XGTacticalGameCore.
  BuildCharacter: the stats at their ECharacterStat entries, each of the row's eight abilities and six properties
  counted into aAbilities and aProperties, zeros included, and its traversal flags), with the base stats set by hand
  over it. Armour, weapons and perks add theirs when the battle starts, so nothing of them is added here;
- soldiers and MEC troopers are the soldier character (eChar_Soldier), a SHIV the tank's (eChar_Tank), named in
  kChar.strName; a MEC is the MEC class (eSC_Mec) in a MEC suit, a SHIV no class in a SHIV chassis;
- the inventory is written as it is listed: the armour (or suit, or chassis), the item in the pistol's place, the
  large items in order (a soldier's weapon; a heavy's rocket launcher with the machine gun in the pistol's place, as
  the game's own developer squad has it; a MEC's gun, then its modules; a SHIV's gun), the small items in order, and
  the psi amp every soldier of the game's own squads carries as its one custom item;
- perks are the character's aUpgrades: each chosen one written as 1.

Each family (settings.game_kind) has an Adapter: the kinds of unit it writes and the most units its landing takes.
LWR's is the one the scripts were read for; Long War without Rebalance and plain Enemy Within write soldiers only
(their scripts were not read: MECs and SHIVs on them are reported as not written, never guessed at).

`choices(catalogue)` is what the setup panel offers; `resolve(document, catalogue)` checks a squad against an install
(errors stop a play, warnings don't) and gives the records; `squad_text(records)` the value of the `set` command.
"""
from collections import Counter
import re

from gamedata import ROW_STATS, TRAVERSALS, array

KIND_LABELS = dict(soldier='Soldier', mec='MEC trooper', shiv='SHIV')
STAT_KEYS = dict(hp='eStat_HP', aim='eStat_Offense', defence='eStat_Defense', mobility='eStat_Mobility',
                 will='eStat_Will', sight='eStat_SightRadius')
STAT_LABELS = dict(hp='HP', aim='Aim', defence='Defence', mobility='Mobility', will='Will', sight='Sight')
# The looks of the game's own developer squad (XComOnlineProfileSettings.ExtendedLaunch_BuildSoldiersFromParts), so
# their heads, hair and voices are ones the game has. A SHIV has none.
LOOKS = {
    'man-a': ('Man A', 'iHead=31,iGender=1,iRace=2,iHaircut=20,iHairColor=2,iFacialHair=7,iVoice=1'),
    'man-b': ('Man B', 'iHead=36,iGender=1,iRace=3,iHaircut=19,iHairColor=10,iFacialHair=-1,iSkinColor=4,iVoice=1'),
    'man-c': ('Man C', 'iHead=16,iGender=1,iHaircut=22,iHairColor=9,iFacialHair=4,iSkinColor=3,iVoice=1'),
    'man-d': ('Man D', 'iHead=31,iGender=1,iRace=2,iHaircut=20,iHairColor=8,iFacialHair=-1,iVoice=1'),
    'woman-a': ('Woman A', 'iHead=43,iGender=2,iHaircut=10,iHairColor=1,iFacialHair=-1,iSkinColor=1,iVoice=12'),
    'woman-b': ('Woman B', 'iHead=43,iGender=2,iHaircut=10,iHairColor=6,iFacialHair=-1,iSkinColor=2,iVoice=12'),
}
SOLDIER_CLASSES = ('eSC_None', 'eSC_Assault', 'eSC_HeavyWeapons', 'eSC_Sniper', 'eSC_Support')
PSI_AMP = 'eItem_PsiAmp'
# Names the game can take in its `set` command: the play file is ASCII, and a name sits in quotes inside a bracketed
# record, so quotes, backslashes, brackets, commas, equals signs and | (which ends a console command) are left out.
NAME_OK = re.compile(r"[A-Za-z0-9 .'-]*")
MAX_LINE = 16000        # the longest m_aSoldiers text a play writes (eight full units come to about 9,000)


class Adapter:
    """A family's rules. kinds: the kinds of unit written; max_units: the most units the landing takes."""
    def __init__(self, family, label, kinds, max_units, note=None):
        self.family, self.label, self.kinds, self.max_units, self.note = family, label, kinds, max_units, note


ADAPTERS = {
    'lwr': Adapter('lwr', 'Long War Rebalance', ('soldier', 'mec', 'shiv'), 8),
    'longwar': Adapter('longwar', 'Long War, not LWR', ('soldier',), 6,
                       'On Long War without Rebalance the editor writes soldiers only.'),
    'ew': Adapter('ew', 'Enemy Within', ('soldier',), 6, 'On plain Enemy Within the editor writes soldiers only.'),
}


def adapter(family):
    return ADAPTERS.get(family) or Adapter(family, family, ('soldier',), 6, 'The editor writes soldiers only on this install.')


# ---- items: their roles, from the install's own tables ----

def _props(catalogue, row, key, enum, length):
    return {p.lower() for p in catalogue.flags(row, key, enum, length)}


def item_info(catalogue, index):
    """What the panel shows and the rules read of one item: its label, size, properties, roles and bonuses."""
    enum = catalogue.enums['EItemType']
    out = dict(id=enum.name(index), index=index, label=catalogue.item_label(index), costed=index in catalogue.costed,
               roles=[])
    if index in catalogue.armours:
        row = catalogue.armours[index]
        props = _props(catalogue, row, 'Properties', 'EArmorProperty', 4)
        out['armour'] = dict(hp=_int(row.get('iHPBonus')), defence=_int(row.get('iDefenseBonus')),
                             mobility=_int(row.get('iMobilityBonus')), will=_int(row.get('iWillBonus')),
                             fuel=_int(row.get('iFlightFuel')), large=_int(row.get('iLargeItems')),
                             small=_int(row.get('iSmallItems')),
                             abilities=catalogue.flags(row, 'ABILITIES', 'EAbility', 4),
                             properties=sorted(catalogue.flags(row, 'Properties', 'EArmorProperty', 4)))
        out['roles'].append('shiv-deck' if 'eap_tank' in props else 'mec-suit' if 'eap_mec' in props else 'armour')
    if index in catalogue.weapons:
        row = catalogue.weapons[index]
        props = _props(catalogue, row, 'Properties', 'EWeaponProperty', 6)
        size = catalogue.resolve('EItemSize', row.get('iSize'))
        large = size == 1
        out['weapon'] = dict(size='large' if large else 'small' if size == 0 else 'other',
                             properties=sorted(catalogue.flags(row, 'Properties', 'EWeaponProperty', 6)),
                             abilities=catalogue.flags(row, 'ABILITIES', 'EAbility', 6),
                             damage=_int(row.get('iDamage')), aim=_int(row.get('iOffenseBonus')),
                             hp=_int(row.get('iHPBonus')), will=_int(row.get('iWillBonus')))
        mec, integrated, secondary = 'ewp_mec' in props, 'ewp_integrated' in props, 'ewp_secondary' in props
        if large:
            if mec: out['roles'].append('mec-module' if secondary else 'mec-gun')
            if integrated and not mec: out['roles'].append('shiv-gun')
            if not mec and not integrated:
                out['roles'].append('heavy-weapon' if secondary and 'ewp_heavy' in props else 'primary')
        elif size == 0:
            if 'ewp_pistol' in props: out['roles'].append('pistol')
            elif secondary or 'ewp_backpack' in props:
                users = [k for k, flag in (('soldier', not (props <= {'ewp_mec', 'ewp_integrated', 'ewp_secondary',
                                                                        'ewp_backpack', 'ewp_encumber', 'ewp_noreload',
                                                                        'ewp_explosive'})),
                                           ('mec', mec), ('shiv', integrated)) if flag]
                out['roles'] += [f'small-{k}' for k in users]
    return out


def _int(text):
    try: return int(str(text).strip())
    except (TypeError, ValueError): return 0


# the slots of each kind: (slot, the roles its normal list offers)
SLOTS = {
    'soldier': dict(armour=('armour',), sidearm=('pistol',), weapons=('primary', 'heavy-weapon'), items=('small-soldier',)),
    'mec': dict(armour=('mec-suit',), weapons=('mec-gun', 'mec-module'), items=('small-mec',)),
    'shiv': dict(armour=('shiv-deck',), weapons=('shiv-gun',), items=('small-shiv',)),
}
# Show every item: any item of the slot's size (armours of the unit's kind only: the body comes from it)
WIDE = dict(sidearm='small', weapons='large', items='small')


def item_table(catalogue):
    enum = catalogue.enums['EItemType']
    out = {}
    for index in sorted(set(catalogue.armours) | set(catalogue.weapons)):
        name = enum.unique(index)
        if not name or index == 0 or name.endswith('_MAX'): continue
        out[name] = item_info(catalogue, index)
    return out


def slot_lists(items, wide=False):
    """{kind: {slot: [item ids]}}: the normal lists (roles, and a cost row: equipment XCOM makes), or with wide every
    item of the slot's size."""
    out = {}
    for kind, slots in SLOTS.items():
        out[kind] = {}
        for slot, roles in slots.items():
            if wide and slot in WIDE:
                ids = [i for i, info in items.items() if info.get('weapon', {}).get('size') == WIDE[slot]]
            else:
                ids = [i for i, info in items.items() if set(info['roles']) & set(roles) and (wide or info['costed'])]
            out[kind][slot] = sorted(ids, key=lambda i: (items[i]['label'] or i).lower())
    return out


# ---- perks ----

# Entries of EPerkType that are states or markers the game sets during a battle, not perks a unit has (LWR's
# localisation names them as statuses), by their full names: they are left out of the normal list.
STATUS_PERKS = {
    'ePerk_None', 'ePerk_MAX', 'ePerk_SuppressedActive', 'ePerk_CriticallyWounded', 'ePerk_Flying', 'ePerk_Panicked',
    'ePerk_CombatStimActive', 'ePerk_Disoriented', 'ePerk_Electropulse', 'ePerk_BattleFatigue', 'ePerk_FallenComrades',
    'ePerk_MindMerger', 'ePerk_GreaterMindMerger', 'ePerk_StealthGrenade', 'ePerk_OTS_Leader_Bonus',
    'ePerk_OnlyForGermanModeStrings_ItemRangeBonus', 'ePerk_OnlyForGermanModeStrings_ItemRangePenalty',
    'ePerk_OnlyForGermanModeStrings_AimingAnglesBonus', 'ePerk_AutopsyRequired', 'ePerk_Implanted', 'ePerk_Poisoned',
    'ePerk_ChryssalidSpawn', 'ePerk_Plague', 'ePerk_Poison', 'ePerk_BloodCall', 'ePerk_Overload', 'ePerk_DeathBlossom',
    'ePerk_Implant', 'ePerk_PsiDrain', 'ePerk_CannonFire', 'ePerk_SeekerStealth', 'ePerk_SeekerStrangle',
    'ePerk_MindMerge_Mechtoid', 'ePerk_PlasmaBarrage', 'ePerk_ClusterBomb',
}


def perk_table(catalogue):
    """[{id, label, normal}] of the install's perks: normal ones have a title and are no state the battle sets (gene
    mods, psionics and Foundry projects are their own systems, kept to Show every perk). Ordered by label."""
    enum = catalogue.enums['EPerkType']
    out = []
    for index, name in enumerate(enum.entries):
        if name in enum.ambiguous or name in ('ePerk_None', 'ePerk_MAX') or name.startswith('ePerk_MAX_'): continue
        label = catalogue.label('perk', index)
        own_system = re.match(r'ePerk_(GeneMod_|Foundry_|Psi|Mind|TelekineticField|Rift)', name) is not None
        normal = bool(label) and name not in STATUS_PERKS and not own_system and 'DEPRECATED' not in name
        out.append(dict(id=name, index=index, label=label or name, normal=normal))
    return sorted(out, key=lambda p: (p['label'].lower(), p['index']))


# ---- base characters ----

def base_character(catalogue, kind):
    """The base character a kind of unit is written over, as XGTacticalGameCore.BuildCharacter makes it from the
    install's config row: {'type': index, 'stats': {entry: value}, 'abilities': Counter, 'properties': Counter,
    'traversals': [indices], 'bio': float}, or None when the install has no row for it."""
    key = 'eChar_Tank' if kind == 'shiv' else 'eChar_Soldier'
    row = catalogue.characters.get(key)
    if row is None: return None
    stat = catalogue.enums['ECharacterStat']
    stats = {}
    for field, entry in ROW_STATS.items():
        if entry in stat: stats[stat.index(entry)] = _int(row.get(field))
    abilities = Counter(catalogue.resolve('EAbility', t) for t in array(row, 'ABILITIES', 8))
    properties = Counter(catalogue.resolve('ECharacterProperty', t) for t in array(row, 'Properties', 6))
    trav = catalogue.enums['ETraversalType']
    traversals = sorted(trav.index(f'eTraversal_{name}') for name in TRAVERSALS
                        if str(row.get(f'bCanUse_eTraversal_{name}', 'False')).lower() == 'true'
                        and f'eTraversal_{name}' in trav)
    try: bio = float(row.get('fBioElectricParticleScale', '1'))
    except ValueError: bio = 1.0
    return dict(type=row['index'], stats=stats, abilities=abilities, properties=properties, traversals=traversals,
                bio=bio)


def base_stats(catalogue, kind):
    base = base_character(catalogue, kind)
    if base is None: return None
    stat = catalogue.enums['ECharacterStat']
    return {key: base['stats'].get(stat.index(entry), 0) for key, entry in STAT_KEYS.items() if entry in stat}


# ---- what the panel offers ----

def countries(catalogue):
    enum = catalogue.enums['ECountry']
    out = []
    for index, name in enumerate(enum.entries):
        label = catalogue.label('country', index)
        if label and name in enum and not name.endswith('_MAX'): out.append(dict(id=name, index=index, label=label))
    return sorted(out, key=lambda c: c['label'].lower())


def choices(catalogue):
    """Everything the setup panel offers for an install, as JSON."""
    rules = adapter(catalogue.family)
    classes = catalogue.enums['ESoldierClass']
    items = item_table(catalogue)
    return dict(
        family=catalogue.family, familyLabel=rules.label, maxUnits=rules.max_units, note=rules.note,
        kinds=[dict(id=k, label=KIND_LABELS[k], available=k in rules.kinds,
                    why=None if k in rules.kinds else rules.note) for k in ('soldier', 'mec', 'shiv')],
        classes=[dict(id=c, label=catalogue.label('class', classes.index(c)) or c) for c in SOLDIER_CLASSES if c in classes],
        ranks=[dict(value=r, label=label) for r, label in catalogue.ranks()],
        looks=[dict(id=k, label=v[0]) for k, v in LOOKS.items()],
        countries=countries(catalogue),
        items=items, slots=slot_lists(items), slotsAll=slot_lists(items, wide=True),
        perks=perk_table(catalogue),
        base={kind: base_stats(catalogue, kind) for kind in ('soldier', 'mec', 'shiv')},
        stats=[dict(id=k, label=STAT_LABELS[k]) for k in STAT_KEYS],
        templates=templates(catalogue), diagnostics=list(catalogue.diagnostics))


# ---- LWR's own rules the tables don't say (research/test-squad-records.md) ----

# XGBattleDesc.MapSoldierToPawn: the armours that have a body. Any other armour gives no pawn, and the unit is left out
# of the battle without a word.
LWR_PAWN_ARMOURS = {57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 159, 160, 182,      # soldiers' armours
                    113, 114, 115,                                                    # SHIV chassis
                    145, 148, 191, 192, 193, 194, 195, 210}                           # MEC suits, base augments
# plain Enemy Within and Long War: the base game's own armours, by name (their scripts were not read; LWR's
# MapSoldierToPawn keeps a case for each of these beside its own)
BASE_ARMOURS = {'eItem_ArmorKevlar', 'eItem_ArmorCarapace', 'eItem_ArmorSkeleton', 'eItem_ArmorTitan',
                'eItem_ArmorArchangel', 'eItem_ArmorGhost', 'eItem_ArmorPsi'}
# LWR's tactical mutator (LWRItemCharges) gives a battle scanner and a smoke grenade their charges from perk entries,
# not from the item: scanners from aUpgrades[ePerk_BattleScanner] >> 1, a smoke grenade's one from
# aUpgrades[ePerk_SmokeBomb] >> 1; bit 1 of each is the perk itself
CHARGE_PERKS = {'eItem_BattleScanner': ('ePerk_BattleScanner', 'count'), 'eItem_SmokeGrenade': ('ePerk_SmokeBomb', 'one')}
MEC_TAKEN = ('eItem_FragGrenade', 'eItem_AlienGrenade', 'eItem_Medikit')    # LWR sets their charges to 0 on a MEC


class UnitResult:
    def __init__(self, unit):
        self.id, self.unit = unit['id'], unit
        self.errors, self.warnings, self.notes = [], [], []
        self.record = None
        self.summary = ''


class Resolved:
    """A squad checked against an install: units (UnitResult), squad-wide errors, warnings and notes, and, when it can
    be played, the m_aSoldiers text."""
    def __init__(self):
        self.units, self.errors, self.warnings, self.notes = [], [], [], []
        self.text = None
        self.max_units = None

    @property
    def playable(self):
        return not self.errors and all(not u.errors for u in self.units) and self.text is not None

    def all_errors(self):
        """The squad's errors and each unit's, named."""
        return self.errors + [f'{unit_name(u.unit)}: {e}' for u in self.units for e in u.errors]

    def public(self):
        return dict(playable=self.playable, count=len(self.units), maxUnits=self.max_units, errors=self.errors,
                    warnings=self.warnings, notes=self.notes,
                    units=[dict(id=u.id, label=unit_name(u.unit), summary=u.summary, errors=u.errors,
                                warnings=u.warnings, notes=u.notes) for u in self.units])

    def receipt(self):
        """What a play's ledger and message keep of the squad: its units in a few words, its warnings and notes."""
        return dict(units=[f'{unit_name(u.unit)}: {u.summary}' for u in self.units],
                    warnings=self.warnings + [f'{unit_name(u.unit)}: {w}' for u in self.units for w in u.warnings],
                    notes=self.notes + [f'{unit_name(u.unit)}: {n}' for u in self.units for n in u.notes])


def unit_name(unit):
    return (unit['first'] if unit['kind'] == 'shiv' else f"{unit['first']} {unit['last']}").strip() or '(no name)'


def game_name(text):
    """A name as the record takes it, or a ValueError saying why the game can't take it."""
    if not NAME_OK.fullmatch(text):
        bad = sorted({ch for ch in text if not NAME_OK.fullmatch(ch)})
        shown = ' '.join('a new line' if ch == '\n' else repr(ch) if not ch.isprintable() else ch for ch in bad)
        raise ValueError(f'The game takes names of letters, digits, spaces and . \' - only, and "{text}" has {shown}')
    return text


def _item(catalogue, name):
    """The item index of an enum name on this install, or None."""
    enum = catalogue.enums['EItemType']
    return enum.index(name) if name and name in enum else None


def resolve(document, catalogue):
    """The squad document checked against an install's catalogue (None: no install to check it against)."""
    out = Resolved()
    if catalogue is None:
        out.errors.append('There is no install to check the squad against')
        out.units = [UnitResult(u) for u in document['units']]
        return out
    rules = adapter(catalogue.family)
    out.max_units = rules.max_units
    items, perks = item_table(catalogue), {p['id']: p for p in perk_table(catalogue)}
    for unit in document['units']: out.units.append(_resolve_unit(unit, catalogue, rules, items, perks))
    count = len(document['units'])
    if count > rules.max_units:
        out.errors.append(f'{rules.label}\'s landing takes at most {rules.max_units} units here, and the squad has {count}')
    elif count > 6:
        out.notes.append(f'Unit{"s 7 and 8 land" if count == 8 else " 7 lands"} one tile behind the landing points, '
                         'where the game finds room: its own rule for a squad of more than six')
    if sum(1 for u in document['units'] if u['kind'] == 'shiv') > 1 and catalogue.family == 'lwr':
        out.warnings.append('Long War lets one SHIV act each turn: once one has moved or fired, the others wait for the '
                            'next turn. The game\'s Robot Overlords option lifts this; the editor leaves the game\'s '
                            'options as they are')
    records = [u.record for u in out.units]
    if all(r is not None for r in records) and not out.errors:
        text = squad_text(records)
        if len(text) > MAX_LINE:
            out.errors.append(f'The squad is too long for the game\'s command ({len(text)} characters, at most {MAX_LINE})')
        else: out.text = text
    return out


def _props_of(items, name):
    return {p.lower() for p in items.get(name, {}).get('weapon', {}).get('properties', [])}


def _resolve_unit(unit, catalogue, rules, items, perk_info):
    r = UnitResult(unit)
    kind, enum = unit['kind'], catalogue.enums
    words = []
    if kind not in rules.kinds:
        r.errors.append(f'The editor writes no {KIND_LABELS[kind]} on {rules.label}' + (f': {rules.note}' if rules.note else ''))
    # names
    for text in ([unit['first']] if kind == 'shiv' else [unit['first'], unit['last']]):
        try: game_name(text)
        except ValueError as error: r.errors.append(str(error))
    if not (unit['first'].strip() or (kind != 'shiv' and unit['last'].strip())): r.warnings.append('It has no name: the game shows none')
    # class and rank
    classes = enum['ESoldierClass']
    if kind == 'soldier':
        cls = unit['class'] or 'eSC_None'
        if cls in classes.ambiguous: r.errors.append(f'Its class {cls} names more than one entry of this install\'s classes'); cls = None
        elif cls not in classes: r.errors.append(f'Its class {cls} is not one of this install\'s'); cls = None
        elif cls not in SOLDIER_CLASSES:
            r.errors.append(f'Its class ({catalogue.label("class", classes.index(cls)) or cls}) is not one the editor writes: '
                            'rookie or one of the four base classes'); cls = None
    else:
        cls = 'eSC_Mec' if kind == 'mec' else 'eSC_None'
        if cls not in classes: r.errors.append(f'This install has no {cls}'); cls = None
    ranks = catalogue.ranks()
    if ranks and unit['rank'] >= len(ranks):
        r.warnings.append(f'Rank {unit["rank"]} has no name on this install (the highest is {len(ranks) - 1})')
    # look and country
    country = 0
    if kind != 'shiv':
        if unit['look'] not in LOOKS: r.errors.append('Choose a look' if unit['look'] is None else f'{unit["look"]} is not one of the looks')
        countries = enum['ECountry']
        if unit['country'] in countries and catalogue.label('country', countries.index(unit['country'])):
            country = countries.index(unit['country'])
        elif unit['country']:
            r.notes.append(f'Its country {unit["country"]} is not on this install: it is {catalogue.label("country", 0) or "the first country"} in the game')
    # armour: the body comes from it
    armour, want = None, dict(soldier='armour', mec='mec-suit', shiv='shiv-deck')[kind]
    what = dict(soldier='armour', mec='MEC suit', shiv='chassis')[kind]
    info = items.get(unit['armour'] or '')
    if not unit['armour']: r.errors.append(f'Choose its {what}')
    elif _item(catalogue, unit['armour']) is None: r.errors.append(f'Its {what} {unit["armour"]} is not on this install')
    elif info is None or 'armour' not in info: r.errors.append(f'{info["label"] if info else unit["armour"]} is not an armour on this install')
    elif want not in info['roles']: r.errors.append(f'{info["label"]} is not a {KIND_LABELS[kind]}\'s {what}: the body comes from it')
    elif (catalogue.family == 'lwr' and info['index'] not in LWR_PAWN_ARMOURS) or (catalogue.family != 'lwr' and unit['armour'] not in BASE_ARMOURS):
        r.errors.append(f'{info["label"]} has no body when the game loads a squad this way: the unit would be left out of the battle')
    else:
        armour = info['index']
        words.append(info['label'])
    # the pistol's place
    pistol = 0
    if kind == 'soldier' and unit['sidearm']:
        pistol = _item(catalogue, unit['sidearm']) or 0
        if not pistol: r.notes.append(f'Its sidearm {unit["sidearm"]} is not on this install: it goes without one')
        else:
            sinfo = items.get(unit['sidearm'], {})
            words.append(sinfo.get('label') or unit['sidearm'])
            if 'pistol' not in sinfo.get('roles', ()) and not (cls == 'eSC_HeavyWeapons' and 'primary' in sinfo.get('roles', ())):
                r.warnings.append(f'{sinfo.get("label") or unit["sidearm"]} is not a pistol: it is carried on the thigh, where the pistol goes')
    elif kind != 'soldier' and unit['sidearm']: r.notes.append('A sidearm is a soldier\'s: it is left out')
    # large items, in order
    large = []
    for name in unit['weapons']:
        index = _item(catalogue, name)
        if not index: r.notes.append(f'{name} is not on this install: it is left out'); continue
        large.append(name)
    roles = [set(items.get(n, {}).get('roles', ())) for n in large]
    labels = [items.get(n, {}).get('label') or n for n in large]
    if kind == 'soldier':
        if not large: r.warnings.append('It has no weapon')
        if len(large) > 2:
            r.warnings.append(f'The game equips a soldier\'s first two large items: {", ".join(labels[2:])} '
                              f'{"is" if len(labels) == 3 else "are"} carried but not equipped')
        for label, role in zip(labels, roles):
            if not role & {'primary', 'heavy-weapon'}: r.warnings.append(f'{label} is not a soldier\'s weapon in this install\'s tables')
    elif kind == 'mec':
        if not large or 'mec-gun' not in roles[0]: r.errors.append('A MEC trooper needs its gun first among its large items')
        if sum(1 for role in roles if 'mec-gun' in role) > 1:
            r.warnings.append('Its guns all go in its right arm: only the last one listed is carried')
        seen = set()
        for name, label, role in zip(large, labels, roles):
            if name in seen and 'mec-module' in role: r.warnings.append(f'{label} is listed twice: a MEC has one place for it')
            seen.add(name)
            if not role & {'mec-gun', 'mec-module'}: r.warnings.append(f'{label} is not a MEC\'s gun or module in this install\'s tables')
    else:
        if not large: r.errors.append('A SHIV needs a gun')
        elif 'shiv-gun' not in roles[0]: r.warnings.append(f'{labels[0]} is not a SHIV\'s gun in this install\'s tables')
        if len(large) > 1:
            r.warnings.append(f'A SHIV carries only its first gun: {", ".join(labels[1:])} '
                              f'{"is" if len(labels) == 2 else "are"} left behind')
    words += labels if kind == 'mec' else labels[:2]
    # small items, in order
    small = []
    for name in unit['items']:
        if not _item(catalogue, name): r.notes.append(f'{name} is not on this install: it is left out'); continue
        small.append(name)
    slabels = [items.get(n, {}).get('label') or n for n in small]
    words += slabels
    if small and kind == 'shiv':
        r.warnings.append('A SHIV carries no items in battle: their stat bonuses count, and there is nothing to use')
    elif small:
        capacity = (info or {}).get('armour', {}).get('small')
        backpack = sum(1 for n in small if 'ewp_backpack' in _props_of(items, n))
        if capacity is not None and len(small) > capacity:
            r.warnings.append(f'{len(small)} items, and the {what} has {capacity} small slots: the game puts items past '
                              'the third into the backpack, which holds five')
        if max(len(small) - backpack - 3, 0) + backpack > 5: r.warnings.append('More than five items for the backpack: the game carries five')
        role = f'small-{kind}'
        for name, label in zip(small, slabels):
            if role not in items.get(name, {}).get('roles', ()): r.warnings.append(f'{label} is not a {KIND_LABELS[kind]}\'s item in this install\'s tables')
        if kind == 'mec' and catalogue.family == 'lwr':
            taken = sorted({label for name, label in zip(small, slabels) if name in MEC_TAKEN})
            if taken: r.warnings.append(f'Long War gives a MEC no {", ".join(taken)}: carried, with no charges')
    # perks, then the charges LWR keeps in perk entries
    upgrades = {}
    for name in unit['perks']:
        if name not in enum['EPerkType']: r.notes.append(f'The perk {name} is not on this install: it is left out'); continue
        upgrades[enum['EPerkType'].index(name)] = 1
        p = perk_info.get(name)
        words.append(p['label'] if p else name)
        if p and not p['normal']:
            r.warnings.append(f'{p["label"]} is not one of the usual perks: the game reads it as it reads the others, '
                              'which may give no ability')
    if catalogue.family == 'lwr' and kind != 'shiv':
        for item_name, (perk_name, how) in CHARGE_PERKS.items():
            carried = small.count(item_name)
            if not carried or perk_name not in enum['EPerkType']: continue
            index = enum['EPerkType'].index(perk_name)
            upgrades[index] = upgrades.get(index, 0) + 2 * (carried if how == 'count' else 1)
        if small.count('eItem_SmokeGrenade') > 1: r.notes.append('Long War gives smoke grenades one charge however many are carried')
    head = KIND_LABELS[kind] if kind != 'soldier' or not cls else (catalogue.label('class', classes.index(cls)) or 'Soldier')
    r.summary = ' · '.join([head] + [w for w in words if w])
    base = base_character(catalogue, kind)
    if base is None: r.errors.append(f'The install has no base character for a {KIND_LABELS[kind]}')
    if r.errors: return r
    stat_enum = enum['ECharacterStat']
    stats = dict(base['stats'])
    for key, value in unit['stats'].items():
        if STAT_KEYS[key] in stat_enum: stats[stat_enum.index(STAT_KEYS[key])] = value
    amp = _item(catalogue, PSI_AMP)
    r.record = dict(kind=kind, first=unit['first'], last=unit['last'], type=base['type'], armour=armour,
                    pistol=pistol if kind == 'soldier' else 0, large=[_item(catalogue, n) for n in large],
                    small=[_item(catalogue, n) for n in small], custom=[amp] if kind == 'soldier' and amp else [],
                    upgrades=upgrades, abilities=base['abilities'], properties=base['properties'], stats=stats,
                    traversals=base['traversals'], bio=base['bio'], eclass=cls,
                    class_index=classes.index(cls) if cls else 0, rank=unit['rank'], country=country,
                    look=LOOKS[unit['look']][1] if kind != 'shiv' else None)
    return r


# ---- the text ----

def unit_text(rec):
    """One TTransferSoldier as `set` takes it (names checked by game_name)."""
    inventory = [f'iArmor={rec["armour"]}', f'iPistol={rec["pistol"]}']
    for key, values in (('LargeItems', rec['large']), ('SmallItems', rec['small']), ('CustomItems', rec['custom'])):
        if values: inventory += [f'arr{key}[{i}]={v}' for i, v in enumerate(values)] + [f'iNum{key}={len(values)}']
    char = [f'strName="{game_name(rec["first"]) if rec["kind"] == "shiv" else "Soldier"}"', f'iType={rec["type"]}',
            f'kInventory=({",".join(inventory)})']
    char += [f'aUpgrades[{i}]={v}' for i, v in sorted(rec['upgrades'].items()) if v]
    char += [f'aAbilities[{i}]={n}' for i, n in sorted((i, n) for i, n in rec['abilities'].items() if i is not None and n)]
    char += [f'aProperties[{i}]={n}' for i, n in sorted((i, n) for i, n in rec['properties'].items() if i is not None and n)]
    char += [f'aStats[{i}]={v}' for i, v in sorted(rec['stats'].items()) if v]
    char += [f'aTraversals[{i}]=1' for i in rec['traversals']]
    char += [f'eClass={rec["eclass"]}', f'fBioElectricParticleScale={rec["bio"]:.6f}']
    out = f'(kChar=({",".join(char)})'
    if rec['kind'] != 'shiv':
        soldier = [f'strFirstName="{game_name(rec["first"])}"', f'strLastName="{game_name(rec["last"])}"',
                   f'iRank={rec["rank"]}', f'iCountry={rec["country"]}',
                   f'kAppearance=({rec["look"]},iBody=-1,iBodyMaterial=-1,iEyeColor=-1,iFlag={rec["country"]},'
                   'iArmorSkin=-1,iArmorDeco=-1,iArmorTint=7)']
        if rec['class_index']: soldier.append(f'kClass=(eType={rec["class_index"]})')
        out += f',kSoldier=({",".join(soldier)})'
    return out + ',iUnitLoadoutID=-1)'


def squad_text(records):
    """The value of `set XComOnlineProfileSettings m_aSoldiers` for the records, in landing order."""
    return '(' + ','.join(unit_text(rec) for rec in records) + ')'


def soldier_first(resolved):
    """A playable squad with its first soldier or MEC trooper moved to the front, for a battle whose covert operative
    takes the first unit's looks (a SHIV has none: missions.LEAD_NOTE). Returns (text, the name of the unit moved, or
    None when one already led), or (None, None) when the squad has only SHIVs."""
    records = [u.record for u in resolved.units]
    lead = next((i for i, r in enumerate(records) if r['kind'] != 'shiv'), None)
    if lead is None: return None, None
    if lead == 0: return resolved.text, None
    order = [records[lead]] + records[:lead] + records[lead + 1:]
    return squad_text(order), unit_name(resolved.units[lead].unit)


# ---- the default squad, and a new unit of each kind ----

DEFAULT_NAME = 'Test squad'
# The six squaddies plays had before the panel (EXP-29 run 6), each a unit's fields (_unit): first and last name, class,
# armour, sidearm, weapon, small item, look, country. The heavy's pair is the game's own: the machine gun in the pistol's place, the rocket launcher as the
# weapon.
DEFAULT_UNITS = (
    dict(first='Tom', last='Alpha', cls='eSC_Assault', armour='eItem_ArmorKevlar', sidearm='eItem_Pistol',
         weapons='eItem_Shotgun', items='eItem_FragGrenade', look='man-a', country='eCountry_Canada'),
    dict(first='Raj', last='Bravo', cls='eSC_Support', armour='eItem_ArmorKevlar', sidearm='eItem_Pistol',
         weapons='eItem_AssaultRifle', items='eItem_FragGrenade', look='man-b', country='eCountry_India'),
    dict(first='Mia', last='Charlie', cls='eSC_HeavyWeapons', armour='eItem_ArmorCarapace', sidearm='eItem_LMG',
         weapons='eItem_RocketLauncher', items='eItem_FragGrenade', look='woman-a', country='eCountry_Mexico'),
    dict(first='Leo', last='Delta', cls='eSC_Sniper', armour='eItem_ArmorKevlar', sidearm='eItem_Pistol',
         weapons='eItem_SniperRifle', items='eItem_FragGrenade', look='man-c', country='eCountry_Italy'),
    dict(first='Eva', last='Echo', cls='eSC_Support', armour='eItem_ArmorCarapace', sidearm='eItem_Pistol',
         weapons='eItem_AssaultRifle', items='eItem_Medikit', look='woman-b', country='eCountry_Mexico'),
    dict(first='Sam', last='Foxtrot', cls='eSC_Assault', armour='eItem_ArmorKevlar', sidearm='eItem_Pistol',
         weapons='eItem_AssaultRifle', items='eItem_NeedleGrenade', look='man-d', country='eCountry_Canada'),
)


def _unit(i, *, first, last, cls, armour, sidearm, weapons, items, look, country, kind='soldier'):
    return dict(id=f'unit-{i}', kind=kind, first=first, last=last, **{'class': cls}, rank=1, look=look, country=country,
                armour=armour, sidearm=sidearm, weapons=[weapons] if isinstance(weapons, str) else list(weapons),
                items=[items] if isinstance(items, str) else list(items), perks=[], stats={})


def default_document(catalogue=None):
    """The default squad: the six squaddies, by the game's names. It is the same document for every install; each
    resolves it with its own tables."""
    from squads import SCHEMA, SCHEMA_VERSION
    return dict(schema=SCHEMA, version=SCHEMA_VERSION, name=DEFAULT_NAME,
                units=[_unit(i, **row) for i, row in enumerate(DEFAULT_UNITS, 1)])


def templates(catalogue):
    """A new unit of each kind for the panel's Add and kind changes: the default soldier's gear, a MEC with the
    minigun, kinetic strike and flamethrower, a SHIV with its autocannon (each where the install has them)."""
    items = item_table(catalogue)
    lists = slot_lists(items)

    def pick(kind, slot, *wanted):
        for name in wanted:
            if name in lists[kind][slot]: return name
        return lists[kind][slot][0] if lists[kind][slot] else None
    soldier = _unit(0, first='New', last='Soldier', cls='eSC_Assault', armour=pick('soldier', 'armour', 'eItem_ArmorKevlar'),
                    sidearm=pick('soldier', 'sidearm', 'eItem_Pistol'),
                    weapons=[pick('soldier', 'weapons', 'eItem_AssaultRifle')],
                    items=[pick('soldier', 'items', 'eItem_FragGrenade')], look='man-a', country='eCountry_Canada')
    mec = _unit(0, first='New', last='MEC', cls='eSC_Mec', armour=pick('mec', 'armour', 'eItem_MecArmor1'), sidearm=None,
                weapons=[pick('mec', 'weapons', 'eItem_Chaingun')]
                + [m for m in ('eItem_MecKineticArm', 'eItem_MecFlameThrower') if m in lists['mec']['weapons']],
                items=[], look='man-b', country='eCountry_India', kind='mec')
    shiv = _unit(0, first='SHIV', last='', cls='eSC_None', armour=pick('shiv', 'armour', 'eItem_SHIVDeck_I'), sidearm=None,
                 weapons=[pick('shiv', 'weapons', 'eItem_ShivMinigun')], items=[], look=None, country=None, kind='shiv')
    for unit in (soldier, mec, shiv):
        unit.pop('id')
        unit['weapons'] = [w for w in unit['weapons'] if w]
        unit['items'] = [i for i in unit['items'] if i]
    return dict(soldier=soldier, mec=mec, shiv=shiv)
