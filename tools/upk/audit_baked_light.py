"""A research tool (not shipped): stage B0 of the game-likeness plan, the maps' baked light as the game stores it,
surveyed over the install, and the atlases of one map exported ad hoc for the stage's spike.

  python -B tools/upk/audit_baked_light.py survey [--maps <map> ...] [--output <json>]
      per map: the static mesh components with lightmaps (texture, vertex, none) and with shadow maps, the atlases and
      shadow-map textures they read and their bytes (on disk, and as the GPU holds their blocks), each texture's
      format and whether it saves SRGB, the lights and which lightmaps and shadow maps name them, and what the
      components without a lightmap have in their place (hidden, no lights taken, a light environment, lights named
      irrelevant); and once, what the game's material shaders do with each (the light-map policies of one material's
      shader map, the constants of its lightmap and no-lightmap base passes)
  python -B tools/upk/audit_baked_light.py scale <map> <component> [--output <json>]
      one piece's lightmap worked both ways: the light the baker's relight.flat_light gives (the three direction
      values summed) and the light the game's shader gives a flat normal (each weighted by its basis vector's squared
      cosine, a third), texel by texel, with what a light of the codec's model stores (lightmap_encode)
  python -B tools/upk/audit_baked_light.py near <map> <x> <y> <z> [--radius 600]
      the lightmapped pieces whose box meets a sphere round a game point, brightest flat light first (to pick a piece)
  python -B tools/upk/audit_baked_light.py spike-export <map> --cache <scratch cache>
      the spike of B2 (flagged off on the page: ?baked=on): each lightmapped piece's record (its two atlases, their
      scales, its UV scale and bias and channel) and every atlas as the game stores it (a DDS of its DXT1 mips), written
      into the map's newest export in that cache as baked-light.json and lm-<index>.dds. Throwaway: B1 is the export.

Every package is read through the shipped readers (lighting_records.component_record for a component's lightmap,
shadowmaps.shadow_maps for its sun shadow maps, lightmap_fields.texture_fields for a texture's mips). Read only: the
install is never written. The maps default to every map the configured install's records name.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
for folder in ('viewer', 'bake', 'lab'):
    sys.path.insert(0, str(TOOLS / folder))
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402

import labpaths  # noqa: E402
import lighting_records  # noqa: E402
import lightmap_encode as codec  # noqa: E402
import lightmap_fields  # noqa: E402
import lightmap_texels  # noqa: E402
import lightmap_textures  # noqa: E402
from package import Package, FormatError, Reader  # noqa: E402
import shadowmaps  # noqa: E402

LIGHT_SUFFIX = 'LightComponent'
# the properties of a component that say how the game lights it when it has no lightmap (their defaults are the
# classes', which a package does not save: None here means "the class default")
UNLIT_KEYS = ('HiddenGame', 'bAcceptsLights', 'bAcceptsDynamicLights', 'bUsePrecomputedShadows', 'CastShadow',
              'LightEnvironment', 'bForceDirectLightMap', 'bAcceptsStaticDecals')
LIGHT_KEYS = ('LightAffectsClassification', 'bEnabled', 'CastShadow', 'UseDirectLightMap', 'bForceDynamicLight',
              'CastStaticShadows', 'CastDynamicShadows')
# The game's lightmap basis (section 0 of the implementation plan; lightmap_encode.BASIS): a flat tangent-space normal
# (0, 0, 1) meets each at cos 35.26 degrees, so each squared cosine is a third and the three sum to one.
FLAT_WEIGHTS = (codec.BASIS @ np.array([0.0, 0.0, 1.0])) ** 2
UNREADABLE = (FormatError, ValueError, IndexError, KeyError, OSError)


def guid_hex(raw):
    return bytes(raw).hex() if isinstance(raw, (bytes, bytearray)) and len(raw) == 16 else None


def level_exports(p):
    """The export indices of the persistent level's actors' components, by kind: static mesh components, skeletal
    mesh components, light components (each under an actor of TheWorld.PersistentLevel, archetypes left out)."""
    out = defaultdict(list)
    for i in range(1, len(p.exports) + 1):
        path = p.paths[i - 1]
        if not path.startswith('TheWorld.PersistentLevel.') or path.count('.') != 3 or 'Default__' in path:
            continue
        cls = p.cls(i)
        if 'StaticMeshComponent' in cls:
            out['static'].append(i)
        elif 'SkeletalMeshComponent' in cls:
            out['skeletal'].append(i)
        elif cls.endswith(LIGHT_SUFFIX):
            out['light'].append(i)
    return out


_DEFAULT_CHANNELS = {}


def light_channels(p, index):
    """The lighting channels a light lights, as names: its own LightingChannels where it saves them, else the
    LightComponent class default object's (Engine.upk of the package's folder: BSP, Static, Dynamic, CompositeDynamic).
    A piece is lit by a light only where their channels meet."""
    raw = p.own(index, 'LightingChannels')
    if raw is None:
        folder = p.path.parent
        if folder not in _DEFAULT_CHANNELS:
            engine = Package(folder / 'Engine.upk')
            raw = engine.own(engine.by_name['Default__LightComponent'], 'LightingChannels')
            _DEFAULT_CHANNELS[folder] = sorted(k[0] for k, v in engine.tagged(Reader(raw)).items()
                                               if v['value'] is True and k[0] != 'bInitialized')
        return _DEFAULT_CHANNELS[folder]
    return sorted(k[0] for k, v in p.tagged(Reader(raw)).items() if v['value'] is True and k[0] != 'bInitialized')


def texture_bytes(p, index):
    """A lighting texture's format, top size, live mips, bytes on disk (as stored, compressed or not) and as the GPU
    holds them (the blocks of each live mip), and its saved SRGB (None: not saved, the class default)."""
    t = lightmap_fields.texture_fields(p, index)
    live = [m for m in t['mips'] if m['bytes'] and not m['flags'] & 32]
    top = max(live, key=lambda m: m['width'] * m['height'])
    return dict(format=t['format'], size=[top['width'], top['height']], mips=len(live),
                disk=sum(m['bytes'] for m in live), gpu=sum(lightmap_textures.mip_bytes(t['format'], m['width'],
                                                                                        m['height']) for m in live),
                inline=all(m['inline'] for m in live), srgbSaved=p.own(index, 'SRGB'))


def component_light(p, ci):
    """A static mesh component's LOD 0 lighting: its lightmap record and its shadow maps (shadowmaps.shadow_maps for
    the classes it reads, else the record's own references)."""
    rec = lighting_records.component_record(p, ci)
    lod = rec['lods'][0] if rec['lods'] else None
    lm = lod['lightmap'] if lod else dict(type=0)
    if p.cls(ci) in lightmap_fields.COMPONENT_CLASSES:
        sms = shadowmaps.shadow_maps(p, ci)
    else:
        sms = [dict(export=r, texture=p.own(r, 'Texture'), guid=guid_hex(p.own(r, 'LightGuid')))
               for r in (lod['shadowMaps'] if lod else []) if r > 0]
    return lm, sms


def survey_map(p):
    exports = level_exports(p)
    comps = Counter()
    by_class = Counter()
    slots = Counter()
    shadow_mapped = 0
    unlit = Counter()
    unlit_owner = Counter()
    unlit_cls = Counter()
    atlas_users = Counter()
    shadow_textures = Counter()
    in_lightmaps = Counter()
    in_shadow_maps = Counter()
    errors = []
    for ci in exports['static']:
        by_class[p.cls(ci)] += 1
        try:
            lm, sms = component_light(p, ci)
        except UNREADABLE as error:
            errors.append([p.name(ci), str(error)[:100]])
            comps['unread'] += 1
            continue
        kind = {0: 'none', 1: 'vertex', 2: 'texture'}.get(lm['type'], str(lm['type']))
        comps[kind] += 1
        for g in lm.get('lightGuids') or []:
            in_lightmaps[g] += 1
        if lm['type'] == 2:
            # (EW's record has three slots: the colour, the directions, and a third that names no texture)
            slots['%d slots, %d with a texture' % (len(lm['slots']), sum(s['index'] > 0 for s in lm['slots']))] += 1
            for s in lm['slots']:
                if s['index'] > 0:
                    atlas_users[s['index']] += 1
        if sms:
            shadow_mapped += 1
        for sm in sms:
            if sm.get('texture'):
                shadow_textures[sm['texture']] += 1
            if sm.get('guid'):
                in_shadow_maps[sm['guid']] += 1
        if lm['type'] == 0:
            owner = p.exports[ci - 1]['outer']
            unlit_owner[p.cls(owner) if owner > 0 else '?'] += 1
            unlit_cls[p.cls(ci)] += 1
            values = {k: p.effective(ci, k, None) for k in UNLIT_KEYS}
            irrelevant = p.own(ci, 'IrrelevantLights')
            unlit['all'] += 1
            unlit['hidden in game'] += bool(values['HiddenGame'])
            unlit['takes no lights (bAcceptsLights False)'] += values['bAcceptsLights'] is False
            unlit['takes no dynamic lights (bAcceptsDynamicLights False)'] += values['bAcceptsDynamicLights'] is False
            unlit['has a light environment'] += bool(values['LightEnvironment'])
            unlit['names irrelevant lights'] += bool(irrelevant) and len(irrelevant) > 4
            unlit['has a sun shadow map'] += bool(sms)
            unlit['bUsePrecomputedShadows False (saved)'] += values['bUsePrecomputedShadows'] is False
            unlit['bUsePrecomputedShadows True (saved)'] += values['bUsePrecomputedShadows'] is True
            unlit['casts no shadow (saved)'] += values['CastShadow'] is False
            if not values['HiddenGame'] and values['bAcceptsLights'] is not False:
                unlit['drawn and lit'] += 1
    atlases = {}
    for k in sorted(atlas_users):
        try:
            atlases[k] = texture_bytes(p, k)
        except UNREADABLE as error:
            errors.append([p.name(k), str(error)[:100]])
    shadows = {}
    for k in sorted(shadow_textures):
        try:
            shadows[k] = texture_bytes(p, k)
        except UNREADABLE as error:
            errors.append([p.name(k), str(error)[:100]])
    lights = Counter()
    light_rows = []
    for li in exports['light']:
        guids = {guid_hex(p.own(li, 'LightGuid')), guid_hex(p.own(li, 'LightmapGuid'))} - {None}
        baked = sum(in_lightmaps[g] for g in guids)
        shadowed = sum(in_shadow_maps[g] for g in guids)
        values = {k: p.effective(li, k, None) for k in LIGHT_KEYS}
        channels = light_channels(p, li)
        key = (p.cls(li), values['LightAffectsClassification'] or 'default', bool(baked), bool(shadowed),
               'lights static pieces' if {'Static', 'BSP'} & set(channels) else 'channels ' + ' '.join(channels))
        lights[key] += 1
        if p.cls(li) not in ('PointLightComponent', 'SpotLightComponent') or not baked:
            light_rows.append(dict(light=p.name(li).split('.', 2)[-1], cls=p.cls(li), bakedInto=baked,
                                   shadowMaps=shadowed, channels=channels,
                                   **{k: v for k, v in values.items() if v is not None}))
    def summed(table):
        fmt = Counter((t['format'], tuple(t['size'])) for t in table.values())
        return dict(count=len(table), formats=dict(Counter(t['format'] for t in table.values())),
                    srgbSaved=dict(Counter(str(t['srgbSaved']) for t in table.values())),
                    sizes=[[f, list(s), n] for (f, s), n in fmt.most_common(8)],
                    diskBytes=sum(t['disk'] for t in table.values()), gpuBytes=sum(t['gpu'] for t in table.values()),
                    insideTheMap=sum(t['inline'] for t in table.values()))
    return dict(staticComponents=len(exports['static']), skeletalComponents=len(exports['skeletal']),
                byClass=dict(by_class), lightmaps=dict(comps), lightmapSlots=dict(slots),
                shadowMapped=shadow_mapped, atlases=summed(atlases), shadowMapTextures=summed(shadows),
                atlasUsers=dict(Counter(min(n, 99) for n in atlas_users.values()).most_common(6)),
                noLightmap=dict(unlit), noLightmapOwners=dict(unlit_owner.most_common(12)),
                noLightmapClasses=dict(unlit_cls), lights=[[*k, n] for k, n in lights.most_common()],
                lightsNotBakedOrNotLocal=light_rows[:40], errors=errors[:20])


def texture_defaults(cooked):
    """What a lighting texture's SRGB is when it saves none: the Texture class's default object (Engine.upk), and
    whether LightMapTexture2D has a script class of its own (none: an intrinsic class, Texture2D's defaults)."""
    p = Package(cooked / 'Engine.upk')
    out = {}
    for name in ('Default__Texture', 'Default__Texture2D', 'Default__LightMapTexture2D', 'Default__ShadowMapTexture2D'):
        index = p.by_name.get(name)
        out[name] = None if index is None else {k: p.own(index, k) for k in ('SRGB', 'LODGroup', 'Filter')}
    out['LightMapTexture2D class in Engine.upk'] = 'LightMapTexture2D' in p.by_name
    out['ShadowMapTexture2D class in Engine.upk'] = 'ShadowMapTexture2D' in p.by_name
    return out


def shader_policies(cooked, material='ENV_ForestGround'):
    """One material's shader map as the game compiled it for static meshes (FLocalVertexFactory): its shader types
    (the light-map policies and the light passes), and the constants each base pass reads."""
    import shader_cache
    c = shader_cache.open_cache(cooked / shader_cache.FILE_NAME)
    for m in c.maps:
        try:
            name = c.name(m)
        except UNREADABLE:
            continue
        if name.rsplit('.', 1)[-1].lower() != material.lower():
            continue
        refs = c.shader_refs(m).get('FLocalVertexFactory', {})
        passes = {}
        for kind, sid in sorted(refs.items()):
            if kind.startswith('TBasePassPixelShader') and 'WithoutTranslucentFOW' in kind:
                sh = c.shader(sid)
                passes[kind] = sorted(sh.constants, key=lambda n: (sh.constants[n].set, sh.constants[n].index))
        return dict(material=name, shaderTypes=sorted(refs), basePassConstants=passes)
    return None


def survey(paths, cooked):
    maps, failed = {}, []
    began = time.time()
    for path in paths:
        try:
            p = Package(path)
        except UNREADABLE as error:
            failed.append([path.name, str(error)[:100]])
            continue
        maps[path.stem] = survey_map(p)
        m = maps[path.stem]
        print('%-28s %5d static: %5d texture, %4d vertex, %4d none; %4d shadow-mapped; %3d atlases %6.1f MB GPU'
              % (path.stem, m['staticComponents'], m['lightmaps'].get('texture', 0), m['lightmaps'].get('vertex', 0),
                 m['lightmaps'].get('none', 0), m['shadowMapped'], m['atlases']['count'],
                 m['atlases']['gpuBytes'] / 1048576), flush=True)
    total = Counter()
    formats, srgb, slots, unlit = Counter(), Counter(), Counter(), Counter()
    for m in maps.values():
        for k, v in m['lightmaps'].items():
            total[k] += v
        total['shadowMapped'] += m['shadowMapped']
        total['static'] += m['staticComponents']
        total['atlases'] += m['atlases']['count']
        total['atlasGpuBytes'] += m['atlases']['gpuBytes']
        total['atlasDiskBytes'] += m['atlases']['diskBytes']
        total['shadowTextures'] += m['shadowMapTextures']['count']
        total['shadowGpuBytes'] += m['shadowMapTextures']['gpuBytes']
        formats.update(m['atlases']['formats'])
        srgb.update(m['atlases']['srgbSaved'])
        slots.update(m['lightmapSlots'])
        unlit.update(m['noLightmap'])
    return dict(date=time.strftime('%Y-%m-%d'), seconds=round(time.time() - began, 1), packages=len(paths),
                failed=failed, totals=dict(total), atlasFormats=dict(formats), atlasSrgbSaved=dict(srgb),
                lightmapSlots=dict(slots), noLightmap=dict(unlit), textureDefaults=texture_defaults(cooked),
                shaderPolicies=shader_policies(cooked), maps=maps)


# ---------------------------------------------------------------------------------------------------------------
# The direction values' scale, on one piece

def directional(lm):
    """Whether a lightmap record is a directional lightmap texture: its colour and direction slots name textures."""
    return lm['type'] == 2 and len(lm['slots']) >= 2 and all(s['index'] > 0 for s in lm['slots'][:2])


def piece_texels(p, ci):
    """A lightmapped piece's texels in its rectangle of its atlases: the stored colour and direction values (0-1, the
    DXT1 decode), the record's two slot scales, and the texels' world frames (lightmap_texels.rasterise)."""
    lm, _ = component_light(p, ci)
    if not directional(lm):
        raise ValueError('%s has no directional lightmap texture' % p.name(ci))
    (nac_i, s0), (dmc_i, s1) = [(s['index'], s['scale']) for s in lm['slots'][:2]]
    raw, w, h = lightmap_textures.top_mip_raw(p, nac_i)
    mesh = lightmap_texels.component_mesh(p, ci)
    geo = lightmap_texels.rasterise(mesh, lightmap_texels.world_matrix(p, ci), lm, [w, h])
    nac = lightmap_textures.top_mip_rgb(p, nac_i)[geo['py'], geo['px']]
    dmc = lightmap_textures.top_mip_rgb(p, dmc_i)[geo['py'], geo['px']]
    return lm, np.array(s0[:3], float), np.array(s1[:3], float), nac, dmc, geo, (w, h)


def worked_scale(p, ci):
    lm, s0, s1, nac, dmc, geo, size = piece_texels(p, ci)
    colour = nac ** codec.GAMMA * s0                              # the colour atlas read linear, times its scale
    srgb = np.where(nac <= 0.04045, nac / 12.92, ((nac + 0.055) / 1.055) ** 2.4) * s0     # the GPU's sRGB curve
    directions = dmc ** codec.GAMMA * s1                          # each direction value read linear, times its scale
    summed = colour * directions.sum(1, keepdims=True)            # relight.flat_light
    shader = colour * (directions @ FLAT_WEIGHTS)[:, None]        # the game's shader, flat normal
    luminance = np.array([0.2126, 0.7152, 0.0722])
    lit = (summed @ luminance) > 0.02
    top = int(np.argmax(summed @ luminance))
    up = geo['frames'][:, 2, 2]

    def stats(v):
        y = v @ luminance
        return dict(median=round(float(np.median(y[lit])), 4) if lit.any() else None,
                    p95=round(float(np.percentile(y[lit], 95)), 4) if lit.any() else None,
                    max=round(float(y.max()), 4))
    # what a light of the codec's model stores for a texel lit from straight above, both ways, against UE3's dynamic
    # light pass (saturate(N.L) times the light's colour and attenuation: one for a light overhead)
    overhead = codec.elevation_term(np.array([1.0]), np.array([0.0]))[0] * (codec.BASIS @ np.array([0, 0, 1.0]))
    return dict(map=p.path.stem, component=p.name(ci), atlas=size, rect=list(geo['rect']), texels=int(len(nac)),
                litTexels=int(lit.sum()), facesUp=round(float(np.mean(up > 0.9)), 3),
                slotScales=dict(colour=[round(float(v), 5) for v in s0], directions=[round(float(v), 5) for v in s1]),
                flatWeights=[round(float(v), 5) for v in FLAT_WEIGHTS],
                summedThree=stats(summed), shaderFlat=stats(shader), ratio=round(float(np.median(
                    (summed @ luminance)[lit] / np.maximum((shader @ luminance)[lit], 1e-9))), 4) if lit.any() else None,
                srgbCurveOverPower=round(float(np.median((srgb @ luminance)[lit] / np.maximum((colour @ luminance)[lit],
                                                                                          1e-9))), 4) if lit.any() else None,
                brightestTexel=dict(world=[round(float(v), 1) for v in geo['world'][top]],
                                    storedColour=[round(float(v), 4) for v in nac[top]],
                                    storedDirections=[round(float(v), 4) for v in dmc[top]],
                                    summedThree=[round(float(v), 4) for v in summed[top]],
                                    shaderFlat=[round(float(v), 4) for v in shader[top]]),
                codecOverhead=dict(storedEach=[round(float(v), 4) for v in overhead],
                                   summedThree=round(float(overhead.sum()), 4),
                                   shaderFlat=round(float(overhead @ FLAT_WEIGHTS), 4), dynamicPass=1.0))


def near(p, point, radius):
    out = []
    point = np.array(point, float)
    for ci in level_exports(p)['static']:
        try:
            lm, _ = component_light(p, ci)
            if not directional(lm):
                continue
            mesh = lightmap_texels.component_mesh(p, ci)
            m = lightmap_texels.world_matrix(p, ci)
            world = mesh['positions'] @ m[:3, :3].T + m[:3, 3]
        except UNREADABLE:
            continue
        lo, hi = world.min(0), world.max(0)
        gap = np.maximum(0, np.maximum(lo - point, point - hi))
        if math.sqrt(float((gap ** 2).sum())) > radius:
            continue
        try:
            s = worked_scale(p, ci)
        except UNREADABLE:
            continue
        out.append((s['summedThree']['p95'] or 0, s['component'], s['texels'], s['facesUp'], [round(float(v)) for v in lo],
                    [round(float(v)) for v in hi]))
    out.sort(reverse=True)
    return out


# ---------------------------------------------------------------------------------------------------------------
# The spike's export (throwaway: B1 is the export)

def newest_export(folder):
    found = [g for g in Path(folder).glob('*-map') if (g / 'scene.json').exists()]
    if not found:
        return None
    return max(found, key=lambda g: g.stat().st_mtime)


def spike_export(p, cache):
    import texture
    target = newest_export(Path(cache) / p.path.stem)
    if target is None:
        raise SystemExit('no export of %s in %s: open the map once on a test server with that cache' % (p.path.stem, cache))
    scene = json.loads((target / 'scene.json').read_text(encoding='utf-8'))
    textures, objects, skipped = {}, {}, Counter()
    for obj in scene['objects']:
        actor, component = obj['id'].split(':')
        if not actor.isdigit():
            skipped['not the map\'s own'] += 1
            continue
        ci = int(component)
        if 'StaticMeshComponent' not in p.cls(ci):
            skipped[p.cls(ci)] += 1
            continue
        try:
            lm, sms = component_light(p, ci)
        except UNREADABLE:
            skipped['record not read'] += 1
            continue
        if not directional(lm):
            skipped[{0: 'no lightmap', 1: 'vertex lightmap'}.get(lm['type'], 'other lightmap')] += 1
            continue
        mi = p.effective(ci, 'StaticMesh', 0)
        channel = p.effective(mi, 'LightMapCoordinateIndex', 0) if mi > 0 else 0
        keys = []
        for s in lm['slots'][:2]:
            key = 'lm-%d' % s['index']
            if key not in textures:
                info = texture.export_texture(p, s['index'], target / (key + '.png'), 'auto')
                info['url'] = info.pop('output')
                textures[key] = info
            keys.append(key)
        objects[obj['id']] = dict(colour=keys[0], directions=keys[1], scale0=lm['slots'][0]['scale'],
                                  scale1=lm['slots'][1]['scale'], uvScale=lm['coordinateScale'],
                                  uvBias=lm['coordinateBias'], channel=channel, lights=len(lm['lightGuids']),
                                  shadowMaps=len(sms))
    # whether the map's sky light lights its static pieces at all: on every map it lights the Gameplay_1 channel only
    skies = [light_channels(p, i) for i in level_exports(p)['light'] if p.cls(i) == 'SkyLightComponent']
    out = dict(spike='B0', map=p.path.stem, source=str(p.path.name), textures=textures, objects=objects,
               skyOnStatic=any({'Static', 'BSP'} & set(c) for c in skies), skipped=dict(skipped))
    (target / 'baked-light.json').write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
    print('%s: %d lightmapped pieces, %d atlases into %s; skipped %s' % (p.path.stem, len(objects), len(textures),
                                                                       target, dict(skipped)))


def map_paths(names):
    cooked = labpaths.lwr_cooked()
    if cooked is None:
        raise SystemExit('no CookedPCConsole: set XCOM_COOKED or the settings (python tools/viewer/viewer.py settings)')
    if names:
        return cooked, [cooked / ('%s.upk' % n) for n in names]
    import maplist
    found = maplist.lwr_maps(labpaths.lwr_game())
    return cooked, sorted({e['package'] for e in found.values() if e['package']}, key=lambda q: q.stem.lower())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    s = sub.add_parser('survey')
    s.add_argument('--maps', nargs='*')
    s.add_argument('--output', type=Path)
    w = sub.add_parser('scale')
    w.add_argument('map')
    w.add_argument('component')
    w.add_argument('--output', type=Path)
    n = sub.add_parser('near')
    n.add_argument('map')
    n.add_argument('point', nargs=3, type=float)
    n.add_argument('--radius', type=float, default=600)
    e = sub.add_parser('spike-export')
    e.add_argument('map')
    e.add_argument('--cache', required=True)
    args = ap.parse_args(argv)
    if args.command == 'survey':
        cooked, paths = map_paths(args.maps)
        got = survey(paths, cooked)
        print(json.dumps(dict(totals=got['totals'], formats=got['atlasFormats'], srgbSaved=got['atlasSrgbSaved'],
                              slots=got['lightmapSlots'], noLightmap=got['noLightmap']), indent=1))
        if args.output:
            args.output.write_text(json.dumps(got, indent=1) + '\n', encoding='utf-8', newline='\n')
        return 0
    cooked, (path,) = map_paths([args.map])
    p = Package(path)
    if args.command == 'scale':
        got = worked_scale(p, p.by_name[args.component] if args.component in p.by_name
                           else p.by_name['TheWorld.PersistentLevel.' + args.component])
        print(json.dumps(got, indent=1))
        if args.output:
            args.output.write_text(json.dumps(got, indent=1) + '\n', encoding='utf-8', newline='\n')
    elif args.command == 'near':
        for row in near(p, args.point, args.radius)[:25]:
            print(row)
    elif args.command == 'spike-export':
        spike_export(p, args.cache)
    return 0


if __name__ == '__main__':
    sys.exit(main())
