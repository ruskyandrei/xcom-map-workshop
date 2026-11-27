"""A research tool (not shipped): the sun, the moon and the time of day across the install's maps, for stage T-S0 of
the game-likeness plan (the sun plan's step S0). It reads through the readers the Build uses (lighting_records.py,
and props.tags through the viewer's Package), the editor's atmosphere reader (tools/viewer/atmosphere.py) and, for
`trace` and `write-back`, the baker's own code; it writes nothing into the install.

  python -B tools/upk/audit_suns.py maps [--game <install>] [--out <json>] [--jobs N] [--only MAP ...]
  python -B tools/upk/audit_suns.py trace [--game <install>] [--map URB_Bar] [--jobs N] [--out <json>]
  python -B tools/upk/audit_suns.py level-map [--game <install>] [--map URB_Bar] [--out <json>]
  python -B tools/upk/audit_suns.py write-back --scratch <folder> [--game <install>] [--map URB_Bar] [--out <json>]

maps: every base map the editor lists (library.donors' base maps), each with
- its dominant directional light, the sun or moon: its height over the horizon, its yaw, colour, brightness, the
  shadow maps of it on the map's pieces (distance fields and shadow factors, the texels in their rectangles) and its
  own shadow map of the level (lighting_records.dominant_shadow_map: its size and the light-space box it covers);
- the other directional lights, the sky lights (upper and lower colour and brightness);
- the sky domes: the pieces whose mesh is one of the Skybox package's, with their materials;
- the TimeOfDay of each DefaultMaps.ini record naming it;
- its lighting samples for moving things and how many the dominant light does not reach (lighting_records.light_volume);
- its atmosphere (atmosphere.read): the height fog's colours and values, the grade and bloom, and the post-process
  volumes with the members of the grade each sets;
- a kind read from its light (kind_of): moon, dim, sunset, low sun or day.

trace: every dominant-light shadow map of the map traced from nothing, as the relight traces a piece of another map
(shadowmaps.fresh_shadow_map: 4 x 4 sub-samples a texel, one ray each toward the light, then the distance field), on
the relight's own workers (relight.run_jobs, each worker opening the map and building the scenes before and after an
edit, as a Build's relight does). Counted: the components, atlases, texels and rays; timed: the scenes a worker
builds first, the tracing, and the whole.

level-map: the dominant light's own shadow map of the level held against the map's geometry: a ray from each texel's
centre on the importance bounds' near face along the light, its hit's depth beside the stored one, in three layouts.

write-back: the lighting samples' marks written into a scratch copy of the map through package_edit.write_edited
(every mark flipped), read back, and written back as they were; and the light writer (native_lights.set_property)
tried on the dominant light's component in a growing copy (package_grow.Grower), from the start native_lights'
props_start gives and from the start past the leading shadow map, then read back.

Each command puts its part into the evidence file (--out, default research/evidence/sun-audit-2026-11-27.json) and
keeps the others' parts.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import struct
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
paths.use('upk', 'viewer')
import lighting_records as lighting  # noqa: E402
import settings  # noqa: E402

OUT = REPO / 'research' / 'evidence' / 'sun-audit-2026-11-27.json'
PL = 'TheWorld.PersistentLevel.'
SKY_MESH = 'Skybox.'
FOG_KEYS = ('bEnabled', 'FogDensity', 'FogHeight', 'FogHeightFalloff', 'FogMaxOpacity', 'StartDistance',
            'LightInscatteringColor', 'LightInscatteringBrightness', 'OppositeLightColor', 'OppositeLightBrightness',
            'LightTerminatorAngle')
GRADE_KEYS = ('bEnableSceneEffect', 'Scene_Shadows', 'Scene_HighLights', 'Scene_MidTones', 'Scene_Desaturation',
              'Scene_Colorize', 'Scene_TonemapperScale', 'bEnableBloom', 'Bloom_Scale', 'Bloom_Threshold',
              'Bloom_Tint', 'Bloom_ScreenBlendThreshold')
LIGHT_FLAGS = ('bEnabled', 'CastShadows', 'CastStaticShadows', 'CastDynamicShadows', 'bCastCompositeShadow',
               'UseDirectLightMap', 'LightingChannels')
# the relight's scenes as a Build's relight makes them (relight.py's defaults)
SCENE_ARGS = dict(samples=64, bounce_rays=64, stride=2, emissive=True, source_radius=None)


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def byte_colour(value):
    """A Color the package gives as 0-1 floats (R, G, B, A), as 0-255 R, G, B."""
    return [round(v * 255) for v in value[:3]] if value else None


def guid(raw):
    return bytes(raw).hex() if isinstance(raw, (bytes, bytearray)) else None


def install(args):
    game = args.game or settings.game_install(settings.load_settings())[0]
    if game is None:
        sys.exit('no game install: give --game, or set it (python tools/viewer/viewer.py settings --game <folder>)')
    return Path(game)


def map_path(game, name):
    for folder in settings.cooked_folders(game):
        if (folder / (name + '.upk')).is_file():
            return folder / (name + '.upk')
    sys.exit(f'no {name}.upk in {game}')


def update_evidence(out, key, value):
    data = json.loads(out.read_text(encoding='utf-8')) if out.is_file() else {}
    data[key] = value
    data['tool'] = 'tools/upk/audit_suns.py'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')


# --------------------------------------------------------------------------------------------------------- maps

def records(game):
    """{map name, lower case: [(mission, TimeOfDay)]} of the DefaultMaps.ini records the editor lists."""
    import installs
    import maplist
    import mapsini
    out = defaultdict(list)
    for line in maplist.records(installs.maps_text(game)):
        name = mapsini.field(line, 'Name')
        if name:
            out[name.lower()].append((mapsini.unquoted(line, 'MissionType'), mapsini.unquoted(line, 'TimeOfDay')))
    return out


def height_and_yaw(rotation):
    """(degrees over the horizon the light comes from, its yaw in degrees, the unit vector toward the light)."""
    from export_math import forward
    f = forward(rotation)
    return (round(math.degrees(math.asin(max(-1.0, min(1.0, -f[2])))), 2), round(rotation[1] * 360 / 65536 % 360, 2),
            [round(-v, 5) for v in f])


def light_entry(p, ci):
    actor = p.exports[ci - 1]['outer']
    rotation = p.effective(actor, 'Rotation', [-16384, 0, 0])
    height, yaw, to_light = height_and_yaw(rotation)
    return dict(component=p.name(ci)[len(PL):], cls=p.cls(ci), actorClass=p.cls(actor), rotation=rotation,
                height=height, yaw=yaw, toLight=to_light, colour=byte_colour(p.effective(ci, 'LightColor', [1, 1, 1, 1])),
                brightness=round(float(p.effective(ci, 'Brightness', 1.0)), 4),
                enabled=bool(p.effective(ci, 'bEnabled', True)), guid=guid(p.own(ci, 'LightGuid')),
                saved=lighting.explicit_properties(p, ci, LIGHT_FLAGS))


def level_map(p, ci):
    """The dominant light's own shadow map of the level, summed up."""
    m = lighting.dominant_shadow_map(p, ci)
    out = dict(sizeX=m['sizeX'], sizeY=m['sizeY'], depths=len(m['depths']))
    if m['bounds']:
        out['bounds'] = [round(v, 1) for v in m['bounds']]
    if m['bounds'] and m['depths']:
        b = m['bounds']
        out.update(unitsPerTexel=[round((b[3] - b[0]) / m['sizeX'], 2), round((b[4] - b[1]) / m['sizeY'], 2)],
                   depthRange=[min(m['depths']), max(m['depths'])])
    return out


def piece_shadow_maps(p, guids):
    """{light guid: counts} of the shadow maps the persistent level's mesh components hold, by the light they are of:
    components, maps (distance fields and shadow factors), those on components naming no mesh, atlases and the texels
    in their rectangles."""
    counts = defaultdict(Counter)
    atlases = defaultdict(set)
    sizes = {}
    errors = []
    for i in range(1, len(p.exports) + 1):
        if not p.cls(i).endswith('StaticMeshComponent') or not p.name(i).startswith(PL):
            continue
        try:
            record = lighting.component_record(p, i)
        except (ValueError, struct.error) as error:
            errors.append(f'{p.name(i)}: {error}')
            continue
        lods = record['lods']
        refs = [r for r in (lods[0]['shadowMaps'] if lods else []) if r > 0]
        lights_here = set()
        for ref in refs:
            light = guid(p.own(ref, 'LightGuid'))
            c = counts[light]
            factor = bool(p.own(ref, 'bIsShadowFactorTexture', False))
            c['shadowFactors' if factor else 'distanceFields'] += 1
            if p.effective(i, 'StaticMesh', 0) <= 0:
                c['onComponentsWithoutMesh'] += 1
                continue
            texture = p.own(ref, 'Texture')
            scale = struct.unpack('<2f', bytes(p.own(ref, 'CoordinateScale')))
            if texture not in sizes:
                top = lighting.texture_record(p, texture)['largestMip']
                sizes[texture] = (top['width'], top['height']) if top else (0, 0)
            w, h = sizes[texture]
            c['texels'] += round(scale[0] * w) * round(scale[1] * h)
            atlases[light].add(texture)
            lights_here.add(light)
        for light in lights_here:
            counts[light]['components'] += 1
    out = {g: dict(c, atlases=len(atlases[g])) for g, c in counts.items()}
    return out, errors[:5]


def sky_domes(p):
    out = []
    for i in range(1, len(p.exports) + 1):
        if 'MeshComponent' not in p.cls(i) or not p.name(i).startswith(PL):
            continue
        mesh = p.effective(i, 'StaticMesh', 0)
        if not mesh or not p.name(mesh).startswith(SKY_MESH):
            continue
        actor = p.exports[i - 1]['outer']
        materials = [p.name(m) if m else None for m in p.refs(p.effective(i, 'Materials'))]
        out.append(dict(actor=p.name(actor)[len(PL):], mesh=p.name(mesh), materials=materials,
                        hidden=bool(p.effective(actor, 'bHidden', False) or p.effective(i, 'HiddenGame', False)),
                        scale=p.effective(actor, 'DrawScale', 1.0)))
    return out


def atmosphere_entry(p):
    import atmosphere
    a = atmosphere.read(p)
    if a is None:
        return None
    world = a['world']
    volumes = []
    for v in a['volumes']:
        sets = sorted(k for k in v['settings'] if k in GRADE_KEYS or k in FOG_KEYS or k.startswith('XComFOW')
                      or k in ('XComFogOfWarColor',))
        overrides = sorted(k[len('bOverride_'):] for k, on in v['settings'].items() if k.startswith('bOverride_') and on)
        volumes.append(dict(name=v['name'], priority=v['priority'], enabled=v['enabled'], unbound=v['unbound'],
                            box=v['box'], saves=sets, overrides=overrides,
                            grade={k: v['settings'][k] for k in GRADE_KEYS if k in v['settings']}))
    return dict(fog={k: world['fog'].get(k) for k in FOG_KEYS}, fogSaved=world['saved']['fog'],
                grade={k: world['postProcess'].get(k) for k in GRADE_KEYS},
                gradeSaved=[k for k in world['saved']['postProcess'] if k in GRADE_KEYS],
                environmentColor=world['environmentColor'], volumes=volumes)


def kind_of(light):
    """What the dominant light's colour and height read as: moon (bluer than red), dim (no channel past 159 once
    times its brightness: a night lit by fires or a glow), sunset (orange, under 13 degrees), low sun (orange) or day;
    None with no dominant light. A reading of the light only: the records' TimeOfDay is the game's own word."""
    if light is None:
        return None
    r, g, b = light['colour']
    if b > r:
        return 'moon'
    if max(r, g, b) * light['brightness'] < 160:
        return 'dim'
    if g < 0.75 * r:
        return 'sunset' if light['height'] < 13 else 'low sun'
    return 'day'


def survey(job):
    name, path, recs = job
    out = dict(map=name, file=Path(path).name, size=Path(path).stat().st_size, sha256=sha256(path),
               records=[dict(mission=m, timeOfDay=t) for m, t in recs], errors=[])
    try:
        p = lighting.Package(path)
    except (ValueError, OSError) as error:
        out['errors'].append(f'open: {error}')
        return out
    dominant, others, skies = [], [], []
    for i in range(1, len(p.exports) + 1):
        cls = p.cls(i)
        if not p.name(i).startswith(PL):
            continue
        try:
            if cls == 'DominantDirectionalLightComponent':
                entry = light_entry(p, i)
                entry['levelMap'] = level_map(p, i)
                dominant.append(entry)
            elif cls.endswith('DirectionalLightComponent'):
                others.append(light_entry(p, i))
            elif cls == 'SkyLightComponent':
                skies.append(dict(component=p.name(i)[len(PL):],
                                  colour=byte_colour(p.effective(i, 'LightColor', [1, 1, 1, 1])),
                                  brightness=round(float(p.effective(i, 'Brightness', 1.0)), 4),
                                  lowerColour=byte_colour(p.effective(i, 'LowerColor', [1, 1, 1, 1])),
                                  lowerBrightness=round(float(p.effective(i, 'LowerBrightness', 0.0)), 4),
                                  enabled=bool(p.effective(i, 'bEnabled', True))))
        except (ValueError, struct.error) as error:
            out['errors'].append(f'{p.name(i)}: {error}')
    try:
        maps, errors = piece_shadow_maps(p, {d['guid'] for d in dominant})
        out['errors'] += errors
    except (ValueError, struct.error) as error:
        maps = {}
        out['errors'].append(f'shadow maps: {error}')
    for d in dominant:
        d['pieceShadowMaps'] = maps.get(d['guid'], {})
    out['otherLightsShadowMaps'] = {g: c for g, c in maps.items() if g not in {d['guid'] for d in dominant}}
    out.update(dominant=dominant, otherDirectional=others, skyLights=skies)
    try:
        out['skyDomes'] = sky_domes(p)
    except (ValueError, struct.error) as error:
        out['skyDomes'] = []
        out['errors'].append(f'sky domes: {error}')
    level = next((i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'Level' and p.name(i) == PL[:-1]), None)
    try:
        v = lighting.light_volume(p, level)
        out['samples'] = dict(count=len(v['samples']), notReached=sum(s[-1] for s in v['samples']),
                              spacing=round(v['spacing'], 2))
    except (ValueError, struct.error, TypeError) as error:
        out['samples'] = None
        out['errors'].append(f'lighting samples: {error}')
    try:
        out['atmosphere'] = atmosphere_entry(p)
    except (ValueError, struct.error) as error:
        out['atmosphere'] = None
        out['errors'].append(f'atmosphere: {error}')
    main = max(dominant, key=lambda d: d['brightness']) if dominant else None
    out['kind'] = kind_of(main)
    return out


def summary(maps):
    """The headline counts and the table's rows."""
    kinds = Counter(m['kind'] or 'no dominant light' for m in maps)
    times = Counter(t['timeOfDay'] for m in maps for t in m['records'])
    by_map_time = Counter(tuple(sorted({t['timeOfDay'] for t in m['records']})) for m in maps)
    disagree = []
    for m in maps:
        said = {t['timeOfDay'] for t in m['records']}
        if m['kind'] in ('moon', 'dim') and 'eMissionTime_Day' in said or m['kind'] in ('day', 'low sun', 'sunset') \
                and 'eMissionTime_Night' in said:
            disagree.append(dict(map=m['map'], kind=m['kind'], records=sorted(said)))
    rows = []
    for m in maps:
        d = max(m['dominant'], key=lambda x: x['brightness']) if m['dominant'] else None
        a = m['atmosphere'] or {}
        fog, grade = a.get('fog') or {}, a.get('grade') or {}
        rows.append(dict(
            map=m['map'], kind=m['kind'], records=dict(Counter(t['timeOfDay'] for t in m['records'])),
            light=None if d is None else dict(colour=d['colour'], brightness=d['brightness'], height=d['height'],
                                              yaw=d['yaw'], levelMap=[d['levelMap']['sizeX'], d['levelMap']['sizeY']],
                                              pieces=d['pieceShadowMaps'].get('components', 0),
                                              texels=d['pieceShadowMaps'].get('texels', 0)),
            dominantLights=len(m['dominant']), otherDirectional=len(m['otherDirectional']),
            sky=[dict(colour=s['colour'], brightness=s['brightness'], lower=s['lowerColour'],
                      lowerBrightness=s['lowerBrightness']) for s in m['skyLights']],
            domes=sorted({(s['materials'][0] if s['materials'] else None) or s['mesh'] for s in m['skyDomes']},
                         key=str),
            fog=None if not fog else dict(enabled=fog.get('bEnabled'), density=fog.get('FogDensity'),
                                          height=fog.get('FogHeight'),
                                          inscattering=byte_colour(fog.get('LightInscatteringColor')),
                                          inscatteringBrightness=fog.get('LightInscatteringBrightness'),
                                          opposite=byte_colour(fog.get('OppositeLightColor')),
                                          oppositeBrightness=fog.get('OppositeLightBrightness'),
                                          maxOpacity=fog.get('FogMaxOpacity')),
            grade=None if not grade else dict(enabled=grade.get('bEnableSceneEffect'),
                                              shadows=grade.get('Scene_Shadows'),
                                              highlights=grade.get('Scene_HighLights'),
                                              midtones=grade.get('Scene_MidTones'),
                                              desaturation=grade.get('Scene_Desaturation'),
                                              colorize=grade.get('Scene_Colorize'),
                                              bloomScale=grade.get('Bloom_Scale')),
            gradeVolumes=[v['name'] for v in a.get('volumes', []) if v['enabled'] and v['grade']],
            samples=m['samples']))
    domes = Counter(d for r in rows for d in r['domes'])
    return dict(maps=len(maps), kinds=dict(kinds), recordTimes=dict(times),
                mapsByRecordTimes={'+'.join(k) or '(no record)': v for k, v in by_map_time.items()},
                kindAgainstRecords=disagree,
                withSkyLight=sorted(m['map'] for m in maps if m['skyLights']),
                withoutSkyLight=sorted(m['map'] for m in maps if not m['skyLights']),
                withoutDominantLight=sorted(m['map'] for m in maps if not m['dominant']),
                withSeveralDominantLights=sorted(m['map'] for m in maps if len(m['dominant']) > 1),
                withOtherDirectional=sorted(m['map'] for m in maps if m['otherDirectional']),
                withSkyDome=len([m for m in maps if m['skyDomes']]),
                withoutSkyDome=sorted(m['map'] for m in maps if not m['skyDomes']),
                domeMaterials=dict(domes.most_common()),
                fogOn=sorted(m['map'] for m in maps if (m['atmosphere'] or {}).get('fog', {}).get('bEnabled')),
                gradeVolumeMaps=sorted(r['map'] for r in rows if r['gradeVolumes']),
                maxHeight=max((r['light']['height'] for r in rows if r['light']), default=None),
                sunHeights={r['map']: r['light']['height'] for r in rows if r['kind'] in ('day', 'low sun', 'sunset')},
                errors={m['map']: m['errors'] for m in maps if m['errors']}, rows=rows)


def run_maps(args):
    import library
    game = install(args)
    recs = records(game)
    donors = [(name, str(path)) for name, role, path in library.donors(game) if role == 'base'
              and (not args.only or name in args.only)]
    jobs = [(name, path, recs.get(name.lower(), [])) for name, path in donors]
    started = time.perf_counter()
    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs) as pool:
            maps = pool.map(survey, jobs)
    else:
        maps = [survey(j) for j in jobs]
    maps.sort(key=lambda m: m['map'].casefold())
    result = dict(date='2026-11-27', game=settings.kind_label(game), population='library.donors: the base map of '
                  'each map record the editor lists (Firaxis-cooked packages), persistent level only',
                  seconds=round(time.perf_counter() - started, 1), summary=summary(maps), maps=maps)
    update_evidence(args.out, 'maps', result)
    s = result['summary']
    print(f"{s['maps']} maps in {result['seconds']} s; kinds {s['kinds']}; records {s['recordTimes']}")
    print(f"with sky light {len(s['withSkyLight'])}, without {len(s['withoutSkyLight'])}; with a dome {s['withSkyDome']}"
          f"; no dominant light: {s['withoutDominantLight']}; errors: {len(s['errors'])}")


# -------------------------------------------------------------------------------------------------------- trace

def run_trace(args):
    paths.use('bake')
    import relight
    import shadowmaps
    import lightmap_fields
    game = install(args)
    src = map_path(game, args.map)
    p = lighting.Package(src)
    lights = shadowmaps.dominant_lights(p)
    enabled = {g: l for g, l in lights.items() if l['enabled']}
    receivers = shadowmaps.dominant_receivers(p, enabled)
    sizes, texels = {}, 0
    for _, _, sm, _ in receivers:
        if sm['texture'] not in sizes:
            top = lightmap_fields.texture_fields(p, sm['texture'])['mips'][0]
            sizes[sm['texture']] = (top['width'], top['height'])
        w, h = sizes[sm['texture']]
        texels += round(sm['scale'][0] * w) * round(sm['scale'][1] * h)
    jobs = [dict(path=path, ci=ci, sm=sm, light=light, source=None, fresh=True) for path, ci, sm, light in receivers]
    queue = [('shadow', ('shadow', k), None, False, job) for k, job in enumerate(jobs)]
    # what a worker builds before its first job: the two scenes of an edit (timed here, in this process)
    t = time.perf_counter()
    scene = relight.Scene(p, **SCENE_ARGS)
    after = relight.Scene(p, **SCENE_ARGS)
    scenes = time.perf_counter() - t
    workers = args.jobs or relight.default_jobs()
    results = {}

    def on_piece(path, r, error, failed, spent, memory):
        results[path[1]] = (r, error, spent)
    started = time.perf_counter()
    if workers <= 1:
        relight._worker_set(p, scene, after, None)
    peak = relight.run_jobs(queue, workers, (str(src), SCENE_ARGS, {}, {}, None, None), on_piece)
    wall = time.perf_counter() - started
    done = [r for r, e, _ in results.values() if r is not None]
    errors = [e for _, e, _ in results.values() if e]
    seconds = sorted((s for _, _, s in results.values()), reverse=True)
    run = dict(map=args.map, workers=workers, cpus=multiprocessing.cpu_count(), components=len(receivers),
               shadowMaps=len(jobs), atlases=len(sizes), rectangleTexels=texels,
               texelsWritten=sum(r['report']['texelsWritten'] for r in done),
               rays=sum(r['report']['subSamplesChanged'] for r in done), upsample=shadowmaps.UPSAMPLE,
               traced=len(done), empty=len(jobs) - len(done) - len(errors), errors=errors[:5],
               scenesSecondsOneProcess=round(scenes, 2), wallSeconds=round(wall, 1),
               jobSecondsSum=round(sum(seconds), 1), slowestJobs=[round(s, 2) for s in seconds[:5]],
               peakWorkerMemoryMB=round(peak))
    print(json.dumps(run))
    data = json.loads(args.out.read_text(encoding='utf-8')).get('trace', {}) if args.out.is_file() else {}
    data.setdefault('method', 'shadowmaps.fresh_shadow_map for every dominant-light distance-field shadow map of the '
                    'map (shadowmaps.dominant_receivers), each a fresh job, on relight.run_jobs with relight\'s worker '
                    'start (the map opened and the scenes before and after an edit built, relight.py\'s defaults); '
                    'wallSeconds from the queue handed over to the last result, the workers\' start included')
    data.setdefault('runs', []).append(run)
    update_evidence(args.out, 'trace', data)


# ---------------------------------------------------------------------------------------------------- level-map

def run_level_map(args):
    paths.use('bake')
    import numpy as np
    import relight
    game = install(args)
    p = lighting.Package(map_path(game, args.map))
    ci = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'DominantDirectionalLightComponent'
              and p.name(i).startswith(PL))
    m = lighting.dominant_shadow_map(p, ci)
    sx, sy, b = m['sizeX'], m['sizeY'], m['bounds']
    l2w = np.array(m['lightToWorld'])
    w2l = np.array(m['worldToLight'])
    scene = relight.Scene(p, samples=1, bounce_rays=0, emissive=False)
    xs = b[0] + (np.arange(sx) + 0.5) * (b[3] - b[0]) / sx
    ys = b[1] + (np.arange(sy) + 0.5) * (b[4] - b[1]) / sy
    X, Y = np.meshgrid(xs, ys)
    near = np.stack([X.ravel(), Y.ravel(), np.full(X.size, b[2]), np.ones(X.size)], 1) @ l2w
    forward = l2w[2, :3] / np.linalg.norm(l2w[2, :3])
    dist = np.asarray(scene.occluder.scene.run(near[:, :3].astype(np.float32),
                                               np.tile(forward, (len(near), 1)).astype(np.float32),
                                               query='DISTANCE'), float)
    hit = np.isfinite(dist) & (dist < 1e9)
    traced = b[2] + dist
    depths = np.array(m['depths'], float)
    layouts = {'rows of X, Y down the rows': depths,
               'columns (transposed)': depths.reshape(sx, sy).T.ravel(),
               'rows, Y flipped': depths.reshape(sy, sx)[::-1].ravel()}
    out = dict(map=args.map, component=p.name(ci)[len(PL):], sizeX=sx, sizeY=sy, bounds=[round(v, 2) for v in b],
               unitsPerTexel=[round((b[3] - b[0]) / sx, 2), round((b[4] - b[1]) / sy, 2)],
               worldToLightTimesLightToWorld=np.round(w2l @ l2w, 4).tolist(),
               lightDirection=[round(v, 5) for v in forward.tolist()],
               hits=int(hit.sum()), texels=int(len(hit)), depthScale='near face + depth / 65535 x box depth',
               layouts={})
    for name, stored in layouts.items():
        z = b[2] + stored / 65535.0 * (b[5] - b[2])
        d = z[hit] - traced[hit]
        out['layouts'][name] = dict(medianDifference=round(float(np.median(d)), 2),
                                    within25=round(float(np.mean(np.abs(d) < 25)), 4),
                                    within100=round(float(np.mean(np.abs(d) < 100)), 4),
                                    correlation=round(float(np.corrcoef(z[hit], traced[hit])[0, 1]), 4))
    print(json.dumps(out))
    update_evidence(args.out, 'levelMap', out)


# --------------------------------------------------------------------------------------------------- write-back

def marks_round_trip(src, scratch):
    import package_edit
    p = lighting.Package(src)
    level = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'Level' and p.name(i) == PL[:-1])
    v = lighting.light_volume(p, level)
    flipped = [1 - s[-1] for s in v['samples']]
    first, second = scratch / f'{src.stem}-marks-flipped.upk', scratch / f'{src.stem}-marks-back.upk'
    t = time.perf_counter()
    report = package_edit.write_edited(str(src), str(first), lighting.mark_edits(v, flipped))
    written = time.perf_counter() - t
    q = lighting.Package(first)
    w = lighting.light_volume(q, level)
    same_rest = all(a[:-1] == b[:-1] for a, b in zip(v['samples'], w['samples']))
    back = package_edit.write_edited(str(first), str(second), lighting.mark_edits(w, [s[-1] for s in v['samples']]))
    r = lighting.Package(second)
    again = lighting.light_volume(r, level)
    data_same = r.data[r.header['headersize']:] == p.data[p.header['headersize']:] if 'headersize' in r.header \
        else None
    return dict(samples=len(v['samples']), markedBefore=sum(s[-1] for s in v['samples']),
                edits=len(flipped), flippedReadBack=[s[-1] for s in w['samples']] == flipped,
                otherFieldsKept=same_rest, offset=v['offset'], writeSeconds=round(written, 2),
                report={k: report[k] for k in sorted(report) if not isinstance(report[k], (list, dict))},
                writtenBackAsTheMapHasThem=[s[-1] for s in again['samples']] == [s[-1] for s in v['samples']],
                logicalBytesAsTheMapsAfterTheSummary=data_same,
                backReport={k: back[k] for k in sorted(back) if not isinstance(back[k], (list, dict))})


def light_writer(src, scratch):
    """native_lights.set_property on the dominant light's component, in a growing copy of the map."""
    paths.use('bake')
    import native_copy
    import native_lights
    import package_grow
    import props as legacy_props
    p = lighting.Package(src)
    ci = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'DominantDirectionalLightComponent'
              and p.name(i).startswith(PL))
    ai = p.exports[ci - 1]['outer']
    e = p.exports[ci - 1]
    g = package_grow.Grower(str(src))
    walker = native_copy.Walker(p, g)
    given = native_lights.props_start(p, ci)
    out = dict(component=p.name(ci)[len(PL):], exportSize=e['size'], startGiven=given)
    try:
        native_lights.set_property(walker, g, bytearray(g.export_data(ci)), given, 'Brightness', 'FloatProperty', None,
                                   struct.pack('<f', 2.5))
        out['fromTheStartGiven'] = 'written (unexpected)'
    except ValueError as error:
        out['fromTheStartGiven'] = f'refused: {error}'
    m = lighting.dominant_shadow_map(p, ci)
    skip = m['offset'] - e['off'] + 2 * len(m['depths'])
    right = legacy_props.props_start(p.data, dict(e, off=e['off'] + skip, size=e['size'] - skip), p.names) - e['off']
    out['startPastTheShadowMap'] = right
    data = bytearray(g.export_data(ci))
    colour = [255, 139, 45]
    data = native_lights.set_property(walker, g, data, right, 'Brightness', 'FloatProperty', None, struct.pack('<f', 2.5))
    data = native_lights.set_property(walker, g, data, right, 'LightColor', 'StructProperty', 'Color',
                                      bytes([colour[2], colour[1], colour[0], 0]))
    data = native_lights.set_property(walker, g, data, right, 'bCastCompositeShadow', 'BoolProperty', None, b'\x01')
    g.relocate(ci, bytes(data))
    rotation = [-2912, 16384, 0]
    native_copy.set_pose(walker, g, p, ai, None, rotation)
    dst = scratch / f'{src.stem}-sun-written.upk'
    g.write(str(dst))
    q = lighting.Package(dst)
    n = lighting.dominant_shadow_map(q, ci)
    out.update(written=dict(Brightness=2.5, LightColor=colour, bCastCompositeShadow=True, actorRotation=rotation),
               readBack=dict(Brightness=round(q.own(ci, 'Brightness'), 4),
                             LightColor=byte_colour(q.own(ci, 'LightColor')),
                             bCastCompositeShadow=bool(q.own(ci, 'bCastCompositeShadow')),
                             actorRotation=q.own(ai, 'Rotation'), LightGuid=guid(q.own(ci, 'LightGuid')),
                             guidKept=q.own(ci, 'LightGuid') == p.own(ci, 'LightGuid')),
               shadowMapKept=n['depths'] == m['depths'] and n['bounds'] == m['bounds'],
               exportSizeAfter=q.exports[ci - 1]['size'])
    return out


def run_write_back(args):
    paths.use('bake')
    game = install(args)
    src = map_path(game, args.map)
    scratch = Path(args.scratch)
    if scratch.resolve().is_relative_to(src.parent.resolve()) or scratch.resolve().is_relative_to(Path(game).resolve()):
        sys.exit('the scratch folder must be outside the game install')
    scratch.mkdir(parents=True, exist_ok=True)
    before = sha256(src)
    out = dict(map=args.map, marks=marks_round_trip(src, scratch), lightWriter=light_writer(src, scratch))
    if sha256(src) != before:
        sys.exit('the install\'s map changed during the run')
    for f in scratch.glob(f'{src.stem}-*.upk'):
        f.unlink()
    print(json.dumps(out, indent=1))
    update_evidence(args.out, 'writeBack', out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ('maps', 'trace', 'level-map', 'write-back'):
        s = sub.add_parser(name)
        s.add_argument('--game', type=Path, help='the game install (default: the editor\'s game setting)')
        s.add_argument('--out', type=Path, default=OUT, help='the evidence file (default %(default)s)')
        if name == 'maps':
            s.add_argument('--jobs', type=int, default=max(1, (multiprocessing.cpu_count() or 2) // 4))
            s.add_argument('--only', action='append', help='only this map (repeatable)')
        else:
            s.add_argument('--map', default='URB_Bar')
        if name == 'trace':
            s.add_argument('--jobs', type=int, help='the workers (default: relight.default_jobs, as a Build)')
        if name == 'write-back':
            s.add_argument('--scratch', type=Path, required=True, help='a folder outside the install for the copies')
    args = ap.parse_args(argv)
    {'maps': run_maps, 'trace': run_trace, 'level-map': run_level_map, 'write-back': run_write_back}[args.command](args)


if __name__ == '__main__':
    main()
