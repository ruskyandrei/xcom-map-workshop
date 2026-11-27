"""A material's program on its export record (game-likeness plan, track A, stage A-S3): its compiled shaders'
slice (shader_slice.py) with the textures it samples exported, made where the exporter is told to
(`Exporter.programs`), so that the bake's albedo, which resolves materials through the exporter, never opens the
shader cache.

How a material finds its shader map (measured by the survey, F-167): a material instance with a static permutation
of its own is keyed by its static parameter set (the base material's ID with its switches' values and override
flags); anything else by the first such instance up its parents, else by its root material's own ID with no
switches. A match by the switches' values alone is taken where the exact one isn't there.

  Programs(keep)                                    the shader caches an export opens, kept in the editor's cache
  program(exporter, index, chain, record, textures) the program, its textures exported, or None (the reason in the
                                                    export's diagnostics)
  painted_colours(p, component, vertices)           a component's own painted colours (LOD 0), RGBA bytes a vertex
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'upk'))
import shader_cache  # noqa: E402
import shader_slice  # noqa: E402
import materials  # noqa: E402
from package import FormatError  # noqa: E402

SEE_THROUGH = ('BLEND_Translucent', 'BLEND_Additive', 'BLEND_Modulate')


class Programs:
    """The shader cache of each cooked folder an export reads (opened once, kept in `keep`, the editor's cache
    folder), and what an export says once."""

    def __init__(self, keep=None):
        self.keep = Path(keep) if keep else None
        self.caches = {}

    def cache_for(self, package_path):
        folder = Path(package_path).resolve().parent
        if folder not in self.caches:
            path = folder / shader_cache.FILE_NAME
            try:
                self.caches[folder] = shader_cache.open_cache(path, keep=self.keep) if path.is_file() else None
            except (OSError, ValueError, FormatError):
                self.caches[folder] = None
        return self.caches[folder]


def shader_key(p, index):
    """(how, base id, switches, owner) of a material: 'instance' from the nearest permutation instance up its
    parents, or 'root' from the root material's resource ID; `owner` is the object whose resource that is (its
    texture list gives a Texture expression's texture)."""
    current, seen, root = index, set(), index
    while current > 0:
        if current in seen:
            raise FormatError('a material parent cycle')
        seen.add(current)
        own = materials.static_parameters(p, current) if p.cls(current) != 'Material' else None
        if own is not None:
            return 'instance', own['base'], own['switches'], current
        root = current
        current = p.own(current, 'Parent', 0)
    if p.cls(root) not in ('Material', 'DecalMaterial'):
        raise FormatError('its root %s is a %s' % (p.name(root), p.cls(root)))
    return 'root', materials.resource_id(p, root), [], root


def match(cache, base, switches):
    """('exact' | 'values' | 'base' | 'none', the shader map or None)."""
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
    return 'base', None


def gives_colour(prog):
    """Whether a program gives the material's colour: its colour, or an unlit material's glow."""
    return 'diffuse' in prog['outputs'] or bool(prog.get('unlit') and 'glow' not in prog['refused'])


def program(exporter, index, chain, record, textures):
    """The material's program (shader_slice's form) with each texture it samples exported (`texture`, its export
    key, and `srgb`), or None: no shader cache, no shader map, or its colour not sliced, each said once in the
    export's diagnostics. `textures` is the material's texture parameters as the exporter resolved them (name to
    texture object), its defaults included."""
    if exporter.programs is None or not chain:
        return None
    p = exporter.p
    cache = exporter.programs.cache_for(p.path)
    if cache is None:
        return None
    name = p.name(index)
    try:
        how, base, switches, owner = shader_key(p, index)
        kind, smap = match(cache, base, switches)
        if smap is None:
            raise shader_slice.Refused('unmatched', 'no shader map of %s %s' % (
                shader_cache.guid_text(base), ', '.join('%s=%s' % (n, v) for n, v, _ in switches) or 'with no switches'))
        values = {'vectors': record.get('vectors') or {}, 'scalars': record.get('scalars') or {}}
        prog = shader_slice.slice_material(cache, smap, values, translucent=record.get('blend') in SEE_THROUGH)
        if not gives_colour(prog):
            raise shader_slice.Refused('colour', prog['refused'].get('diffuse') or prog['refused'].get('glow')
                                       or 'not sliced')
        defaults = materials.resource_textures(p, owner)
        for t in prog['textures'].values():
            source = textures.get(t['parameter']) if t.get('parameter') else None
            if not (isinstance(source, int) and source > 0) and t.get('index') is not None and t['index'] < len(defaults):
                source = defaults[t['index']]
            key = exporter.texture(source) if isinstance(source, int) and source > 0 else None
            if key is None:
                raise shader_slice.Refused('texture', 'its texture %s could not be read' % (
                    t.get('parameter') or '#%s' % t.get('index')))
            t['texture'] = key
            t['srgb'] = bool(exporter.textures[key].get('srgb'))
        prog['map'] = dict(base=smap.base_id, switches=[[n, v] for n, v, _ in smap.switches], matched=kind, by=how)
        return prog
    except shader_slice.Refused as why:
        exporter.warn(name, 'Drawn as before: its compiled shaders could not be followed (%s)' % why)
    except (FormatError, ValueError, KeyError, IndexError) as error:
        exporter.warn(name, 'Drawn as before: its compiled shaders could not be read (%s)' % error)
    return None


def painted_colours(p, component, vertices):
    """A placed piece's own painted vertex colours (its component's LOD 0 override colours, painted in the level
    editor) as RGBA bytes, four a vertex in the mesh's vertex order (the order mesh.py exports), or None when it has
    none or their count isn't the mesh's."""
    import native_fields
    try:
        r = p.native(component)
        lods = native_fields.mesh_lods(r, p)['lods']
    except (FormatError, ValueError, KeyError):
        return None
    if not lods or not lods[0].get('overrideVertexColors'):
        return None
    record = lods[0]
    data = p.data[record['overrideVertexColorsOffset']:record['overrideVertexColorsEnd']]
    # the flag (1), the stride and count (8), then the counted array: its stride (4), its count (4), its bytes
    if len(data) < 17:
        return None
    import struct
    stride, count = struct.unpack_from('<2I', data, 1)
    if stride != 4 or count != vertices or len(data) < 17 + 4 * count:
        return None
    raw = bytes(data[17:17 + 4 * count])
    out = bytearray(len(raw))
    out[0::4], out[1::4], out[2::4], out[3::4] = raw[2::4], raw[1::4], raw[0::4], raw[3::4]     # BGRA to RGBA
    return bytes(out)
