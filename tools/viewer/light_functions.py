"""A light's light function on its export record (game-likeness plan, stage F1): the material the game draws on a light
to change its brightness as time goes (a pulse, a flicker), as a program the page runs each frame in the Game look.

A light component's `Function` names a `LightFunction` whose `SourceMaterial` the game draws on the light: its
compiled light function shader (`FLightFunctionPixelShader` of the material's shader map) gives the factor the light
is multiplied by, sliced by shader_slice.slice_light_function. A light function with no material changes nothing,
so its light gets no record. One the slice refuses (a pattern projected from the light, which differs from place to
place), whose material is in another package or is an instance (its own values are not read here), is drawn steady,
and said once in the export's diagnostics.

  light_function(p, component, programs) -> dict(material, program, moves), or None; shader_slice.Refused
  add(p, lights, programs, warn)          each light record of `lights` (the package's) with a light function gains
                                          `lightFunction`
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'upk'))
import material_programs  # noqa: E402
import shader_cache  # noqa: E402
import shader_slice  # noqa: E402
from package import FormatError  # noqa: E402


def light_function(p, component, programs):
    """The light function of light component `component` as the page draws it: dict(material (its path), program (a
    program whose output `light` is the factor, r, g, b), moves (whether it changes with time)), or None where the
    light has none, its light function names no material or no shader cache is had. Refused with the reason where it
    can't be followed."""
    fn = p.effective(component, 'Function', 0)
    if not fn:
        return None
    if fn < 0:
        raise shader_slice.Refused('package', 'its light function %s is in another package' % p.name(fn))
    source = p.effective(fn, 'SourceMaterial', 0)
    if not source:
        return None
    if source < 0:
        raise shader_slice.Refused('package', 'its material %s is in another package' % p.name(source))
    if p.cls(source) != 'Material':
        raise shader_slice.Refused('instance', 'its material %s is a %s' % (p.name(source), p.cls(source)))
    cache = programs.cache_for(p.path) if programs is not None else None
    if cache is None:
        return None
    how, base, switches, owner = material_programs.shader_key(p, source)
    kind, smap = material_programs.match(cache, base, switches)
    if smap is None:
        raise shader_slice.Refused('unmatched', 'no shader map of %s' % shader_cache.guid_text(base))
    program = shader_slice.slice_light_function(cache, smap, {})
    moves = any({'vector', 'scalars'} & set(c) for c in program['constants'].values())
    return dict(material=p.name(source), program=program, moves=moves)


def add(p, lights, programs, warn=None):
    """`lightFunction` on each record of `lights` whose component has a light function the page can draw; each one
    that can't be followed said through warn(source, message)."""
    for record in lights:
        ci = p.by_name.get(record['component'])
        if not ci:
            continue
        try:
            found = light_function(p, ci, programs)
        except shader_slice.Refused as why:
            if warn:
                warn(record['component'], 'Drawn steady: its light function could not be followed (%s)' % why)
            continue
        except (FormatError, ValueError, KeyError, IndexError) as error:
            if warn:
                warn(record['component'], 'Drawn steady: its light function could not be read (%s)' % error)
            continue
        if found:
            record['lightFunction'] = found
    return lights
