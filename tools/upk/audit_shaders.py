"""A research tool (not shipped): track A's survey of the game-likeness plan (A-S0), over the editor's cache of
exported maps and the install's RefShaderCache.

Pass a: every material the cache's exports draw is matched to a material shader map of the cache, counted by
material and weighted by the mesh sections that draw it. A material instance with a static permutation of its own
is keyed by its static parameter set (base material ID and switches), anything else by the first such instance up
its parents, else by its root material's own ID with no switches. Matches are tried exactly (switches' values and
override flags), then by the switches' values alone, then by the base ID alone.

Pass b: every matched material sliced (tools/viewer/shader_slice.py), counted by sections drawn: its colour
translated or left as today (by reason), each output's end found, the colour's mark by form, the inputs read; with
--colours, each translated material's colour on white and on mid-grey vertex colours against today's texture,
ranked by how far it moves weighted by its sections.

  python -B tools/upk/audit_shaders.py a|b [--cache <cache>] [--out <json>] [--maps <map> ...] [--colours]

The numbers go into the findings register (F-167); the evidence file into research/evidence.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import settings  # noqa: E402
from package import Package, FormatError  # noqa: E402
import materials  # noqa: E402
import shader_cache  # noqa: E402

KEY = re.compile(r'^(?:stream-(.+)-)?(\d+)$')


def newest_export(folder):
    """The newest map export (a generation folder with a scene.json) of a map's cache folder, or None."""
    found = [g for g in Path(folder).glob('*-map') if (g / 'scene.json').exists()]
    if not found:
        return None
    return max(found, key=lambda g: int(re.search(r'-v(\d+)-', g.name).group(1)) if re.search(r'-v(\d+)-', g.name) else 0)


def drawn_sections(scene):
    """{material key: sections drawn} over the scene's objects and its streams' (a section drawn once an object)."""
    counts = Counter()
    objects = list(scene.get('objects', []))
    for stream in (scene.get('streams') or {}).values():
        objects += stream.get('objects', [])
    meshes = scene.get('meshes', {})
    for o in objects:
        mesh = meshes.get(str(o.get('mesh')))
        if not mesh:
            continue
        own = o.get('materials') or []
        for section in mesh.get('sections', []):
            slot = section.get('slot', 0)
            key = own[slot] if slot < len(own) and own[slot] is not None else section.get('material')
            if key is not None:
                counts[str(key)] += 1
    return counts


def shader_key(p, index, with_owner=False):
    """(how, base id, switches) of a material: 'instance' from the nearest permutation instance up its parents, or
    'root' from the root material's resource ID; with_owner adds the object whose resource that is."""
    current, seen, root = index, set(), index
    while current > 0:
        if current in seen:
            raise FormatError('a material parent cycle')
        seen.add(current)
        own = materials.static_parameters(p, current) if p.cls(current) != 'Material' else None
        if own is not None:
            return ('instance', own['base'], own['switches']) + ((current,) if with_owner else ())
        root = current
        current = p.own(current, 'Parent', 0)
    if p.cls(root) not in ('Material', 'DecalMaterial'):
        raise FormatError('the root %s is a %s' % (p.name(root), p.cls(root)))
    return ('root', materials.resource_id(p, root), []) + ((root,) if with_owner else ())


def match(cache, base, switches):
    """('exact' | 'values' | 'base' | 'none', the map or None)."""
    found = cache.by_base.get(base, [])
    if not found:
        return 'none', None
    want = sorted(switches)
    for m in found:
        if sorted(m.switches) == want:
            return 'exact', m
    values = sorted((n, v) for n, v, _ in switches)
    for m in found:
        if sorted((n, v) for n, v, _ in m.switches) == values:
            return 'values', m
    on = {n for n, v, _ in switches if v}
    for m in found:
        if {n for n, v, _ in m.switches if v} == on:
            return 'values', m
    return 'base', found[0]


def pass_a(args):
    cache_folder = Path(args.cache or settings.configured('cache'))
    by_map, totals, by_material, examples = {}, Counter(), Counter(), defaultdict(list)
    cache = None
    for folder in sorted(cache_folder.iterdir()):
        if args.maps and folder.name not in args.maps:
            continue
        export = newest_export(folder) if folder.is_dir() else None
        if export is None:
            continue
        scene = json.loads((export / 'scene.json').read_text(encoding='utf-8'))
        source = Path(scene['source']['file'])
        if cache is None:
            cache = shader_cache.open_cache(source.parent / shader_cache.FILE_NAME)
        sections = drawn_sections(scene)
        packages = {}
        tally = Counter()
        for key, count in sections.items():
            record = scene['materials'].get(key, {})
            found = KEY.match(key)
            if key == 'interior' or key.endswith('-missing'):
                outcome = 'no material'           # the export's own stand-ins: an interior's fill, a missing material
            elif not found:
                outcome = 'unread key'
            else:
                stream, index = found.group(1), int(found.group(2))
                name = (scene['streams'][stream]['package'] if stream else source.name)
                kind = 'stream' if stream else 'map'
                try:
                    if name not in packages:
                        packages[name] = Package(source.parent / name)
                    p = packages[name]
                    how, base, switches = shader_key(p, index)
                    outcome, m = match(cache, base, switches)
                    outcome = '%s (%s)' % (outcome, how)
                except (FormatError, OSError, KeyError, ValueError) as error:
                    outcome = 'unreadable'
                    examples['unreadable'].append('%s %s: %s' % (folder.name, record.get('name'), error))
                if kind == 'stream':
                    tally['stream materials'] += 1
            tally[outcome] += count
            totals[outcome] += count
            by_material[outcome] += 1
            if outcome.startswith(('none', 'base')) and len(examples[outcome]) < 12:
                examples[outcome].append('%s %s' % (folder.name, record.get('name')))
        by_map[folder.name] = dict(tally)
        print('%-28s %s' % (folder.name, dict(tally)))
    drawn = sum(v for k, v in totals.items() if k != 'no material')
    matched = sum(v for k, v in totals.items() if k.startswith(('exact', 'values')))
    summary = dict(sections=drawn, matched=matched, share=round(matched / drawn, 4) if drawn else None,
                   bySection=dict(totals.most_common()), byMaterial=dict(by_material.most_common()))
    print('\nsections drawn %d, matched %d (%.1f%%)' % (drawn, matched, 100 * matched / max(drawn, 1)))
    for k, v in totals.most_common():
        print('  %-24s %7d sections  %5d materials' % (k, v, by_material[k]))
    if args.out:
        Path(args.out).write_text(json.dumps(dict(pass_='a', summary=summary, maps=by_map,
                                                  examples=dict(examples)), indent=1) + '\n',
                                  encoding='utf-8', newline='\n')
        print('written', args.out)


# ---------------------------------------------------------------------------------------------------------------
# Pass b: every matched material sliced

def small_texture(p, index, size=128):
    """A texture's pixels at its first mip no larger than `size` (or its smallest), as floats (h, w, 4) 0..1, with
    its sRGB flag; None where it can't be read."""
    import io
    import numpy as np
    from PIL import Image
    from mesh import bulk
    from texture import decompress_payload, dds_header
    from package import cache_file
    try:
        r = p.native(index)
        bulk(r)
        mips = []
        for _ in range(r.count()):
            item = bulk(r)
            item['width'], item['height'] = r.unpack('2i')
            if item['size'] > 0 and item['count'] > 0 and not item['flags'] & 32:
                mips.append(item)
        if not mips:
            return None
        fits = [m for m in mips if max(m['width'], m['height']) <= size]
        mip = max(fits, key=lambda m: m['width']) if fits else min(mips, key=lambda m: m['width'])
        data = mip['data']
        if mip['flags'] & 1:
            path = cache_file(p.path.parent, p.effective(index, 'TextureFileCacheName'))
            with path.open('rb') as f:
                f.seek(mip['offset'])
                data = f.read(mip['size'])
        data = decompress_payload(data, mip['flags'])
        fmt = p.effective(index, 'Format')
        w, h = mip['width'], mip['height']
        if fmt in ('PF_DXT1', 'PF_DXT3', 'PF_DXT5', 'PF_BC5'):
            fourcc = {'PF_DXT1': 'DXT1', 'PF_DXT3': 'DXT3', 'PF_DXT5': 'DXT5', 'PF_BC5': 'ATI2'}[fmt]
            image = Image.open(io.BytesIO(dds_header(w, h, fourcc, len(data)) + data)).convert('RGBA')
        elif fmt == 'PF_A8R8G8B8':
            image = Image.frombytes('RGBA', (w, h), data, 'raw', 'BGRA')
        elif fmt == 'PF_G8':
            image = Image.frombytes('L', (w, h), data).convert('RGBA')
        else:
            return None
        pixels = np.asarray(image, dtype=np.float64) / 255.0
        srgb = bool(p.effective(index, 'SRGB', True))
        if srgb:
            pixels[..., :3] = np.where(pixels[..., :3] <= 0.04045, pixels[..., :3] / 12.92,
                                       ((pixels[..., :3] + 0.055) / 1.055) ** 2.4)
        return pixels
    except Exception:
        return None


def sampler(pixels):
    """sample(uv (n, 2)) -> (n, 4): nearest texel, wrapping."""
    import numpy as np
    h, w = pixels.shape[:2]

    def sample(uv):
        x = (np.floor(uv[:, 0] * w).astype(np.int64)) % w
        y = (np.floor(uv[:, 1] * h).astype(np.int64)) % h
        return pixels[y, x]
    return sample


def to_lab(linear):
    import numpy as np
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = np.clip(np.asarray(linear, dtype=np.float64), 0, None) @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def srgb8(linear):
    import numpy as np
    c = np.clip(np.asarray(linear, dtype=np.float64), 0, 1)
    return [int(round(255 * (v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055))) for v in c]


def program_colour(program, textures, grey):
    """The mean linear colour of a program's diffuse over a 64 by 64 grid of UVs, with vertex colours all `grey`."""
    import numpy as np
    import shader_eval
    n = 64
    u, v = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n)
    uv = np.stack([u.ravel(), v.ravel()], axis=1)
    inputs = {'uv%d' % k: uv for k in range(4)}
    inputs['color'] = np.full((n * n, 4), grey)
    inputs['cameraVector'] = np.tile([0.0, 0.0, 1.0], (n * n, 1))
    inputs['worldPosition'] = np.tile([0.0, 0.0, -600.0, 1.0], (n * n, 1))
    for name, axis in (('worldTangent', [1.0, 0, 0]), ('worldBinormal', [0, 1.0, 0]), ('worldNormal', [0, 0, 1.0])):
        inputs[name] = np.tile(axis, (n * n, 1))
    out = shader_eval.run(program, inputs, textures, n=n * n)
    return out['diffuse'].mean(axis=0)


def pass_b(args):
    import shader_slice
    import numpy as np
    cache_folder = Path(args.cache or settings.configured('cache'))
    totals, by_material, reasons, ends, forms, input_kinds = (Counter() for _ in range(6))
    ranked, examples = [], defaultdict(list)
    cache = None
    for folder in sorted(cache_folder.iterdir()):
        if args.maps and folder.name not in args.maps:
            continue
        export = newest_export(folder) if folder.is_dir() else None
        if export is None:
            continue
        scene = json.loads((export / 'scene.json').read_text(encoding='utf-8'))
        source = Path(scene['source']['file'])
        if cache is None:
            cache = shader_cache.open_cache(source.parent / shader_cache.FILE_NAME)
        packages = {}
        tally = Counter()
        for key, count in drawn_sections(scene).items():
            if key == 'interior' or key.endswith('-missing'):
                continue
            record = scene['materials'].get(key, {})
            found = KEY.match(key)
            if not found:
                outcome = 'unread key'
            else:
                stream, index = found.group(1), int(found.group(2))
                name = scene['streams'][stream]['package'] if stream else source.name
                try:
                    if name not in packages:
                        packages[name] = Package(source.parent / name)
                    p = packages[name]
                    how, base, switches, owner = shader_key(p, index, with_owner=True)
                    kind, m = match(cache, base, switches)
                    if m is None:
                        raise shader_slice.Refused('unmatched', kind)
                    values = {'vectors': record.get('vectors') or {}, 'scalars': record.get('scalars') or {}}
                    translucent = record.get('blend') in ('BLEND_Translucent', 'BLEND_Additive', 'BLEND_Modulate')
                    program = shader_slice.slice_material(cache, m, values, translucent=translucent)
                    for out in program['outputs']:
                        ends[out] += count
                    for out, why in program['refused'].items():
                        reasons['%s: %s' % (out, why.split(':')[0])] += count
                    for sources in program['inputs'].values():
                        for s in sources:
                            if s:
                                input_kinds[s['kind'] + (str(s.get('channel', '')) if s['kind'] == 'uv' else '')] += count
                    form = program.get('ends', {}).get('diffuse')
                    if form:
                        forms[form] += count
                    unlit = program.get('unlit') and 'glow' not in program['refused']
                    if unlit:
                        tally['unlit'] += count
                    if 'diffuse' in program['outputs'] or unlit:
                        outcome = 'translated'
                        if args.colours and 'diffuse' in program['outputs']:
                            colour = colours(p, owner, record, program, scene)
                            if colour:
                                ranked.append(dict(map=folder.name, material=record.get('name'), sections=count,
                                                   **colour))
                    else:
                        why = program['refused'].get('diffuse', 'no colour')
                        outcome = 'left as today'
                        reasons['colour: ' + why.split(':')[0]] += count
                        if len(examples[why.split(':')[0]]) < 10:
                            examples[why.split(':')[0]].append('%s %s: %s' % (folder.name, record.get('name'), why))
                except shader_slice.Refused as why:
                    outcome = 'left as today'
                    reasons['colour: ' + why.code] += count
                    if len(examples[why.code]) < 10:
                        examples[why.code].append('%s %s: %s' % (folder.name, record.get('name'), why))
                except (FormatError, OSError, KeyError, ValueError) as error:
                    outcome = 'unreadable'
                    if len(examples['unreadable']) < 10:
                        examples['unreadable'].append('%s %s: %s' % (folder.name, record.get('name'), error))
            tally[outcome] += count
            totals[outcome] += count
            by_material[outcome] += 1
        print('%-28s %s' % (folder.name, dict(tally)), flush=True)
    drawn = sum(totals.values())
    share = totals['translated'] / drawn if drawn else 0
    ranked.sort(key=lambda r: -r['dE'] * r['sections'])
    print('\nsections drawn %d, colour translated %d (%.1f%%)' % (drawn, totals['translated'], 100 * share))
    for k, v in totals.most_common():
        print('  %-16s %7d sections  %5d materials' % (k, v, by_material[k]))
    print('ends found (sections):', dict(ends.most_common()))
    print('colour mark forms (sections):', dict(forms.most_common()))
    print('inputs read (sections):', dict(input_kinds.most_common()))
    print('reasons (sections):')
    for k, v in reasons.most_common(30):
        print('  %7d  %s' % (v, k))
    if ranked:
        print('most changed colours (dE x sections):')
        for r in ranked[:15]:
            print('  %-24s %-60s dE %5.1f  today %s  white %s  grey %s' % (
                r['map'], r['material'], r['dE'], r['today'], r['white'], r['grey']))
    if args.out:
        Path(args.out).write_text(json.dumps(dict(
            pass_='b', sections=drawn, translated=totals['translated'], share=round(share, 4),
            bySection=dict(totals.most_common()), byMaterial=dict(by_material.most_common()),
            ends=dict(ends.most_common()), colourForms=dict(forms.most_common()),
            inputs=dict(input_kinds.most_common()), reasons=dict(reasons.most_common()),
            examples=dict(examples), mostChanged=ranked[:60]), indent=1) + '\n', encoding='utf-8', newline='\n')
        print('written', args.out)


def colours(p, owner, record, program, scene):
    """{'dE', 'today', 'white', 'grey'}: the program's mean colour on white and on mid-grey vertex colours, and
    today's texture's, in sRGB; None when a texture can't be read."""
    import numpy as np
    defaults = materials.resource_textures(p, owner)
    names = record.get('textureParameters') or {}
    samplers = {}
    for key, t in program['textures'].items():
        index = None
        if t.get('parameter') and names.get(t['parameter']) in p.by_name:
            index = p.by_name[names[t['parameter']]]
        elif t.get('index') is not None and t['index'] < len(defaults):
            index = defaults[t['index']]
        pixels = small_texture(p, index) if index and index > 0 else None
        if pixels is None:
            return None
        samplers[key] = sampler(pixels)
    white = program_colour(program, samplers, 1.0)
    grey = program_colour(program, samplers, 0.5)
    today = None
    diffuse = record.get('diffuse')
    if diffuse:
        found = KEY.match(str(diffuse))
        if found and not found.group(1):
            pixels = small_texture(p, int(found.group(2)))
            if pixels is not None:
                today = pixels[..., :3].reshape(-1, 3).mean(axis=0)
    if today is None:
        return None
    return dict(dE=round(float(np.linalg.norm(to_lab(white) - to_lab(today))), 1), today=srgb8(today),
                white=srgb8(white), grey=srgb8(grey))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('stage', choices=['a', 'b'])
    ap.add_argument('--colours', action='store_true', help='pass b: work out and rank the colours too (slower)')
    ap.add_argument('--cache', help='the cache of exported maps (default: the cache setting)')
    ap.add_argument('--out', help='the evidence file to write (JSON)')
    ap.add_argument('--maps', nargs='*')
    args = ap.parse_args(argv)
    if args.stage == 'a':
        pass_a(args)
    else:
        pass_b(args)


if __name__ == '__main__':
    main()
