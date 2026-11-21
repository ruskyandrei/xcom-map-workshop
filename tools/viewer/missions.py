"""The kinds of mission a map's DefaultMaps.ini records give a battle, and what the editor knows of each
(private/plans/done/mission-types-plan.md): one table that Play in game (what a play of each kind needs, and what it
still goes without), the Build (the names the game matches in a record's display name) and the compiler (the maps
the game's script knows by name) share. The page has its twin of kind_key (web/missions.js) and reads the rest from
the server (/play.json's missionKinds).

A battle's kind is its record's: its MissionType, and for a council mission (eMission_Special) its CouncilType
(plan 2.1). Play in game installs the record of the mission picked (installs.py) and starts the game on it with the
console commands gamelaunch.py writes; a battle started that way has no campaign behind it, so a few things a
campaign would hand over are given by commands of their own (plan 2.2, A2):
- options on the `open` line, as the campaign's travel line has them for the kind: ?Meld=1 for abductions and UFOs,
  ?CapturePoints=1 for data recovery, ?RadarArrays=1 for data recovery and covert extraction (the map's loader adds
  the packages XComContent.ini lists for each);
- terror: the civilians' looks (the profile's m_kCivilianContent), read from the install's DefaultContent.ini as
  XGBattleDesc.BuildCivilianContent picks them (F-93: without them the game ran out of bounds giving them looks);
- crashed and landed UFOs: the UFO type (XGBattleDesc's m_eUFOType), from the record's ShipType;
- the Chryssalid Hive and Portent: which council mission it is (XGBattleDesc's m_eCouncilType).
Each of these goes in only once its run in the game has shown it to work (LINES: state 'works'); until then a play
goes without it and the play dialog says what is missing. A server started with --try-mission-lines puts the
untried ones in too, for the experiment that tries them (EXP-53).

The aliens stay four pods of Sectoids (five on a terror site) whatever the kind (decision 2): a mission's scripted
drop-ins and waves come from its stream whatever the pods are. EXALT missions get pods of EXALT operatives instead
(EXALT_KINDS), as the game's own battle set-up makes them for an EXALT type (15 November, after EXP-57's data recovery
had Sectoids).

The play dialog shows a kind's state, what it goes without and its notes as short paragraphs, one fact each.
"""
import re

import maplist
import mapsini

# A record's kind: its MissionType without eMission_, and for eMission_Special with a council type the council type
# (Special/Bomb). Special without one is a story or DLC mission.
COUNCIL = ('Bomb', 'Assault', 'Rescue', 'Extraction')

# A kind's state: 'works' (played and working on this path), 'untried' (not played yet: the run named tries it),
# 'hangs' (played: the battle stops at its start under Long War), 'no' (not played on this path at all). What the play
# dialog says of it: only a problem (the user, 16 November 2026: nothing says a kind is untried, or that it was tried).
STATES = {'works': '', 'untried': '', 'hangs': 'Hangs at the start under Long War', 'no': ''}
# The enemies a play has (gamelaunch.ALIENS, or EXALT_ALIENS for EXALT_KINDS), as the dialog says them
PODS_NOTE = 'Enemies: four pods of Sectoids.'
TERROR_PODS_NOTE = 'Enemies: five pods of Sectoids.'
EXALT_PODS_NOTE = 'Enemies: four pods of EXALT operatives, each with a heavy or a sniper.'
# (F-110: XComAlienPodManager places a commander only when the battle's description names one, which the campaign does)
COMMANDER_NOTE = 'No commander: the campaign adds one.'
OPERATIVE_NOTE = 'The covert operative is the game\'s stand-in (Debug McGee, with a pistol).'
# The stand-in operative takes the first unit's looks (XGBattle_SPCovertOpsExtraction.CreateDebugCovertOperative, on a
# battle with no campaign behind it). A SHIV has none, and the battle then waits on its loading screen for a body, head
# and voice that don't exist (T-44, EXP-72 runs 5, 10 and 11). So a play of a kind with an operative (`operative`)
# lands its first soldier or MEC trooper first, and says so; with only SHIVs it says what happens.
LEAD_NOTE = '{name} lands first: the covert operative takes the first unit\'s looks, which a SHIV doesn\'t have.'
NO_LEAD_MISSING = ('With only SHIVs in the squad the covert operative gets no looks, and the battle stays on its '
                   'loading screen.')
# EXALT's missions: their pods are EXALT_ALIENS (XGBattleDesc.GenerateAliens: the leader, one of the same and a sniper
# or heavy). Under Long War a play of one has saving on (play_setup's `saving`, SAVING_WHY for the dialog's checkbox):
# F-109, LWRebalance's RebalanceMutator.ReloadExaltMission saves every EXALT battle as it starts and loads the save,
# and a battle opened before the main menu's login can't finish a save (F-89; EXP-53 runs 2, 3 and 7 stopped at
# "Mission Briefing: Please Wait"). With saving on the battle opens after the login, and the reload went through
# (EXP-57 run 2, 15 November). Plain Enemy Within doesn't reload them; it hasn't been played.
EXALT_KINDS = ('CaptureAndHold', 'CovertOpsExtraction', 'ExaltRaid')
EXALT_ALIENS = 'eChar_ExaltOperative'
SAVING_KINDS = EXALT_KINDS
SAVING_WHY = 'Always on: Long War saves and reloads EXALT missions as they start.'

# kind -> label, group (maplist.GROUPS), state, the experiment run that tries it, the open line's options, the
# commands it may need (LINES) and anything else known of it on this path.
# EXP-53, played 15 November under LWR: runs 1 (council bomb), 4 (council rescue), 5 (crashed small scout) and 7 (base
# defence, alien base, Confounding Light) worked; runs 2, 3 and 7's EXALT HQ hung at the start (F-109): plays of
# those have saving on now (SAVING_KINDS). EXP-57 run 2 played a data recovery that way: the reload went through and
# the battle played, with Sectoids, which a play of an EXALT kind no longer has (EXALT_ALIENS).
KINDS = {
    'Abduction': dict(label='Abduction', state='works', run='EXP-29 and every play since', options=('Meld',)),
    'Crash': dict(label='Crashed UFO', state='works', run='EXP-53 run 5', options=('Meld',), lines=('ufoType',),
                  note=COMMANDER_NOTE),
    'LandedUFO': dict(label='Landed UFO', state='untried', run='EXP-53 run 5 played a crashed one', options=('Meld',),
                      lines=('ufoType',), note=COMMANDER_NOTE),
    # (played and working with the civilians' looks: EXP-53 run 6, 15 November, URB_StreetHurricane_Terror's variant)
    'TerrorSite': dict(label='Terror', state='works', run='EXP-53 run 6', lines=('civilians',)),
    'CaptureAndHold': dict(label='Data recovery', state='works', run='EXP-57 run 2, with saving on',
                           options=('CapturePoints', 'RadarArrays'), note=OPERATIVE_NOTE, operative=True),
    'CovertOpsExtraction': dict(label='Covert extraction', state='untried', run='EXP-57, with saving on',
                                options=('RadarArrays',), note=OPERATIVE_NOTE, operative=True),
    'Special/Bomb': dict(label='Council bomb', state='works', run='EXP-53 run 1', lines=('councilType',)),
    'Special/Assault': dict(label='Council assault', state='untried', run='EXP-53 run 4', lines=('councilType',)),
    'Special/Rescue': dict(label='Council rescue', state='works', run='EXP-53 run 4', lines=('councilType',)),
    'Special/Extraction': dict(label='Council extraction', state='untried', run='EXP-53 run 4', lines=('councilType',)),
    'Special': dict(label='Special mission', state='untried', run='one run for each story map', lines=('councilType',),
                    note='Story and DLC missions rely on the campaign (Zhang, the volunteer). Confounding Light works.'),
    'AlienBase': dict(label='Alien base', state='works', run='EXP-53 run 7', note=COMMANDER_NOTE),
    'Final': dict(label='Final mission', state='untried', run='EXP-53 run 7'),
    'HQAssault': dict(label='Base defence', state='works', run='EXP-53 run 7',
                      note='Base defence counts on the campaign\'s staff.'),
    'ExaltRaid': dict(label='EXALT raid', state='untried', run='EXP-57, with saving on'),
    'MPDeathmatch': dict(label='Multiplayer', state='no', run=None,
                         note='A multiplayer map: plays are single-player only.'),
}
for _key, _kind in KINDS.items():
    _kind.setdefault('options', ())
    _kind.setdefault('operative', False)
    _kind.setdefault('lines', ())
    _kind.setdefault('note', None)
    _kind['group'] = maplist.MISSION_GROUP.get(_key.split('/')[0], 'council' if _key.startswith('Special/') else
                                               'story' if _key == 'Special' else 'other')

# The commands a play may add for a kind, with whether they are known to work (plan A2). The open line's options are
# one line for this table: what they do was read from the exe, not played (O-2).
LINES = {
    # (O-2 answered, EXP-53 runs 2, 3 and 5, 15 November: with them the map's loader loaded CapturePointResources,
    # RadarArrayResources and MeldResources, and the battles started; runs 2 and 3 then hung for a reason of their own,
    # F-109. Still left out of plays: every kind played works without them, its content loading when first needed,
    # and as standard they would change every abduction's start, which no run has tried.)
    'options': dict(state='untried', run='EXP-53 runs 2, 3 and 5 (O-2)',
                    missing='The campaign\'s extra content for it ({options}) loads when first needed.'),
    # (F-107: a terror battle started without them hung at the loading screen, 12 and 15 November; with them it played,
    # EXP-53 run 6, 15 November. The missing sentence is for an install whose DefaultContent.ini gives no looks.)
    'civilians': dict(state='works', run='EXP-53 run 6 (O-4)',
                      missing='No civilian looks in this install\'s DefaultContent.ini: the battle never leaves the '
                              'loading screen (F-107).'),
    # (EXP-53 run 5 played with it and worked; whether it set anything the log doesn't show)
    'ufoType': dict(state='untried', run='EXP-53 run 5 (O-3)',
                    missing='The battle isn\'t told the UFO type (Long War\'s pods read it from the record).'),
    'councilType': dict(state='untried', run='EXP-53 run 7 (O-3)',
                        missing='The battle isn\'t told which council mission it is ({which}).'),
}

# Council missions the game's script tells apart by XGBattleDesc.m_eCouncilType (plan 2.2), by the record's map family.
COUNCIL_BY_MAP = {'EWI_ChryssalidHive': ('eFCM_ChryssalidHive', 'the Chryssalid Hive\'s end and narration'),
                  'DLC2_1_Portent': ('eFCM_Progeny_Portent', 'Portent\'s squad order')}

# Names the game matches (plan 2.5). DISPLAY_MARKERS: text the game's script looks for anywhere in the record's display
# name, which a variant's records keep (the Build: display_name). NAMED_MAPS: maps the script, a mutator or a Kismet
# switch knows by their whole name, which a variant can't keep: the compiler notes it.
DISPLAY_MARKERS = (
    ('_Bomb', 'Long War sends the bomb mission\'s reinforcements through its BombDisposalReinforcement throttle'),
    ('TempleShip', 'Long War orders the squad on its points as on the Temple Ship'),
)
NAMED_MAPS = {
    'EWI_ExaltHQAssault': 'the game reveals its buildings by the map\'s name',
    'EWI_HQAssault_MP': 'the game spawns no Meld there by the map\'s name',
    'EWI_MeldTutorial': 'the game gives the Meld tutorial its council type by the map\'s family',
    'DLC1_1_LowFriends': 'Zhang and the mission\'s script are tied to the map\'s name, and Long War lands there by it',
    'DLC1_2_CnfndLight': 'Zhang, the train\'s end and the stream\'s Kismet are tied to the map\'s name',
    'DLC1_3_Gangplank': 'Zhang and the mission\'s script are tied to the map\'s name',
    'DLC2_2_Deluge': 'the timer\'s wording and the stream\'s Kismet are tied to the map\'s name',
    'DLC2_3_Furies': 'the mission\'s script is tied to the map\'s name',
    'URB_SmallCemetery': 'Long War lands there by the map\'s name',
}

UFO_TYPES = ('eShip_UFOSmallScout', 'eShip_UFOLargeScout', 'eShip_UFOAbductor', 'eShip_UFOSupply', 'eShip_UFOBattle',
             'eShip_UFOEthereal')
OPTION, VALUE = re.compile(r'[A-Za-z][A-Za-z0-9]{0,31}'), re.compile(r'[A-Za-z0-9]{1,32}')


def kind_key(record):
    """A record's kind (a KINDS key) from its text (str or bytes), by the map list's rule (maplist.record_kind)."""
    mission, council = maplist.record_kind(record)
    if mission == 'Special':
        return f'Special/{council}' if council in COUNCIL else 'Special'
    return mission


def kind(key):
    """KINDS' entry for a kind, or one for a kind the table doesn't know (a mission type of another install)."""
    return KINDS.get(key) or dict(label=key or 'Unknown', state='untried', run=None, options=(), lines=(), note=None,
                                  group='other')


def label(key):
    return kind(key)['label']


# ---------------------------------------------------------------- what a play of a record needs

def civilian_content(content_text):
    """The value of the profile's m_kCivilianContent as XGBattleDesc.BuildCivilianContent would make it, from the
    install's DefaultContent.ini text: pawn 28, five civilians (men first, every other one a woman: three men, two
    women), each a civilian body of the game's own (no custom tag) with a civilian head of its race and gender and a
    hair a civilian can wear. The game picks at random; this takes the first of each, so a play is the same each time.
    None when the file lacks them."""
    def entries(key):
        out = []
        for line in content_text.splitlines():
            m = re.match(r'\s*\+?%s\s*=\s*\((.*)\)\s*$' % key, line)
            if m: out.append(dict(re.findall(r'(\w+)\s*=\s*("[^"]*"|[^,\s)]+)', m.group(1))))
        return out
    clean = lambda e: {k: v.strip('"') for k, v in e.items()}  # noqa: E731
    bodies = [clean(e) for e in entries('BodyPackageInfo')]
    heads = [clean(e) for e in entries('HeadPackageInfo')]
    hairs = [clean(e) for e in entries('HairPackageInfo')]
    out = dict(Male=dict(bodies=[], heads=[], hairs=[]), Female=dict(bodies=[], heads=[], hairs=[]))
    for gender, count in (('Male', 3), ('Female', 2)):
        free = [b for b in bodies if b.get('Character') == 'eChar_Civilian' and b.get('Gender') == f'eGender_{gender}'
                and not b.get('CustomTag') and b.get('Id', '').isdigit()]
        hair = [h for h in hairs if h.get('Gender') == f'eGender_{gender}' and h.get('bCanUseOnCivilian', '').lower() == 'true'
                and not h.get('CustomTag') and h.get('Id', '').isdigit()]
        for k, body in enumerate(free[:count]):
            head = [h for h in heads if h.get('Character') == 'eChar_Civilian' and h.get('Gender') == f'eGender_{gender}'
                    and h.get('Race') == body.get('Race') and h.get('Id', '').isdigit()]
            if not head or not hair: continue
            out[gender]['bodies'].append(int(body['Id']))
            out[gender]['heads'].append(int(head[k % len(head)]['Id']))
            out[gender]['hairs'].append(int(hair[k % len(hair)]['Id']))
    if not out['Male']['bodies'] or not out['Female']['bodies']: return None
    arrays = ','.join(f'{gender}{part.capitalize()}=({",".join(map(str, out[gender][part]))})'
                      for gender in ('Male', 'Female') for part in ('bodies', 'heads', 'hairs'))
    return f'(iPawn=28,{arrays})'


def play_setup(record, content_text=None, try_untried=False, lwr=False):
    """What a play of this record needs (plan A2): dict(kind, label, state, words, lines: the `set` commands to add,
    options: the open line's options [(name, value)], missing: what the play goes without, in sentences, notes: what
    else is known of the kind on this path, one sentence each, saving: why the play has saving on whatever was asked,
    or None, aliens: the pods' character for gamelaunch.play_text, or None for its default, operative: the battle has a
    covert operative who takes the first unit's looks, LEAD_NOTE).
    content_text: the install's DefaultContent.ini (for terror's civilians). try_untried: put in the commands not yet
    known to work (serve --try-mission-lines, for EXP-53). lwr: the install is Long War Rebalance (SAVING_KINDS)."""
    if isinstance(record, bytes): record = record.decode('latin-1')
    key = kind_key(record) if record else 'Abduction'
    k = kind(key)
    use = lambda line: LINES[line]['state'] == 'works' or try_untried  # noqa: E731
    lines, options, missing, notes = [], [], [], []
    if k['options']:
        if use('options'): options = [(name, '1') for name in k['options']]
        elif k['state'] != 'works':     # a kind played and working without them misses nothing
            missing.append(LINES['options']['missing'].format(options=', '.join(f'?{o}=1' for o in k['options'])))
    if 'ufoType' in k['lines']:
        ship = mapsini.unquoted(record or '', 'ShipType')
        if ship in UFO_TYPES:
            if use('ufoType'): lines.append(f'set XGBattleDesc m_eUFOType {ship}')
            else: missing.append(LINES['ufoType']['missing'])
    if 'councilType' in k['lines']:
        family = mapsini.field(record or '', 'MapFamily') or ''
        if family in COUNCIL_BY_MAP:
            value, which = COUNCIL_BY_MAP[family]
            if use('councilType'): lines.append(f'set XGBattleDesc m_eCouncilType {value}')
            else: missing.append(LINES['councilType']['missing'].format(which=which))
    if 'civilians' in k['lines']:
        value = civilian_content(content_text) if content_text else None
        if value and use('civilians'): lines.append(f'set XComOnlineProfileSettingsDataBlob m_kCivilianContent {value}')
        else: missing.append(LINES['civilians']['missing'])
    exalt = key in EXALT_KINDS
    if k['state'] != 'no':
        notes.append(EXALT_PODS_NOTE if exalt else TERROR_PODS_NOTE if key == 'TerrorSite' else PODS_NOTE)
    if k['note']: notes.append(k['note'])
    words = STATES[k['state']]
    for name, value in options:
        if not OPTION.fullmatch(name) or not VALUE.fullmatch(value): raise ValueError(f'bad option {name}={value}')
    return dict(kind=key, label=k['label'], state=k['state'], words=words, lines=lines, options=options,
                missing=missing, notes=notes, saving=SAVING_WHY if lwr and key in SAVING_KINDS else None,
                aliens=EXALT_ALIENS if exalt else None, operative=k['operative'])


def kinds_for_page(content_text=None, try_untried=False, lwr=False):
    """The kinds as the page shows them in the play dialog (/play.json): {kind: {label, group, state, words, missing,
    notes, saving}}, the missing sentences as a play of a typical record of the kind in this install would have them (a
    UFO with a ship type; content_text: the install's DefaultContent.ini; lwr: whether it is Long War Rebalance)."""
    out = {}
    for key, k in KINDS.items():
        sample = f'MissionType=eMission_{key.split("/")[0]}' + (f', CouncilType=eFCMType_{key.split("/")[1]}' if '/' in key else '')
        if 'ufoType' in k['lines']: sample += ', ShipType=eShip_UFOSmallScout'
        setup = play_setup(sample, content_text=content_text, try_untried=try_untried, lwr=lwr)
        out[key] = dict({f: setup[f] for f in ('label', 'state', 'words', 'missing', 'notes', 'saving')}, group=k['group'])
    return out


# ---------------------------------------------------------------- names the game matches

def markers(display, variant):
    """The DISPLAY_MARKERS a record's display name has that the variant's name lacks, as the suffix the variant's
    display name takes after its name ('_Bomb'), so the game's script finds them in the variant's record too."""
    out = ''
    for marker, _ in DISPLAY_MARKERS:
        if marker in (display or '') and marker not in variant:
            out += marker if marker.startswith('_') else f'_{marker}'
    return out


def display_name(base_display, variant, inner, tail=''):
    """A variant record's display name: '<variant><markers> (<inner>)<tail>' (markers: the matched text the base
    record's display name has, plan Part B)."""
    return f'{variant}{markers(base_display, variant)} ({inner}){tail}'


_WORDS = re.compile(r'\s*\S+\s*\((.*)\)\s*(\|\d+)?\s*')
_TAIL = re.compile(r'\s*(\|\d+)\s*$')
# what an added UFO mission's display name says of its ship: the words LWR reads a UFO's size from (its script looks
# for 'Small Scout', ' Crashed Destroyer ', ' Abductor ', ' Supply Ship ', ' Crashed Overseer ', ' BATTLESHIP' in the
# mission's map display name), spelt as the game's own records spell them
SHIP_WORDS = {'eShip_UFOSmallScout': 'Small Scout', 'eShip_UFOLargeScout': 'Large Scout', 'eShip_UFOAbductor': 'Abductor',
              'eShip_UFOSupply': 'Supply Ship', 'eShip_UFOBattle': 'Battleship', 'eShip_UFOEthereal': 'Overseer Ship'}
CRASHED_WORDS = dict(SHIP_WORDS, eShip_UFOLargeScout='Destroyer Ship')


def record_words(display):
    """(the words a record's display name has in brackets, its ' |n' ending or ''): 'CSmallScout_Farm (Crashed Small
    Scout - A Farm) |6' gives ('Crashed Small Scout - A Farm', ' |6'). A display name without brackets gives all of it
    but the ending."""
    display = display or ''
    m = _WORDS.fullmatch(display)
    if m: return m.group(1).strip(), f' {m.group(2)}' if m.group(2) else ''
    tail = _TAIL.search(display)
    return (display[:tail.start()] if tail else display).strip(), f' {tail.group(1)}' if tail else ''


def added_words(entry):
    """What an added mission kind's display name says after the base record's words: the kind, and for a UFO its
    ship in the words LWR reads the size from ('Crashed Abductor UFO')."""
    kind = entry['kind']
    if ADDED_KINDS.get(kind, {}).get('ufo'):
        words = (CRASHED_WORDS if kind == 'Crash' else SHIP_WORDS).get(entry.get('ship'), 'UFO')
        return '%s %s UFO' % ('Crashed' if kind == 'Crash' else 'Landed', words)
    return label(kind)


def variant_display(base_display, variant, added=None, tail=''):
    """A variant record's display name (LWR map packs plan, section 3): '<variant><markers> (<the base record's own
    words>) |n'. The words are kept whole, so what the game's script reads in them stays (LWR reads a UFO's size
    there), and nothing of the project's name is in it, so the name is the same at every export. `added`: the words
    of an added mission kind (added_words), put after the base record's. `tail`: the ending for a record that has
    none (the install's: LWR's records end ' |n', plain EW's don't)."""
    words, ending = record_words(base_display)
    if added: words = f'{words}, {added}' if words else added
    return f'{variant}{markers(base_display, variant)} ({words}){ending or tail}'


def matched(display):
    """What the game's script does by the record's display name: [(marker, what depends on it)]."""
    return [(marker, why) for marker, why in DISPLAY_MARKERS if marker in (display or '')]


def named_map(name):
    """What the game does by this map's whole name (NAMED_MAPS), or None."""
    return NAMED_MAPS.get(name)


# ---------------------------------------------------------------- a mission's objects (export 24: C2, C3)
# the page's twin is web/spawns_view.js KINDS
OBJECT_WORDS = {'dropIn': ('drop-in point', 'drop-in points'), 'pod': ('pod', 'pods'), 'landing': ('the landing', 'landings'),
                'soldier': ('a soldier\'s landing point', 'soldiers\' landing points'),
                'operative': ('the covert operative\'s point', 'operative\'s points'), 'vip': ('a VIP\'s point', 'VIPs\' points'),
                'capturePoint': ('a capture point', 'capture points'), 'radar': ('a radar array', 'radar arrays'),
                'bomb': ('the bomb', 'bombs'), 'powerNode': ('a power node', 'power nodes'),
                'use': ('a thing to use', 'things to use'), 'loot': ('a loot point', 'loot points')}
OBJECT_RISK = {
    'soldier': 'the squad lands there on this mission',
    'landing': 'the squad lands there on this mission',
    'operative': 'the game makes the covert operative there',
    'vip': 'the mission\'s VIP starts there',
    'bomb': 'Long War moves the bomb and its nodes to places of its own where it can, and plain Enemy Within plays '
            'them where they stand',
    'powerNode': 'Long War moves the bomb and its nodes to places of its own where it can, and plain Enemy Within '
                 'plays them where they stand',
}


def object_words(o, plural=False):
    """A mission object in words ('a capture point'; plural: 'capture points')."""
    words = OBJECT_WORDS.get(o.get('kind'), (o.get('kind') or 'object', (o.get('kind') or 'object') + 's'))
    return words[1] if plural else words[0]


def object_risk(o):
    """What may go wrong in the game when the object can't be reached."""
    return OBJECT_RISK.get(o.get('kind'), 'the mission\'s soldiers may not reach it, and its objective may not complete')


# ---------------------------------------------------------------- the missions a project is for (Part D)
# A project's `missions` (optional; absent, every mission of its base map): entries {record: i} (the base map's record
# i, the export's `missions` order) or {kind: one of ADDED_KINDS, ship: a UFO type for a UFO mission}: a kind a record
# alone gives a map (decision 6), made from the base map's abduction record (or its first that is no council mission).
BOMB_STREAM = 'URB_Slaughterhouse_Stream'     # LWR gives Boulevard, Fast Food and Street Hurricane their bomb with it
def group_words(group):
    """A mission object's group as words: 'the bomb', 'power node XComLevelActor_6', 'capture point ...'."""
    group = str(group or '')
    if group == 'bomb':
        return 'the bomb'
    if group.startswith('node:'):
        return 'power node %s' % group[5:]
    if group.startswith('capture:'):
        return 'capture point %s' % group[8:]
    return group


ADDED_KINDS = {
    'Abduction': dict(fields=dict(MissionType='eMission_Abduction', CouncilType='eFCMType_None', ShipType='eShip_None'),
                      rotation=True, needs='Nothing under Long War (pods and Meld are placed at load); plain Enemy Within '
                                           'plays the base map\'s pods where they stood.'),
    'TerrorSite': dict(fields=dict(MissionType='eMission_TerrorSite', CouncilType='eFCMType_None', ShipType='eShip_None'),
                       rotation=True, needs='Nothing under Long War: civilians stand at cover the game finds.'),
    'Special/Bomb': dict(fields=dict(MissionType='eMission_Special', CouncilType='eFCMType_Bomb', ShipType='eShip_None'),
                         rotation=False, stream=BOMB_STREAM, lwr=True,
                         needs='Long War only: its bomb mutator places Slaughterhouse\'s bomb and power nodes on the map.'),
    'Crash': dict(fields=dict(MissionType='eMission_Crash', CouncilType='eFCMType_None'), rotation=True, ufo=True,
                  needs='A UFO building on the map (a UFO prefab): Long War puts the commander\'s pod in it.'),
    'LandedUFO': dict(fields=dict(MissionType='eMission_LandedUFO', CouncilType='eFCMType_None'), rotation=True, ufo=True,
                      needs='A UFO building on the map (a UFO prefab): Long War puts the commander\'s pod in it.'),
}


def valid_entry(entry, records):
    """Whether a `missions` entry is one the Build can write, for a base map with `records` missions (a kind that is a
    list or an object is no entry, never a TypeError)."""
    if not isinstance(entry, dict): return False
    if set(entry) == {'record'}:
        return isinstance(entry['record'], int) and not isinstance(entry['record'], bool) and 0 <= entry['record'] < records
    if isinstance(entry.get('kind'), str) and entry['kind'] in ADDED_KINDS and set(entry) <= {'kind', 'ship'}:
        return entry.get('ship') in UFO_TYPES if ADDED_KINDS[entry['kind']].get('ufo') else 'ship' not in entry
    return False


def _set(line, name, value):
    """A record's unquoted field set (mapsini.set_field), or added before the closing bracket when the record has
    none."""
    if mapsini.unquoted(line, name) is not None: return mapsini.set_field(line, name, value, quoted=False)
    close = line.rindex(')')
    return line[:close].rstrip() + ', %s=%s ' % (name, value) + line[close:]


def added_record(template, entry):
    """The record of an added kind (ADDED_KINDS), from the base map's template record (text): its mission type,
    council type and ship type set, and for the bomb Slaughterhouse's bomb stream streamed (mapsini.add_stream, which
    refuses with a ValueError: the Build's record_edits says it). Name, display name and rotation are the caller's."""
    k = ADDED_KINDS[entry['kind']]
    line = template
    for name, value in k['fields'].items():
        line = _set(line, name, value)
    if k.get('ufo'):
        line = _set(line, 'ShipType', entry['ship'])
    if k.get('stream') and ('MapName="%s"' % k['stream']) not in line:
        line, _ = mapsini.add_stream(line, k['stream'])
    return line
