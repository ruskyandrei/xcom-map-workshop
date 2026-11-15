"""What stands between a map and the art of the game's other maps: a read-only audit of a game install, made for
private/plans/done/cross-map-assets-plan.md.

  python -B tools/upk/audit_cross_map.py <game install> <out.json> [--jobs 6] [--no-pairs] [--no-shaders]

Over every base map and streamed level a live DefaultMaps.ini record names:
- the library: the art each package holds under the game's own asset packages (an object under a top-level Package
  export: a mesh, material, texture, effect, sound or archetype, as against the map's own level and its baked
  textures), how many packages hold each object, and the objects that have one path but different sizes;
- the same object in two maps (--no-pairs leaves it out): each Firaxis-cooked base map against the next, every
  object both hold compared byte for byte. A difference counts as explained when it is a name or an object number
  that means the same in both packages, an offset inside the export's own data (bulk data is addressed by its place
  in the file), a material's LightingGuid or ParentLightingGuid, or the last four bytes of a material (one value per
  package). Anything else is listed;
- the shaders (--no-shaders leaves it out): whether every base material (Material, DecalMaterial) of every package has
  an entry in the install's one RefShaderCache: any 16 bytes of the material's last 400, with at least 13 of them
  non-zero, found in the cache. No map holds shader data of its own (the survey counts ShaderCache exports);
- which texture cache file each texture's large mips are in (its TextureFileCacheName);
- what the maps import from outside themselves: per top-level package, the classes imported, how many maps import
  them, and which always-loaded package holds it (the startup package, a script package);
- companion packages: for each <level>_LOC_INT.upk beside a level, the objects the level imports that only the
  companion holds;
- for private/plans/done/cross-map-assets-implementation-plan.md (its X0), with the pairs:
  - the export-table entry of each object and asset package both maps hold: its object flags, export flags,
    generation count, net object counts, package GUID and package flags, and the object's net index (the 4 bytes
    before its tagged properties);
  - per class, the objects whose explained differences (a name, an object number, an offset) lie beyond their tagged
    properties, in native data, and the most such fields one object has;
  and without them, which texture cache each baked texture (LightMapTexture2D, ShadowMapTexture2D) of every package
  names;
- the walk (--no-walk leaves it out; the plan's X1 and X2 gates): every export of every Firaxis-cooked package read
  by the game's property types (schema.py, typed_props.py) and, where it has native data, by its class's layout
  (native_fields.py): the exports whose walk fails, the arrays no script package types, the classes read by a layout,
  the classes with native data that are known to be plain, and the classes with native data and no layout.
"""
import argparse
import collections
import json
import multiprocessing
import os
import re
import struct
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = 'TheWorld'
MATERIALS = ('Material', 'DecalMaterial', 'MaterialInstanceConstant', 'MaterialInstanceTimeVarying')
BASE_MATERIALS = ('Material', 'DecalMaterial')
GUIDS = ('LightingGuid', 'ParentLightingGuid')
# the classes the summary tables list first (every class is counted)
LISTED = ('StaticMesh', 'FracturedStaticMesh', 'SkeletalMesh', 'Material', 'MaterialInstanceConstant',
          'MaterialInstanceTimeVarying', 'DecalMaterial', 'Texture2D', 'ParticleSystem', 'SoundCue', 'SoundNodeWave',
          'PhysicalMaterial', 'PhysicsAsset', 'AnimSet', 'Prefab', 'XComDestructibleActor', 'XComLevelActor',
          'XComFracLevelActor', 'XComDecoFracLevelActor', 'XComInteractiveLevelActor', 'KAsset')
ALWAYS_LOADED = ('Startup', 'Core', 'Engine', 'GameFramework', 'GFxUI', 'XComGame', 'XComStrategyGame', 'XComUIShell')
BAKED = ('LightMapTexture2D', 'ShadowMapTexture2D')
ENTRY_FIELDS = ('objectFlags', 'exportFlags', 'generations', 'netCounts', 'guid', 'packageFlags')
PROP_TYPES = ('BoolProperty', 'StructProperty', 'ByteProperty', 'IntProperty', 'FloatProperty', 'ObjectProperty',
              'ComponentProperty', 'ClassProperty', 'InterfaceProperty', 'NameProperty', 'StrProperty', 'ArrayProperty',
              'DelegateProperty', 'MapProperty')
TAIL = 400          # a base material's shader map ID lies in its last bytes (83 to 139 from the end where sampled)
CACHE_TAIL = 24 << 20   # the cache's material index is at its end; the whole cache is scanned if this misses any


def load_any(path):
    """A package's logical bytes and summary, also one the cooker compressed whole (the startup packages)."""
    sys.path.insert(0, HERE)
    import lzo1x
    import upkinfo as U
    raw = Path(path).read_bytes()
    tag, block, _, total = struct.unpack_from('<IIII', raw, 0)
    if tag == 0x9E2A83C1 and block == 131072:
        count = (total + block - 1) // block
        at, out = 16 + 8 * count, bytearray()
        for n in range(count):
            packed, unpacked = struct.unpack_from('<II', raw, 16 + 8 * n)
            out += lzo1x.decompress(raw[at:at + packed], unpacked)
            at += packed
        raw = bytes(out)
        return raw, U.summary(raw)
    return U.load(str(path))


class Pack:
    def __init__(self, path):
        sys.path.insert(0, HERE)
        import upkinfo as U
        self.U, self.name = U, Path(path).stem
        self.b, self.h = load_any(path)
        self.names, self.imps, self.exps = U.tables(self.b, self.h)
        self.cls = [U.clsname(e['cls'], self.imps, self.exps) for e in self.exps]
        self._full = {}

    def full(self, index):
        """An object's path by its export (positive) or import (negative) number, None for one out of range."""
        if index == 0 or index > len(self.exps) or -index > len(self.imps):
            return None
        if index not in self._full:
            self._full[index] = self.U.objname(index, self.imps, self.exps)
        return self._full[index]

    def top(self, n):
        while self.exps[n]['outer'] > 0:
            n = self.exps[n]['outer'] - 1
        return n

    def assets(self):
        """{(class, path): export number} of the objects under a top-level Package export."""
        out = {}
        for n, e in enumerate(self.exps):
            if e['outer'] <= 0 or self.cls[n] == 'Package':
                continue
            top = self.top(n)
            if self.cls[top] == 'Package' and self.exps[top]['name'] != WORLD:
                out[(self.cls[n], self.full(n + 1))] = n
        return out

    def data(self, n):
        e = self.exps[n]
        return self.b[e['off']:e['off'] + e['size']]

    def packages(self):
        """{path: export number} of the asset packages: the Package exports that are not the level's."""
        return {self.full(n + 1): n for n in range(len(self.exps))
                if self.cls[n] == 'Package' and self.exps[self.top(n)]['name'] != WORLD}

    def entry(self, n):
        """The fields of export `n`'s table entry that upkinfo.tables leaves out."""
        if not hasattr(self, '_entries'):
            self._entries, at = [], self.h['expoff']
            for _ in self.exps:
                self._entries.append(at)
                at += 68 + 4 * struct.unpack_from('<I', self.b, at + 44)[0]
        at = self._entries[n]
        flags, = struct.unpack_from('<Q', self.b, at + 24)
        export_flags, count = struct.unpack_from('<II', self.b, at + 40)
        return dict(objectFlags=flags, exportFlags=export_flags, generations=count,
                    netCounts=list(struct.unpack_from('<%dI' % count, self.b, at + 48)),
                    guid=self.b[at + 48 + 4 * count:at + 64 + 4 * count].hex(),
                    packageFlags=struct.unpack_from('<I', self.b, at + 64 + 4 * count)[0])

    def props(self, n):
        """Where export `n`'s tagged properties begin and end, from the start of its data (the end None when the
        walk fails)."""
        sys.path.insert(0, HERE)
        import props
        e, b = self.exps[n], self.b
        start = o = props.props_start(b, e, self.names)
        end = e['off'] + e['size']
        while o + 8 <= end:
            i, number = struct.unpack_from('<ii', b, o)
            if not 0 <= i < len(self.names):
                break
            if self.names[i] == 'None' and number == 0:
                return start - e['off'], o + 8 - e['off']
            t = struct.unpack_from('<i', b, o + 8)[0]
            if not 0 <= t < len(self.names) or self.names[t] not in PROP_TYPES:
                break
            size = struct.unpack_from('<i', b, o + 16)[0]
            o += 24 + (1 if self.names[t] == 'BoolProperty' else
                       8 + size if self.names[t] in ('StructProperty', 'ByteProperty') else size)
        return start - e['off'], None


def survey(path):
    try:
        p = Pack(path)
    except Exception as error:  # noqa: BLE001
        return Path(path).stem, dict(error=repr(error))
    assets = p.assets()
    imports = collections.defaultdict(collections.Counter)
    for n, e in enumerate(p.imps):
        if e['cls'] not in ('Class', 'Package'):
            imports[p.full(-n - 1).split('.')[0]][e['cls']] += 1
    windows, caches = {}, {}
    cache_tag = None
    if 'TextureFileCacheName' in p.names and 'NameProperty' in p.names:
        cache_tag = struct.pack('<iiii', p.names.index('TextureFileCacheName'), 0, p.names.index('NameProperty'), 0)
    for (cls, path_), n in assets.items():
        if cls == 'Texture2D':
            d = p.data(n)
            at = d.find(cache_tag) if cache_tag else -1
            caches[path_] = p.names[struct.unpack_from('<i', d, at + 24)[0]] if at >= 0 else '(in the package)'
        if cls in BASE_MATERIALS:
            d = p.data(n)
            start = max(0, len(d) - TAIL)
            windows[path_] = sorted({d[o:o + 16].hex() for o in range(start, len(d) - 15)
                                     if sum(1 for x in d[o:o + 16] if x) >= 13})
    baked = collections.Counter()
    for n in range(len(p.exps)):
        if p.cls[n] in BAKED:
            d = p.data(n)
            at = d.find(cache_tag) if cache_tag else -1
            baked[p.names[struct.unpack_from('<i', d, at + 24)[0]] if at >= 0 else '(in the package)'] += 1
    return p.name, dict(licensee=p.h['lic'], bytes=len(p.b), exports=len(p.exps), bakedCaches=dict(baked),
                        shaderCaches=sum(1 for c in p.cls if 'ShaderCache' in c),
                        assets=[(cls, path_, p.exps[n]['size']) for (cls, path_), n in assets.items()],
                        imports={top: dict(c) for top, c in imports.items()}, materialWindows=windows,
                        textureCaches=caches)


def guid_spans(p, data):
    """The 16 value bytes of each LightingGuid and ParentLightingGuid property in an export's data."""
    spans = []
    for key in GUIDS:
        if key not in p.names or 'StructProperty' not in p.names:
            continue
        tag = struct.pack('<iiii', p.names.index(key), 0, p.names.index('StructProperty'), 0)
        at = data.find(tag)
        while at >= 0:
            spans.append((at + 32, at + 48))    # tag: name 8, type 8, size 4, array index 4, struct name 8
            at = data.find(tag, at + 1)
    return spans


def compare_entries(A, B, in_a, in_b):
    """The export-table entries and net indices of what both packages hold: counts, and up to three examples of
    each difference."""
    count, examples = collections.Counter(), collections.defaultdict(list)

    def differs(what, path_, x, y):
        count[what + 'Differs'] += 1
        if len(examples[what]) < 3:
            examples[what].append(dict(object=path_, values=[x, y]))
    for (cls, path_) in sorted(set(in_a) & set(in_b)):
        na, nb = in_a[(cls, path_)], in_b[(cls, path_)]
        kind = 'object' if cls != 'Package' else 'package'
        count[kind + 's'] += 1
        fa, fb = A.entry(na), B.entry(nb)
        for f in ENTRY_FIELDS:
            if fa[f] != fb[f]:
                differs(kind + f[0].upper() + f[1:], path_, fa[f], fb[f])
        if cls == 'Package':
            continue
        (sa, _), (sb, _) = A.props(na), B.props(nb)
        if sa < 4 or sb < 4:
            count['noNetIndex'] += 1
            continue
        xa = struct.unpack_from('<i', A.b, A.exps[na]['off'] + sa - 4)[0]
        xb = struct.unpack_from('<i', B.b, B.exps[nb]['off'] + sb - 4)[0]
        count['netIndex' + ('Minus1' if xa == -1 else 'Zero' if xa == 0 else 'Above0')] += 1
        if xa != xb:
            differs('netIndex', path_, xa, xb)
    return dict(count), dict(examples)


def compare(job):
    """Every asset two packages both hold, byte for byte; and their export-table entries."""
    path_a, path_b = job
    import numpy as np
    A, B = Pack(path_a), Pack(path_b)
    in_a, in_b = A.assets(), B.assets()
    entries = compare_entries(A, B, {**in_a, **{('Package', k): n for k, n in A.packages().items()}},
                              {**in_b, **{('Package', k): n for k, n in B.packages().items()}})
    rows = collections.defaultdict(collections.Counter)
    native = collections.defaultdict(collections.Counter)
    fields, odd, listed = collections.Counter(), [], collections.Counter()
    for key in sorted(set(in_a) & set(in_b)):
        cls = key[0]
        row = rows[cls]
        row['objects'] += 1
        ea, eb = A.exps[in_a[key]], B.exps[in_b[key]]
        if ea['size'] != eb['size']:
            row['sizeDiffers'] += 1
            listed[cls] += 1
            if listed[cls] <= 2:
                odd.append(dict(object=key[1], cls=cls, sizes=[ea['size'], eb['size']]))
            continue
        da, db = A.data(in_a[key]), B.data(in_b[key])
        if da == db:
            row['identical'] += 1
            continue
        size = len(da)
        covered = bytearray(size)
        if cls in MATERIALS:
            for p, d in ((A, da), (B, db)):
                for lo, hi in guid_spans(p, d):
                    covered[lo:hi] = b'\1' * (hi - lo)
            if cls in BASE_MATERIALS:
                covered[size - 4:] = b'\1' * 4
        unexplained = []
        props_end = A.props(in_a[key])[1]
        beyond = collections.Counter()
        native[cls]['compared'] += 1
        if props_end is None:
            native[cls]['propertiesNotWalked'] += 1
        differing = np.flatnonzero(np.frombuffer(da, np.uint8) != np.frombuffer(db, np.uint8))
        noise = False
        for j in differing.tolist():
            if covered[j]:
                noise = noise or cls in MATERIALS
                continue
            for back in range(4):
                o = j - back
                if o < 0 or o + 4 > size:
                    continue
                va, vb = struct.unpack_from('<i', da, o)[0], struct.unpack_from('<i', db, o)[0]
                if 0 <= va < len(A.names) and 0 <= vb < len(B.names) and A.names[va] == B.names[vb]:
                    kind = 'name'
                elif A.full(va) is not None and A.full(va) == B.full(vb):
                    kind = 'object'
                elif va - ea['off'] == vb - eb['off'] and 0 <= va - ea['off'] <= size:
                    kind = 'offset'
                else:
                    continue
                fields[kind] += 1
                if props_end is not None and o >= props_end:
                    beyond[kind] += 1
                covered[o:o + 4] = b'\1' * 4
                break
            else:
                unexplained.append(j)
        for kind, n in beyond.items():
            native[cls]['with' + kind.title()] += 1
            native[cls]['max' + kind.title()] = max(native[cls]['max' + kind.title()], n)
        if unexplained:
            row['unexplained'] += 1
            listed[cls] += 1
            if listed[cls] <= 2:
                j = unexplained[0]
                odd.append(dict(object=key[1], cls=cls, size=size, bytes=len(unexplained), at=unexplained[:8],
                                first=[da[j:j + 8].hex(), db[j:j + 8].hex()]))
        else:
            row['explained'] += 1
            if noise:
                fields['materialNoise'] += 1
    return (A.name, B.name, {cls: dict(row) for cls, row in rows.items()}, dict(fields), odd, entries,
            {cls: dict(row) for cls, row in native.items()})


_SCHEMA = {}


def walk(path):
    """Every export of a package by its property types and its native layout."""
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'viewer'))
    import native_fields
    import schema
    import typed_props
    from package import Package
    folder = os.path.dirname(os.path.abspath(path))
    if folder not in _SCHEMA:
        _SCHEMA[folder] = schema.Schema(schema.build(folder))
    p = Package(path)
    out = typed_props.survey(p, _SCHEMA[folder])
    mapped, plain, unmapped, bad = (collections.Counter() for _ in range(4))
    examples = []
    for index in range(1, len(p.exports) + 1):
        try:
            end = typed_props.fields(p, index, _SCHEMA[folder]).end
        except typed_props.WalkError:
            continue
        if end == p.exports[index - 1]['size']:
            continue
        cls = p.cls(index)
        try:
            native_fields.fields(p, index, end)
            (mapped if cls in native_fields.MAPPED else plain)[cls] += 1
        except native_fields.Unmapped:
            unmapped[cls] += 1
        except native_fields.NativeError as error:
            bad[cls] += 1
            if len(examples) < 4:
                examples.append(str(error))
    out.update(mapped=dict(mapped), plain=dict(plain), unmapped=dict(unmapped), badNative=dict(bad),
               badNativeExamples=examples)
    return Path(path).stem, out


def top_levels(path):
    """Top-level export names of an always-loaded package, with the classes under each."""
    p = Pack(path)
    out = collections.defaultdict(collections.Counter)
    for n in range(len(p.exps)):
        out[p.exps[p.top(n)]['name']][p.cls[n]] += 1
    return p.name, {top: dict(c) for top, c in out.items()}


def companion(job):
    """The objects a level imports that its _LOC_INT companion package holds."""
    level, loc = job
    L, C = Pack(level), Pack(loc)
    held = {C.full(n + 1): C.cls[n] for n in range(len(C.exps)) if C.cls[n] != 'Package'}
    hits = collections.Counter(held[L.full(-n - 1)] for n in range(len(L.imps)) if L.full(-n - 1) in held)
    return L.name, dict(companion=Path(loc).name, companionExports=dict(collections.Counter(C.cls)),
                        importsItHolds=dict(hits))


def shader_check(cache_path, windows):
    """Which base materials have 16 of their last bytes in the shader cache: {path: found}."""
    data, _ = load_any(cache_path)
    wanted = collections.defaultdict(set)
    for path_, hexes in windows.items():
        for h in hexes:
            wanted[bytes.fromhex(h)].add(path_)
    found = set()

    def scan(lo):
        for o in range(lo, len(data) - 15):
            hit = wanted.get(data[o:o + 16])
            if hit:
                found.update(hit)
    scan(max(0, len(data) - CACHE_TAIL))
    scanned = 'the last %d MB' % (CACHE_TAIL >> 20)
    if len(found) < len(windows):
        scan(0)
        scanned = 'all of it'
    return {path_: path_ in found for path_ in windows}, len(data), scanned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('install'); ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--no-pairs', action='store_true'); ap.add_argument('--no-shaders', action='store_true')
    ap.add_argument('--no-walk', action='store_true')
    a = ap.parse_args()
    game = Path(a.install) / 'XEW' / 'XComGame'
    cooked = game / 'CookedPCConsole'
    base, streams = set(), set()
    for line in (game / 'Config' / 'DefaultMaps.ini').read_bytes().decode('latin-1').splitlines():
        if line.lstrip().startswith(';'):
            continue
        base.update(re.findall(r'(?<![A-Za-z])Name="([^"]+)"', line))
        streams.update(re.findall(r'MapName="([^"]+)"', line))
    files = {p.stem.lower(): p for p in cooked.glob('*.upk')}
    base_low = {n.lower() for n in base}
    wanted = sorted(n for n in {x.lower() for x in base | streams} if n in files)
    with multiprocessing.get_context('spawn').Pool(a.jobs) as pool:
        found = dict(pool.imap_unordered(survey, [str(files[n]) for n in wanted], chunksize=2))
        holders = dict(pool.map(top_levels, [str(files[n.lower()]) for n in ALWAYS_LOADED if n.lower() in files]))
        firaxis_base = sorted((n for n, e in found.items() if e.get('licensee') == 64 and n.lower() in base_low),
                              key=str.lower)
        pairs = []
        if not a.no_pairs and len(firaxis_base) > 1:
            ring = [(str(files[x.lower()]), str(files[y.lower()]))
                    for x, y in zip(firaxis_base, firaxis_base[1:] + firaxis_base[:1])]
            pairs = list(pool.imap_unordered(compare, ring))
        locs = [(str(files[n[:-8]]), str(p)) for n, p in sorted(files.items())
                if n.endswith('_loc_int') and not n.endswith('_sf_loc_int') and n[:-8] in files
                and n[:-8] != 'startup']
        companions = dict(pool.map(companion, locs))
        walks = {}
        if not a.no_walk:
            walks = dict(pool.imap_unordered(walk, [str(files[n.lower()]) for n, e in found.items()
                                                    if e.get('licensee') == 64]))

    # the library
    where = collections.defaultdict(dict)       # (class, path) -> {package: size}, Firaxis-cooked packages
    modder = collections.Counter()
    packages, windows, texture_caches = {}, {}, {}
    for name in sorted(found, key=str.lower):
        e = found[name]
        role = 'base' if name.lower() in base_low else 'stream'
        if 'error' in e:
            packages[name] = dict(role=role, **e)
            continue
        counts = collections.Counter(cls for cls, _, _ in e['assets'])
        packages[name] = dict(role=role, licensee=e['licensee'], bytes=e['bytes'], exports=e['exports'],
                              shaderCaches=e['shaderCaches'], assets=sum(counts.values()),
                              staticMeshes=counts.get('StaticMesh', 0))
        if e['licensee'] == 64:
            for cls, path_, size in e['assets']:
                where[(cls, path_)][name] = size
            windows.update(e['materialWindows'])
            texture_caches.update(e['textureCaches'])
        else:
            modder.update(cls for cls, _, _ in e['assets'])
    by_class = collections.defaultdict(list)
    for (cls, path_), held in where.items():
        by_class[cls].append((path_, held))
    order = [c for c in LISTED if c in by_class] + sorted(c for c in by_class if c not in LISTED)
    library = {}
    for cls in order:
        rows = by_class[cls]
        library[cls] = dict(distinct=len(rows), inOnePackage=sum(1 for _, h in rows if len(h) == 1),
                            inTwoToFive=sum(1 for _, h in rows if 2 <= len(h) <= 5),
                            inMoreThanFive=sum(1 for _, h in rows if len(h) > 5),
                            bytes=sum(max(h.values()) for _, h in rows))
    varies = [dict(cls=cls, object=path_, sizes=sorted(set(h.values())), packages=len(h))
              for (cls, path_), h in sorted(where.items()) if len(set(h.values())) > 1]
    per_base = sorted(packages[n]['staticMeshes'] for n in firaxis_base)
    tops = collections.defaultdict(set)
    for (cls, path_), held in where.items():
        if cls in ('StaticMesh', 'FracturedStaticMesh', 'SkeletalMesh'):
            tops[path_.split('.')[0]].update(held)

    # imports from outside the map
    imported = collections.defaultdict(lambda: dict(packages=set(), classes=collections.Counter()))
    for name, e in found.items():
        if e.get('licensee') != 64:
            continue
        for top, classes in e['imports'].items():
            imported[top]['packages'].add(name)
            imported[top]['classes'].update(classes)
    imports = {}
    for top, row in sorted(imported.items(), key=lambda kv: -len(kv[1]['packages'])):
        home = [h for h, tops_ in holders.items() if top in tops_]
        imports[top] = dict(packagesImporting=len(row['packages']), classes=dict(row['classes'].most_common()),
                            isAFile=top.lower() in files, heldBy=home)

    summary = dict(
        packages=dict(named=len(base | streams), read=sum(1 for e in packages.values() if 'error' not in e),
                      firaxisBase=len(firaxis_base),
                      firaxisStreams=sum(1 for n, e in packages.items()
                                         if e.get('licensee') == 64 and e['role'] == 'stream'),
                      otherLicensee=sum(1 for e in packages.values() if e.get('licensee') not in (64, None)),
                      withShaderCacheExports=sum(1 for e in packages.values() if e.get('shaderCaches'))),
        library=library,
        staticMeshesPerBaseMap=dict(min=per_base[0], median=per_base[len(per_base) // 2], max=per_base[-1])
        if per_base else None,
        assetPackagesHoldingMeshes=len(tops),
        samePathDifferentSize=varies,
        otherLicenseeAssets=dict(modder.most_common(12)),
        bakedTextureCaches=dict(
            packages=sum(1 for e in found.values() if e.get('licensee') == 64 and e.get('bakedCaches')),
            textures=dict(sum((collections.Counter(e['bakedCaches']) for e in found.values()
                               if e.get('licensee') == 64), collections.Counter()).most_common()),
            otherLicensee=dict(sum((collections.Counter(e['bakedCaches']) for e in found.values()
                                    if e.get('licensee') not in (64, None)), collections.Counter()).most_common())),
        textureCaches=dict(collections.Counter(texture_caches.values()).most_common()),
        imports=imports, companions=companions)

    if pairs:
        rows, fields, odd = collections.defaultdict(collections.Counter), collections.Counter(), []
        entry_count, entry_examples = collections.Counter(), collections.defaultdict(list)
        native = collections.defaultdict(collections.Counter)
        for x, y, per_class, f, o, (counts, shown), per_native in pairs:
            for cls, row in per_class.items():
                rows[cls].update(row)
            fields.update(f)
            odd.extend(dict(pair=[x, y], **item) for item in o)
            entry_count.update(counts)
            for what, items in shown.items():
                entry_examples[what] += [dict(pair=[x, y], **item) for item in items]
            for cls, row in per_native.items():
                for k, v in row.items():
                    native[cls][k] = max(native[cls][k], v) if k.startswith('max') else native[cls][k] + v
        total = collections.Counter()
        for row in rows.values():
            total.update(row)
        kept, examples = collections.Counter(), []      # up to eight examples a class
        for item in sorted(odd, key=lambda d: (d['cls'], d['object'], d['pair'])):
            kept[item['cls']] += 1
            if kept[item['cls']] <= 8:
                examples.append(item)
        summary['sameObjectInTwoMaps'] = dict(
            pairs=len(pairs), total=dict(total), explainedFields=dict(fields),
            classes={cls: dict(rows[cls]) for cls in sorted(rows, key=lambda c: -rows[c]['objects'])},
            unexplainedOrSizeDiffers=examples)
        summary['entriesOfSharedObjects'] = dict(
            count=dict(sorted(entry_count.items())),
            differences={what: sorted(items, key=lambda d: (d['object'], d['pair']))[:8]
                         for what, items in sorted(entry_examples.items())})
        numbered = {cls: dict(row) for cls, row in native.items() if any(k.startswith('with') for k in row)}
        summary['fieldsBeyondProperties'] = dict(
            note='objects of the same size whose bytes differ; a field is a name, an object number or an offset that '
                 'means the same in both maps and lies after the closing None of the tagged properties',
            classesCompared=len(native), classesWithFields=len(numbered),
            classes={cls: numbered[cls] for cls in sorted(numbered, key=lambda c: -numbered[c]['compared'])},
            propertiesNotWalked={cls: row['propertiesNotWalked'] for cls, row in sorted(native.items())
                                 if row.get('propertiesNotWalked')})

    if walks:
        total = collections.Counter()
        tallies = {k: collections.Counter() for k in ('untyped', 'noClass', 'mapped', 'plain', 'unmapped', 'badNative')}
        failed, examples = [], []
        for name, w in sorted(walks.items()):
            for k in ('exports', 'names', 'objects'):
                total[k] += w[k]
            for k, tally in tallies.items():
                tally.update(w[k])
            failed += [dict(package=name, object=o, cls=c, why=why) for o, c, why in w['failed']]
            examples += w['badNativeExamples']
        summary['walk'] = dict(
            packages=len(walks), exports=total['exports'], nameFields=total['names'], objectFields=total['objects'],
            failed=failed[:40], failedCount=len(failed),
            untypedArrays=dict(tallies['untyped'].most_common()),
            classesNotInTheScriptPackages=dict(tallies['noClass'].most_common()),
            nativeData=dict(readByLayout=dict(tallies['mapped'].most_common()),
                            plain=dict(tallies['plain'].most_common()),
                            noLayout=dict(tallies['unmapped'].most_common()),
                            layoutFailed=dict(tallies['badNative'].most_common()), layoutFailedExamples=examples[:8]))

    if not a.no_shaders:
        cache = cooked / 'RefShaderCache-PC-D3D-SM3.upk'
        if cache.is_file():
            hits, size, scanned = shader_check(cache, windows)
            summary['shaders'] = dict(cache=cache.name, cacheBytes=size, scanned=scanned, baseMaterials=len(hits),
                                      found=sum(hits.values()), notFound=sorted(k for k, v in hits.items() if not v))
        else:
            summary['shaders'] = dict(error='no %s in the install' % cache.name)

    missing = sorted(n for n in base | streams if n.lower() not in files)
    Path(a.out).write_text(json.dumps(dict(
        scope='every base map and stream named by a live DefaultMaps.ini record; the library, the pairs and the '
              'shaders count Firaxis-cooked packages (licensee 64) only',
        missingPackages=missing, summary=summary, packages=packages), indent=1) + '\n',
        encoding='utf-8', newline='\n')
    print('%d packages read (%d Firaxis base maps), %d named but not found'
          % (summary['packages']['read'], len(firaxis_base), len(missing)))
    if pairs:
        t = summary['sameObjectInTwoMaps']['total']
        print('pairs: %d objects, %d identical, %d explained, %d unexplained, %d of another size'
              % tuple(t.get(k, 0) for k in ('objects', 'identical', 'explained', 'unexplained', 'sizeDiffers')))
    if walks:
        w = summary['walk']
        print('walk: %d exports of %d packages, %d failed, untyped arrays %s, %d native layouts failed'
              % (w['exports'], w['packages'], w['failedCount'], w['untypedArrays'],
                 sum(w['nativeData']['layoutFailed'].values())))
    if 'found' in summary.get('shaders', {}):
        print('shaders: %d of %d base materials found in the cache' % (summary['shaders']['found'],
                                                                      summary['shaders']['baseMaterials']))


if __name__ == '__main__':
    main()
