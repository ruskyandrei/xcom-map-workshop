"""A research tool (not shipped): every placed decal of the install's maps read (stage D1 of the game-likeness plan;
F-210, F-211), through the reader the export uses (decal_records.py); it writes nothing into the install.

  python -B tools/upk/audit_decals.py [--game <install>] [--out <json>] [--jobs N] [--only MAP ...]
      [--programs --keep <folder>]

For every package the editor's map records name (library.donors: the base maps and the streams), every
DecalComponent:
- its receivers read to the component's last byte (decal_records.receivers): counted, with the receiving components'
  classes, the vertex and index element sizes, the lightmap types, the shadow maps and the two closing integers;
- its frame (decal_records.frame): the frame vectors' lengths and angles; whether they are the owner actor's axes
  (HitNormal its -X, HitTangent its -Y, HitBinormal its Z) and HitLocation its Location; the size members that
  differ from the class's defaults (tiling, offsets, DecalRotation, NearPlane);
- each stored vertex put in the world (its receiver's actor and component transforms) and given the vertex shader's
  values (decal_records.coordinates): whether the texture coordinates lie in 0..1 and the depth in
  NearPlane..FarPlane, as the clip the decal was stored with would leave them;
- its material: the decal materials by name, blend mode and lighting model.
With --programs, each decal material's compiled shaders (the install's RefShaderCache, kept decompressed in `--keep`)
are sliced for the local vertex factory (the program its export record carries) and for the decal vertex factory,
with what each refuses and the inputs each reads.

The numbers go into the findings register (F-210, F-211); the evidence file into research/evidence.
"""
import argparse
from collections import Counter
import json
import math
import multiprocessing
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import settings  # noqa: E402
from package import Package, FormatError  # noqa: E402
from export_math import multiply, transform  # noqa: E402
import decal_records  # noqa: E402

OUT = HERE.parents[1] / 'research' / 'evidence' / 'decal-audit-2026-11-27.json'
SLACK = 0.01            # how far outside 0..1 a stored vertex's coordinate may lie (float error at the clip's edge)


def install(args):
    game = args.game or settings.game_install(settings.load_settings())[0]
    if game is None:
        sys.exit('no game install: give --game, or set it (python tools/viewer/viewer.py settings --game <folder>)')
    return Path(game)


def axes(rotation):
    m = transform([0, 0, 0], rotation, [1, 1, 1])
    return [[m[r][c] for r in range(3)] for c in range(3)]


def near(a, b, tol=1e-3):
    return a is not None and b is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def placed(p, component):
    """A receiving component's local-to-world transform (its actor's and its own), as the export places a piece."""
    actor = p.exports[component - 1]['outer']
    scale = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
    own = [v * p.effective(component, 'Scale', 1) for v in p.effective(component, 'Scale3D', [1, 1, 1])]
    am = transform(p.effective(actor, 'Location', [0, 0, 0]), p.effective(actor, 'Rotation', [0, 0, 0]), scale)
    cm = transform(p.effective(component, 'Translation', [0, 0, 0]), p.effective(component, 'Rotation', [0, 0, 0]), own)
    return multiply(am, cm)


def survey(job):
    name, path = job
    out = dict(map=name, decals=0, placed=0, archetypes=0, receivers=0, vertices=0, triangles=0, tailBytes=0,
               errors=[], receiverClasses=Counter(), ownerClasses=Counter(), materials=Counter(), notOwnAxes=[],
               notAtOwner=[], unitFrame=0, sizeMembers=Counter(), outsideBox=[], outsideDepth=[], strides=Counter(),
               closing=Counter(), lightmaps=Counter(), shadowMaps=0, worstU=0.0, materialRefs={}, byOwner=0,
               transforms=Counter(), noClip=0, ownerScaled=0, frameLeftOut=Counter(), unindexed=0)
    try:
        p = Package(path)
    except (FormatError, OSError, ValueError) as error:
        out['errors'].append(f'{name}: {error}')
        return out
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) != 'DecalComponent':
            continue
        out['decals'] += 1
        e = p.exports[i - 1]
        try:
            start = p.properties(i)[1]
            out['tailBytes'] += e['off'] + e['size'] - start
            recs = decal_records.receivers(p.native(i), p)
            f = decal_records.frame(p, i)
        except (FormatError, ValueError) as error:
            out['errors'].append(f'{p.name(i)}: {error}')
            continue
        if not recs:
            out['archetypes'] += 1
            continue
        out['placed'] += 1
        owner = e['outer']
        out['ownerClasses'][p.cls(owner)] += 1
        material = decal_records.member(p, i, 'DecalMaterial') or 0
        mname = p.name(material) if material else '(none)'
        out['materials'][mname] += 1
        if material and mname not in out['materialRefs']:
            out['materialRefs'][mname] = material
        saved = decal_records.saved_frame(p, i)
        out['byOwner'] += f['byOwner']
        out['transforms'][str(decal_records.member(p, i, 'DecalTransform'))] += 1
        out['noClip'] += bool(decal_records.member(p, i, 'bNoClip'))
        scale = [v * p.effective(owner, 'DrawScale', 1) for v in p.effective(owner, 'DrawScale3D', [1, 1, 1])]
        out['ownerScaled'] += any(abs(v - 1) > 1e-6 for v in scale)
        for key in decal_records.FRAME:
            if key not in saved:
                out['frameLeftOut'][key] += 1
        vectors = [saved[k] for k in ('HitTangent', 'HitBinormal', 'HitNormal') if k in saved]
        if len(vectors) == 3:
            unit = all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-3 for v in vectors)
            square = all(abs(sum(a * b for a, b in zip(vectors[j], vectors[k]))) < 1e-3
                         for j, k in ((0, 1), (0, 2), (1, 2)))
            out['unitFrame'] += unit and square
        x, y, z = axes(p.effective(owner, 'Rotation', [0, 0, 0]))
        own_axes = {'HitNormal': [-c for c in x], 'HitTangent': [-c for c in y], 'HitBinormal': z}
        if any(not near(saved[k], v) for k, v in own_axes.items() if k in saved):
            out['notOwnAxes'].append(p.name(i))
        if 'HitLocation' in saved and not near(saved['HitLocation'], p.effective(owner, 'Location', [0, 0, 0]), 0.01):
            out['notAtOwner'].append(p.name(i))
        if any(f[k] is None for k in ('location', 'tangent', 'binormal', 'normal')):
            out['errors'].append(f'{p.name(i)}: its frame is not saved')
            continue
        for key, default in decal_records.DEFAULTS.items():
            if decal_records.member(p, i, key) is not None and key not in ('Width', 'Height', 'FarPlane', 'BlendRange', 'DepthBias'):
                out['sizeMembers'][key] += 1
        lo_u = lo_d = math.inf
        hi_u = hi_d = -math.inf
        for rec in recs:
            out['receivers'] += 1
            out['vertices'] += rec['vertexCount']
            out['triangles'] += rec['triangles']
            out['receiverClasses'][p.cls(rec['component'])] += 1
            out['lightmaps'][rec['lightmap']] += 1
            out['shadowMaps'] += len(rec['shadowMaps'])
            out['closing'][f"{rec['data']},{rec['instance']}"] += 1
            out['unindexed'] += not rec['indexed']
            m = placed(p, rec['component'])
            positions, _, normals = decal_records.vertices(rec)
            if not len(positions):
                continue
            points, normals = decal_records.in_world(m, positions, normals)
            u, v, _, depth = decal_records.coordinates(f, points, normals)
            lo_u, hi_u = min(lo_u, float(u.min()), float(v.min())), max(hi_u, float(u.max()), float(v.max()))
            lo_d, hi_d = min(lo_d, float(depth.min())), max(hi_d, float(depth.max()))
        out['worstU'] = max(out['worstU'], -lo_u, hi_u - 1)
        if lo_u < -SLACK or hi_u > 1 + SLACK:
            out['outsideBox'].append([p.name(i), round(lo_u, 3), round(hi_u, 3)])
        if lo_d < f['nearPlane'] - 1 or hi_d > f['farPlane'] + 1:
            out['outsideDepth'].append([p.name(i), round(lo_d, 2), round(hi_d, 2), f['nearPlane'], f['farPlane']])
    for key in ('receiverClasses', 'ownerClasses', 'materials', 'sizeMembers', 'strides', 'closing', 'lightmaps',
                'transforms', 'frameLeftOut'):
        out[key] = dict(out[key])
    out['path'] = str(path)
    return out


def programs(maps, keep):
    """Each decal material sliced for the local and the decal vertex factories: {name: {blend, lighting, local,
    decal}}, each slice's outputs and refusals and the input kinds it reads."""
    import material_programs
    import shader_cache
    import shader_slice
    out, opened = {}, {}
    cache = None
    for m in maps:
        for name, index in m['materialRefs'].items():
            if name in out:
                continue
            path = Path(m['path'])
            if path not in opened:
                opened.clear()
                opened[path] = Package(path)
            p = opened[path]
            if cache is None:
                cache = shader_cache.open_cache(path.parent / shader_cache.FILE_NAME, keep=keep)
            chain, current = [], index
            while current > 0 and current not in chain:
                chain.append(current)
                current = p.own(current, 'Parent', 0)
            blend = next((p.own(c, 'BlendMode') for c in chain if p.own(c, 'BlendMode') is not None), 'BLEND_Opaque')
            light = next((p.own(c, 'LightingModel') for c in chain if p.own(c, 'LightingModel') is not None), 'MLM_Phong')
            row = dict(blend=blend, lighting=light, uses=sum(x['materials'].get(name, 0) for x in maps))
            try:
                how, base, switches, _ = material_programs.shader_key(p, index)
                kind, smap = material_programs.match(cache, base, switches)
            except (FormatError, ValueError) as error:
                row['error'] = str(error)
                out[name] = row
                continue
            row['matched'] = kind
            for tag, factory in (('local', shader_slice.FACTORY), ('decal', 'FLocalDecalVertexFactory')):
                if smap is None:
                    row[tag] = dict(refused='unmatched')
                    continue
                try:
                    prog = shader_slice.slice_material(cache, smap, {}, translucent=blend in material_programs.SEE_THROUGH,
                                                       factory=factory)
                    kinds = sorted({s['kind'] for sources in prog['inputs'].values() for s in sources if s})
                    row[tag] = dict(outputs=sorted(prog['outputs']), refused=prog['refused'], inputs=kinds,
                                    unlit=bool(prog.get('unlit')))
                except shader_slice.Refused as why:
                    row[tag] = dict(refused=str(why))
                except (FormatError, ValueError, KeyError) as error:
                    row[tag] = dict(error=str(error))
            out[name] = row
    return out


def summary(maps):
    total = Counter()
    merged = {k: Counter() for k in ('receiverClasses', 'ownerClasses', 'materials', 'sizeMembers', 'closing',
                                     'lightmaps', 'transforms', 'frameLeftOut')}
    for m in maps:
        for k in ('decals', 'placed', 'archetypes', 'receivers', 'vertices', 'triangles', 'tailBytes', 'unitFrame',
                  'shadowMaps', 'byOwner', 'noClip', 'ownerScaled', 'unindexed'):
            total[k] += m[k]
        for k in merged:
            merged[k].update(m[k])
    return dict(packages=len(maps), withDecals=sum(1 for m in maps if m['placed']), **total,
                **{k: dict(v.most_common()) for k, v in merged.items()},
                errors=[e for m in maps for e in m['errors']],
                notOwnAxes=sum(len(m['notOwnAxes']) for m in maps), notAtOwner=sum(len(m['notAtOwner']) for m in maps),
                outsideBox=[x for m in maps for x in m['outsideBox']],
                outsideDepth=[x for m in maps for x in m['outsideDepth']],
                worstCoordinate=round(max((m['worstU'] for m in maps), default=0.0), 5))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--game', type=Path, help="the game install (default: the editor's game setting)")
    ap.add_argument('--out', type=Path, default=OUT, help='the evidence file (default %(default)s)')
    ap.add_argument('--jobs', type=int, default=max(1, (multiprocessing.cpu_count() or 2) // 4))
    ap.add_argument('--only', action='append', help='only this package (repeatable)')
    ap.add_argument('--programs', action='store_true', help='slice each decal material for both vertex factories')
    ap.add_argument('--keep', type=Path, help='--programs: a folder to keep the decompressed shader cache in')
    args = ap.parse_args(argv)
    import library
    game = install(args)
    jobs = [(name, str(path)) for name, role, path in library.donors(game) if not args.only or name in args.only]
    started = time.perf_counter()
    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs) as pool:
            maps = pool.map(survey, jobs)
    else:
        maps = [survey(j) for j in jobs]
    maps.sort(key=lambda m: m['map'].casefold())
    result = dict(date='2026-11-27', tool='tools/upk/audit_decals.py', game=settings.kind_label(game),
                  population='library.donors: every base map and stream of the map records the editor lists '
                  '(Firaxis-cooked packages)', seconds=round(time.perf_counter() - started, 1), summary=summary(maps))
    if args.programs:
        result['materials'] = programs(maps, args.keep)
    for m in maps:
        m.pop('path', None)
        m.pop('materialRefs', None)
    result['maps'] = [m for m in maps if m['decals'] or m['errors']]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    s = result['summary']
    print(f"{s['packages']} packages ({s['withDecals']} with decals) in {result['seconds']} s: {s['decals']} decal "
          f"components, {s['placed']} placed, {s['archetypes']} archetypes; {s['receivers']} receivers, {s['vertices']} "
          f"vertices, {s['triangles']} triangles; errors {len(s['errors'])}; not the owner's axes {s['notOwnAxes']}, "
          f"not at the owner {s['notAtOwner']}; outside the box {len(s['outsideBox'])} (worst {s['worstCoordinate']}), "
          f"outside the depth {len(s['outsideDepth'])}; by the owner {s['byOwner']}, frame members left out "
          f"{s['frameLeftOut']}, not clipped {s['noClip']} ({s['unindexed']} receivers unindexed), owners scaled "
          f"{s['ownerScaled']}, size members set {s['sizeMembers']}")


if __name__ == '__main__':
    main()
