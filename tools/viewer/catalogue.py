"""Prepared local map exports, and the install's other maps listed for export on first open (exports.py); never import
game packages during a browser request.

What makes a generation folder usable is decided here once, for the map list, the cache's pruning (prune.py) and the
Build's choice of export (compiler.find_export): its scene.json reads whole as a scene of schema 1, of a map or a piece
study (an earlier exporter's, read only to be pruned: the editor opens whole maps), with a map name and an exporter
version, and a folder named as a generation
(<first 16 hex digits of the package's SHA-256>-v<exporter version>-<scope>[-<suffix>]) agrees with what its scene
says of the package, the version and the scope. A truncated or foreign scene.json is no candidate: the next one is
taken (review finding 17).

A map's exports are chosen by the package they were made from (review finding 18): with a game install, a map takes
the newest generation made from the install's own file of it (its SHA-256), and is listed unprepared (exported on first
open) when the cache holds only other packages' exports of it, such as another install's copy.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid


# Maps checked in the game (the editor's verified bases), with their labels where no install list names them.
CHECKED_LABELS = {'URB_Bar': 'Bar', 'TempleShip': 'Temple Ship'}
GENERATION = re.compile(r'^(?P<digest>[0-9a-f]{16})-v(?P<version>\d+)-(?P<scope>map|sample)(?:-[A-Za-z0-9_]+)?$')
SHA256 = re.compile(r'[0-9a-f]{64}')
_MEMO = {}          # a scene.json as it is (path, size, time) -> its entry, or the reason it is no candidate
_MEMO_LOCK = threading.Lock()


def check_scene(folder, data, stat=None):
    """The catalogue entry of the generation `folder` whose scene.json holds `data` (raises ValueError saying why it is
    no usable generation)."""
    if not isinstance(data,dict):raise ValueError('Invalid scene manifest')
    name=data.get('name')
    if data.get('schemaVersion') != 1 or data.get('scope') not in ('map','sample'):
        raise ValueError('Unsupported scene manifest')
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*',name):
        raise ValueError('Invalid base map name')
    version=data.get('exporterVersion')
    if not isinstance(version,int) or isinstance(version,bool) or version < 1: raise ValueError('Invalid exporter version')
    source=data.get('source')
    sha=source.get('sha256') if isinstance(source,dict) else None
    sha=sha if isinstance(sha,str) and SHA256.fullmatch(sha) else None
    named=GENERATION.match(folder.name)
    if named:
        if sha is not None and not sha.startswith(named.group('digest')):
            raise ValueError(f'{folder.name} holds an export of another package ({sha[:16]})')
        if int(named.group('version')) != version or named.group('scope') != data['scope']:
            raise ValueError(f'{folder.name} holds an export of version {version} ({data["scope"]})')
    label=CHECKED_LABELS.get(name,name.replace('_',' '))
    mtime=(stat or (folder/'scene.json').stat()).st_mtime_ns
    return dict(id=name,name=name,label=label,root=folder,scope=data['scope'],ready=True,checked=name in CHECKED_LABELS,
                groups=[],missions=[],sha256=sha,priority=(version,mtime,str(folder)))


def read_scene(folder):
    """(entry, the scene's data) of a generation folder, read whole (raises ValueError or OSError saying why it is no
    usable generation): the Build's reading (compiler.find_export)."""
    folder=Path(folder).resolve()
    manifest=folder/'scene.json'
    stat=manifest.stat()
    data=json.loads(manifest.read_text(encoding='utf8'))
    return check_scene(folder,data,stat),data


def generation(folder):
    """The catalogue entry of a generation folder (raises ValueError or OSError saying why it is no usable generation).
    A scene.json is read once as it is (its size and time): the map list and the pruning ask for the same folders."""
    folder=Path(folder).resolve()
    manifest=folder/'scene.json'
    stat=manifest.stat()
    key=(str(manifest),stat.st_size,stat.st_mtime_ns)
    with _MEMO_LOCK:
        known=_MEMO.get(key)
    if known is None:
        try: known=read_scene(folder)[0]
        except ValueError as error: known=ValueError(str(error))
        with _MEMO_LOCK:
            _MEMO[key]=known
    if isinstance(known,ValueError): raise ValueError(str(known))
    return dict(known,groups=[],missions=[])


def usable(folder):
    """Whether a folder holds a usable generation (generation() reads it)."""
    try:
        generation(folder)
        return True
    except (ValueError,OSError):
        return False


def newer(a, b):
    return b is None or a['priority'] > b['priority']


def load_catalogue(folder, allow_empty=False):
    """Open one exact generation, or select the latest full export of each map. A cache root with none is an error,
    or with allow_empty (the server on a first run) a catalogue with no maps and no default map. Each map's entry keeps
    `candidates`, its newest generation of each package ({SHA-256 or None: entry}), which with_install chooses from."""
    folder=Path(folder).resolve(strict=True)
    if (folder/'scene.json').is_file():
        entry=generation(folder)
        if entry['scope'] != 'map':
            # (an earlier exporter's piece study, of three of URB_Bar's pieces: its folders are still read, to be
            # pruned, but the editor opens whole maps only)
            raise ValueError(f'{folder.name} is a piece study of an earlier export, which the editor no longer opens: '
                             'export the whole map')
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
            kept=dict(previous['candidates']) if previous else {}
            if newer(entry,kept.get(entry['sha256'])): kept[entry['sha256']]=entry
            maps[entry['id']]=dict(entry if newer(entry,previous) else previous,candidates=kept)
    if not maps:
        if allow_empty: return dict(defaultMap=None,maps={})
        raise ValueError('No prepared maps found. Export a map with --scope map first.')
    maps=dict(sorted(maps.items(),key=lambda pair:pair[1]['label'].casefold()))
    return dict(defaultMap=next(iter(maps)),maps=maps)


def chosen(entry, digest):
    """The entry's generation made from the package whose SHA-256 is `digest`: its newest candidate of that package,
    or None. `digest` None (the install's file not known): the newest of any package, as before."""
    candidates=entry.get('candidates') or ({entry['sha256']:entry} if entry.get('root') else {})
    if digest is None:
        return max(candidates.values(),key=lambda e:e['priority'],default=None)
    return candidates.get(digest)


def select(entry, digest, stamp=None):
    """The entry made to serve the generation chosen() gives for `digest`, or unprepared (no root, ready False: exported
    on first open) when the cache has none of that package. `stamp`: the package file as it was hashed (path, size,
    time), kept so recheck() sees it change."""
    pick=chosen(entry,digest)
    out=dict(entry,packageDigest=digest,packageStamp=stamp)
    if pick is None:
        out.update(root=None,ready=False,priority=None,sha256=None)
    else:
        out.update(root=pick['root'],scope=pick['scope'],ready=True,priority=pick['priority'],sha256=pick['sha256'])
    return out


def with_install(catalogue, installed, digests=None):
    """The catalogue with every map the game install plays (maplist.lwr_maps): exported maps take the install's label,
    mission groups and missions; the others are listed unprepared (no root, ready False) until exports.py exports
    them. The default map stays an exported one (with none exported, there is none). Names match whatever their case (packages and records differ:
    CsmallScout_Farm.upk, Name="CSmallScout_Farm"), and a map takes its record's name, which Builds look up.
    `digests(name)`: (the SHA-256 of the install's file of the map, its stamp) or None when unknown; an exported map
    then serves its newest export of that file, and is unprepared when the cache has exports of other files only."""
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
        elif digests is not None:
            found=digests(name)
            if found is not None:
                entry=maps[name]=select(entry,*found)
        entry.update(label=info['label'],groups=list(info['groups']),missions=[dict(m) for m in info['missions']],installed=True)
    if default is not None and not (maps.get(default) or {}).get('root'):
        default=next((name for name,entry in sorted(maps.items(),key=lambda pair:pair[1]['label'].casefold())
                      if entry.get('root')),None)
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


class PackageDigests:
    """The SHA-256 of game packages, worked out once for each file as it is (its size and time) and kept in the cache
    root (.package-digests.json), so a server start hashes only what changed."""

    def __init__(self, cache_root=None):
        self.path=Path(cache_root)/'.package-digests.json' if cache_root else None
        self.lock=threading.Lock()
        self.known=None
        self.changed=False

    def _load(self):
        if self.known is not None: return
        self.known={}
        if self.path is None: return
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(data,dict):
                self.known={k:v for k,v in data.items() if isinstance(v,list) and len(v) == 3}
        except (OSError,ValueError):
            pass

    @staticmethod
    def stamp(path):
        stat=Path(path).stat()
        return (os.path.normcase(str(Path(path).resolve())),stat.st_size,stat.st_mtime_ns)

    def digest(self, path):
        """(SHA-256, stamp) of the file at `path`; raises OSError when it can't be read."""
        stamp=self.stamp(path)
        with self.lock:
            self._load()
            kept=self.known.get(stamp[0])
        if kept and (kept[0],kept[1]) == stamp[1:] and isinstance(kept[2],str) and SHA256.fullmatch(kept[2]):
            return kept[2],stamp
        with open(path,'rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
        with self.lock:
            self.known[stamp[0]]=[stamp[1],stamp[2],sha]
            self.changed=True
        return sha,stamp

    def save(self):
        with self.lock:
            if not self.changed or self.path is None: return
            data,self.changed=dict(self.known),False
        temp=self.path.with_name(f'{self.path.name}.{uuid.uuid4().hex[:8]}.tmp')
        try:
            temp.write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
            os.replace(temp,self.path)
        except OSError:
            temp.unlink(missing_ok=True)
