"""Prepared local map exports, and the install's other maps listed for export on first open (exports.py); never import
game packages during a browser request."""
import json
from pathlib import Path
import re


# Maps checked in the game (the editor's verified bases), with their labels where no install list names them.
CHECKED_LABELS = {'URB_Bar': 'Bar', 'TempleShip': 'Temple Ship'}


def generation(folder):
    folder=Path(folder).resolve()
    manifest=folder/'scene.json'
    data=json.loads(manifest.read_text(encoding='utf8'))
    if not isinstance(data,dict):raise ValueError('Invalid scene manifest')
    name=data.get('name')
    if data.get('schemaVersion') != 1 or data.get('scope') not in ('map','sample'):
        raise ValueError('Unsupported scene manifest')
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*',name):
        raise ValueError('Invalid base map name')
    version=data.get('exporterVersion')
    if not isinstance(version,int) or version < 1: raise ValueError('Invalid exporter version')
    label=CHECKED_LABELS.get(name,name.replace('_',' '))
    return dict(id=name,name=name,label=label,root=folder,scope=data['scope'],ready=True,checked=name in CHECKED_LABELS,
                groups=[],missions=[],priority=(version,manifest.stat().st_mtime_ns,str(folder)))


def load_catalogue(folder, allow_empty=False):
    """Open one exact generation, or select the latest full export of each map. A cache root with none is an error,
    or with allow_empty (the server on a first run) a catalogue with no maps and no default map."""
    folder=Path(folder).resolve(strict=True)
    if (folder/'scene.json').is_file():
        entry=generation(folder)
        return dict(defaultMap=entry['id'],maps={entry['id']:entry})
    maps={}
    # A cache root has map folders containing published generations. A map folder
    # itself is also accepted. In-progress .export-* folders never become choices.
    for child in sorted(folder.iterdir()):
        if not child.is_dir() or child.name.startswith('.'): continue
        candidates=[child]+[p for p in child.iterdir() if p.is_dir() and not p.name.startswith('.')]
        for candidate in candidates:
            if not (candidate/'scene.json').is_file(): continue
            try: entry=generation(candidate)
            except (ValueError,OSError): continue
            if entry['scope'] != 'map': continue
            previous=maps.get(entry['id'])
            if previous is None or entry['priority'] > previous['priority']: maps[entry['id']]=entry
    if not maps:
        if allow_empty: return dict(defaultMap=None,maps={})
        raise ValueError('No prepared maps found. Export a map with --scope map first.')
    maps=dict(sorted(maps.items(),key=lambda pair:pair[1]['label'].casefold()))
    return dict(defaultMap=next(iter(maps)),maps=maps)


def with_install(catalogue, installed):
    """The catalogue with every map the game install plays (maplist.lwr_maps): exported maps take the install's label,
    mission groups and missions; the others are listed unprepared (no root, ready False) until exports.py exports
    them. The default map stays an exported one (with none exported, there is none). Names match whatever their case (packages and records differ:
    CsmallScout_Farm.upk, Name="CSmallScout_Farm"), and a map takes its record's name, which Builds look up."""
    maps={name:dict(entry) for name,entry in catalogue['maps'].items()}
    default=catalogue['defaultMap']
    folded={name.casefold():name for name in maps}
    for name,info in installed.items():
        known=folded.get(name.casefold())
        if known is not None and known != name:
            maps[name]=dict(maps.pop(known),id=name,name=name)
            if default == known: default=name
        entry=maps.get(name)
        if entry is None:
            entry=maps[name]=dict(id=name,name=name,root=None,scope='map',ready=False,checked=name in CHECKED_LABELS,
                                  priority=None)
        entry.update(label=info['label'],groups=list(info['groups']),missions=[dict(m) for m in info['missions']],installed=True)
    maps=dict(sorted(maps.items(),key=lambda pair:pair[1]['label'].casefold()))
    return dict(catalogue,defaultMap=default,maps=maps)


def public_catalogue(catalogue, current=None):
    """What the page shows: each map's id, label, whether it is exported (ready) and checked in the game, its mission
    groups (an export the install doesn't list is 'other') and its missions. With `current`, the exporter version a
    server that exports maps writes, `outdated: True` marks an exported map of the install whose export is older: the
    page exports it again when it opens (an update's exporter fixes reach maps exported before it)."""
    def outdated(entry):
        version=(entry.get('priority') or (0,))[0]
        return bool(current and entry.get('ready') and entry.get('installed') and entry.get('scope') == 'map'
                    and isinstance(version,int) and version < current)
    return dict(defaultMap=catalogue['defaultMap'],maps=[
        dict(id=entry['id'],name=entry['name'],label=entry['label'],ready=bool(entry.get('ready')),
             checked=bool(entry.get('checked')),groups=entry.get('groups') or ['other'],
             missions=entry.get('missions') or [],**({'outdated':True} if outdated(entry) else {}))
        for entry in list(catalogue['maps'].values())])
