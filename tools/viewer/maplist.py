"""Every map the LWR install plays, for the editor's map browser: read from its DefaultMaps.ini, never from a package.

Each live record (a `Maps=(` line not commented out) names a map package; a map can have several records, one per
mission it serves (an abduction, a terror site, capture-and-hold...). For each map this gives:
- `label`: a readable name from its records' display names (the part in brackets, without the development notes
  such as "Beta/Functionality Complete"), else its package name spaced out; LABELS names the few they don't give
  well, and maps that would share a label get their package name's last part in brackets;
- `groups`: the mission groups it serves, the browser's sections (a map is listed under each):
  abduction, ufo (crashed and landed), terror, council (special missions with a council type: rescue, bomb,
  assault, extraction), exalt (covert extraction, capture-and-hold data recovery, the EXALT raid), story (alien
  bases, Temple Ship, base defence, the DLC and tutorial missions), other (multiplayer);
- `missions`: its records' mission types, in file order, with their display names;
- `package`: where its package is (the EW folder first, then the base game's).

The strategy map (the XCOM base, Command1) is left out: it is not a battle map.

One map is listed from records the file comments out (SWITCHED_OFF): Act1_IntroLevel, the tutorial's map (Basic
Training, the first mission of a plain EW campaign with the tutorial on; under LWR a new campaign's first mission plays
URB_CommercialAlley_EWI, EXP-03). LWR keeps both of its records commented out: an abduction ("Helo Crash") and the
tutorial's (Basic Training, streaming the tutorial's script). The editor takes the abduction record, without its ';', as the map's record (records): the map
browser lists the map, the exporter reads its streams and a variant of it gets a copy (Build, Play in game). The
other maps whose records are all commented out are left out: Long War's EU maps, which need EU textures.
"""
import re

import mapsini
import settings

GROUPS = (('abduction', 'Abduction'), ('ufo', 'UFO'), ('terror', 'Terror'), ('council', 'Council'),
          ('exalt', 'EXALT'), ('story', 'Story'), ('other', 'Other'))
MISSION_GROUP = {'Abduction': 'abduction', 'Crash': 'ufo', 'LandedUFO': 'ufo', 'TerrorSite': 'terror',
                 'CovertOpsExtraction': 'exalt', 'CaptureAndHold': 'exalt', 'ExaltRaid': 'exalt',
                 'AlienBase': 'story', 'Final': 'story', 'HQAssault': 'story', 'MPDeathmatch': 'other'}
MISSION_LABEL = {'Abduction': 'Abduction', 'Crash': 'Crashed UFO', 'LandedUFO': 'Landed UFO', 'TerrorSite': 'Terror',
                 'CovertOpsExtraction': 'Covert extraction', 'CaptureAndHold': 'Data recovery',
                 'ExaltRaid': 'EXALT raid', 'AlienBase': 'Alien base', 'Final': 'Final mission',
                 'HQAssault': 'Base defence', 'MPDeathmatch': 'Multiplayer'}
COUNCIL_LABEL = {'Rescue': 'Council rescue', 'Bomb': 'Council bomb', 'Assault': 'Council assault',
                 'Extraction': 'Council extraction'}
LEFT_OUT = {'Strategy'}
# A map whose records are commented out that the editor still offers, and the missions of those records it takes as
# the map's (see the module notes).
SWITCHED_OFF = {'Act1_IntroLevel': ('Abduction',)}
COMMENTED = re.compile(r'^\s*;+\s*(Maps=\(.*)$')
# development notes at the start of a display name's bracketed part
NOTES = re.compile(r'^(?:beta/functionality complete|art placement complete|art placement|art complete|greybox|'
                   r'final|mission variant)\s+', re.I)
# bracketed parts that only name a mission, not the place
MISSION_ONLY = {'abduction', 'terror', 'capture and hold', 'covert extraction', 'fighter', 'crashed fighter',
                'landed raider', 'landed transport', 'landed terrorship', 'exalt headquarters assault'}
# Names the records don't give well: the DLC and tutorial missions (their records' display names are the package
# names), development jokes, typos, and a landed map whose note calls it crashed.
LABELS = {
    'Act2_Pier': 'Progress Pier (tutorial)', 'Act2_Pier_Asian': 'Progress Pier Asian (tutorial)',
    'CB2_MP_Blank': 'Blank (multiplayer)', 'CSupplyship_OverlookA': 'Landed Supply Ship Overlook',
    'DEMO_SonOfFacemelt': 'Son of Facemelt (demo)',
    'DLC1_1_LowFriends': 'Low Friends (Slingshot 1)', 'DLC1_2_CnfndLight': 'Confounding Light (Slingshot 2)',
    'DLC1_3_Gangplank': 'Gangplank (Slingshot 3)', 'DLC2_1_Portent': 'Portent (Progeny 1)',
    'DLC2_2_Deluge': 'Deluge (Progeny 2)', 'DLC2_3_Furies': 'Furies (Progeny 3)',
    'EWI_ChryssalidHive': 'Chryssalid Hive (Newfoundland)', 'EWI_ExaltHQAssault': 'EXALT HQ',
    'EWI_HQAssault': 'XCOM HQ (base defence)', 'EWI_MeldTutorial': 'Meld Tutorial',
    'LAbductor_FarmOutskirts': 'Landed Abductor Farm Outskirts',
    'LSmallScout_RiverValley': 'Landed Small Scout River Valley', 'URB_ConvienienceStore': 'Convenience Store',
    'URB_Highway1': 'Urban Highway', 'URB_IndustrialOffice': 'Industrial Office',
    'URB_PierA_Terror': 'Progress Pier Terror', 'URB_StreetHurricane': 'Street Hurricane',
    # labels that name one of the map's missions rather than the place
    'URB_PoliceStation': 'Police Station', 'URB_CommercialAlley': 'Commercial Alley',
    'URB_ResearchOutpost': 'Research Outpost', 'URB_Truckstop': 'Urban Truckstop',
    'URB_HighwayFallen': 'Urban Highway Fallen',
    'Act1_IntroLevel': 'Basic Training (tutorial map)',
}


def live_records(text):
    """The live `Maps=(` lines of a DefaultMaps.ini's text, in file order."""
    return [l.strip() for l in text.splitlines() if l.lstrip().startswith('Maps=(')]


def switched_off(line, live_names):
    """The record a commented-out line holds (from its `Maps=(` on), when the editor takes it as its map's (SWITCHED_OFF: a
    map listed there with no live record, a record of a mission taken), else None. `live_names`: the names the live
    records give."""
    m = COMMENTED.match(line)
    if not m:
        return None
    record = m.group(1)
    name = mapsini.field(record, 'Name')
    if name not in SWITCHED_OFF or name in live_names or mission_of(record)[1] not in SWITCHED_OFF[name]:
        return None
    return record


def records(text):
    """The records the editor works from, in file order, each as the file writes it (trailing blanks included): the live
    ones and the commented-out ones it takes (switched_off), without the ';' and what comes before the record."""
    live = {mapsini.field(l, 'Name') for l in live_records(text)}
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith('Maps=('):
            out.append(line)
        else:
            record = switched_off(line, live)
            if record:
                out.append(record)
    return out


def record_kind(line):
    """(mission type, council type) of one record (a line of text or bytes), each without its prefix: ('Abduction',
    'None'), ('Special', 'Bomb'). The one rule that the map list's missions (mission_of) and the mission kinds
    (missions.kind_key) are read by."""
    return ((mapsini.unquoted(line, 'MissionType') or '').replace('eMission_', ''),
            (mapsini.unquoted(line, 'CouncilType') or 'eFCMType_None').replace('eFCMType_', ''))


def mission_of(line):
    """(group, mission type without its prefix, readable mission label) of one record (record_kind; missions.KINDS
    gives each kind the same label: test_maplist holds the two)."""
    mission, council = record_kind(line)
    if mission == 'Special':
        if council in COUNCIL_LABEL:
            return 'council', mission, COUNCIL_LABEL[council]
        return 'story', mission, 'Special mission'
    return MISSION_GROUP.get(mission, 'other'), mission, MISSION_LABEL.get(mission, mission)


def label_of(name, display_names):
    """A readable name for a map from its records' display names (see the module notes)."""
    if name in LABELS:
        return LABELS[name]
    for display in display_names:
        m = re.search(r'\(([^)]*)\)', display)
        inner = (m.group(1) if m else '').strip()
        while True:
            stripped = NOTES.sub('', inner).strip()
            if stripped == inner:
                break
            inner = stripped
        inner = re.sub(r'\s+', ' ', inner)
        if inner and inner.lower() not in MISSION_ONLY:
            return inner[0].upper() + inner[1:]
    return re.sub(r'\s+', ' ', name.replace('_', ' ')).strip()


def package_of(lwr, name):
    """The map's package in the install (`lwr`, the game's folder): the EW folder first, then the base game's."""
    for folder in settings.cooked_folders(lwr):
        path = folder / f'{name}.upk'
        if path.is_file():
            return path
    return None


def lwr_maps(lwr):
    """{map name: entry} for every map the install's records name (records: the live ones and SWITCHED_OFF's; see the
    module notes). The records are LWR's own: what the editor installed (installs.py) is taken out first."""
    import installs
    maps = {}
    for line in records(installs.maps_text(lwr)):
        name = mapsini.field(line, 'Name')
        if not name or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', name):
            continue
        group, mission, label = mission_of(line)
        if mission in LEFT_OUT:
            continue
        entry = maps.setdefault(name, dict(name=name, family=mapsini.field(line, 'MapFamily') or name, displays=[],
                                           missions=[], groups=[]))
        entry['displays'].append(mapsini.field(line, 'DisplayName') or '')
        entry['missions'].append(dict(type=mission, label=label, display=mapsini.field(line, 'DisplayName') or ''))
        if group not in entry['groups']:
            entry['groups'].append(group)
    for name, entry in maps.items():
        entry['label'] = label_of(name, entry.pop('displays'))
        entry['groups'].sort(key=[g for g, _ in GROUPS].index)
        entry['package'] = package_of(lwr, name)
    distinct(maps)
    return maps


def distinct(maps):
    """Make labels unique: where maps share one, each gets its package name's last part in brackets, unless the label
    already says it (URB_Boulevard and URB_Boulevard_Euro: "Urban Boulevard" and "Urban Boulevard (Euro)")."""
    shared = {}
    for entry in maps.values():
        shared.setdefault(entry['label'].casefold(), []).append(entry)
    for entries in shared.values():
        if len(entries) < 2:
            continue
        for entry in entries:
            tail = entry['name'].rsplit('_', 1)[-1]
            if tail.casefold() not in entry['label'].replace(' ', '').casefold():
                entry['label'] += f' ({tail})'
