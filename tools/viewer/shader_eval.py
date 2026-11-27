"""A material's program (shader_slice.py) run on numbers: the tests' check of a slice, the survey's colours, and the
mean colour of a material where a tool wants one. The operations are SM3's, carried out as Direct3D 9 defines them,
on arrays of four components (numpy), so a program runs on many samples at once.

  run(program, inputs, textures, engine=None, time=None) -> {output: array (n, components)}

`inputs` gives each program input kind's values: {'uv0': (n, 2), 'uv1': ..., 'color': (n, 4), 'cameraVector':
(n, 3), 'worldPosition': (n, 4) (camera-relative), 'worldTangent', 'worldBinormal', 'worldNormal': (n, 3),
'tangentSign': (n,), 'vFace': (n,), 'vPos': (n, 2)}; `textures` {texture key: sample(uv (n, 2)) -> (n, 4)}, the program's
texture keys (t0, t1...). `time`, when given, works out the constants that move with time again.
"""
import math

import numpy as np

COMPONENTS = 'xyzw'


def _swizzled(value, swizzle, negate=False, absolute=False):
    out = value[:, [COMPONENTS.index(c) for c in swizzle]]
    if absolute:
        out = np.abs(out)
    if negate:
        out = -out
    return out


def apply(op, srcs, sat=False, texld=None, sample=None):
    """The operation on its sources (arrays (n, 4), swizzles applied) as all four destination components."""
    a = srcs[0] if srcs else None
    if op == 'mov':
        r = a.copy()
    elif op == 'add':
        r = a + srcs[1]
    elif op == 'sub':
        r = a - srcs[1]
    elif op == 'mul':
        r = a * srcs[1]
    elif op == 'mad':
        r = a * srcs[1] + srcs[2]
    elif op == 'lrp':
        r = a * srcs[1] + (1 - a) * srcs[2]
    elif op == 'min':
        r = np.minimum(a, srcs[1])
    elif op == 'max':
        r = np.maximum(a, srcs[1])
    elif op == 'slt':
        r = (a < srcs[1]).astype(np.float64)
    elif op == 'sge':
        r = (a >= srcs[1]).astype(np.float64)
    elif op == 'cmp':
        r = np.where(a >= 0, srcs[1], srcs[2])
    elif op == 'frc':
        r = a - np.floor(a)
    elif op == 'abs':
        r = np.abs(a)
    elif op == 'sgn':
        r = np.sign(a)
    elif op == 'rcp':
        x = a[:, :1]
        with np.errstate(divide='ignore'):
            r = np.repeat(np.where(x == 0, np.inf, 1.0 / np.where(x == 0, 1, x)), 4, axis=1)
    elif op == 'rsq':
        x = np.abs(a[:, :1])
        with np.errstate(divide='ignore'):
            r = np.repeat(np.where(x == 0, np.inf, 1.0 / np.sqrt(np.where(x == 0, 1, x))), 4, axis=1)
    elif op == 'exp':
        r = np.repeat(np.exp2(a[:, :1]), 4, axis=1)
    elif op == 'log':
        x = np.abs(a[:, :1])
        with np.errstate(divide='ignore'):
            r = np.repeat(np.where(x == 0, -np.inf, np.log2(np.where(x == 0, 1, x))), 4, axis=1)
    elif op == 'pow':
        x, y = np.abs(a[:, :1]), srcs[1][:, :1]
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            r = np.repeat(np.where(x == 0, np.where(y > 0, 0.0, 1.0), np.power(np.where(x == 0, 1, x), y)), 4, axis=1)
    elif op == 'dp3':
        r = np.repeat((a[:, :3] * srcs[1][:, :3]).sum(axis=1, keepdims=True), 4, axis=1)
    elif op == 'dp4':
        r = np.repeat((a * srcs[1]).sum(axis=1, keepdims=True), 4, axis=1)
    elif op == 'dp2add':
        r = np.repeat((a[:, :2] * srcs[1][:, :2]).sum(axis=1, keepdims=True) + srcs[2][:, :1], 4, axis=1)
    elif op == 'nrm':                          # every component scaled by 1 / the length of xyz
        f = 1.0 / np.sqrt(np.maximum((a[:, :3] ** 2).sum(axis=1, keepdims=True), 1e-30))
        r = a * f
    elif op == 'crs':
        c = np.cross(a[:, :3], srcs[1][:, :3])
        r = np.concatenate([c, np.zeros((len(a), 1))], axis=1)
    elif op == 'sincos':
        x = a[:, :1]
        r = np.concatenate([np.cos(x), np.sin(x), np.zeros((len(a), 2))], axis=1)
    elif op == 'texld':
        coords = a[:, :2]
        if texld == 'project':
            with np.errstate(divide='ignore', invalid='ignore'):
                coords = coords / a[:, 3:4]
        r = np.asarray(sample(coords), dtype=np.float64)
    elif op in ('dsx', 'dsy'):
        r = np.zeros_like(a)                     # one sample has no neighbours
    else:
        raise ValueError('operation %s' % op)
    if sat:
        r = np.clip(r, 0.0, 1.0)
    return r


def constant_value(record, time=None):
    """A program constant's four values, worked out again at `time` when it moves with time."""
    if time is None or not ({'vector', 'scalars'} & set(record)):
        return list(record['value'])
    import shader_slice
    from_json = shader_slice.expr_from_json
    if 'vector' in record:
        return shader_slice.evaluate_uniform(from_json(record['vector']), {}, time)
    out = list(record['value'])
    for k, e in enumerate(record['scalars']):
        if e is not None:
            out[k] = shader_slice.evaluate_uniform(from_json(e), {}, time)[0]
    return out


def input_values(sources, inputs, n):
    """A program input register's four components as an array (n, 4)."""
    out = np.zeros((n, 4))
    for c, src in enumerate(sources):
        if src is None:
            continue
        kind = src['kind']
        if kind == 'const':
            out[:, c] = src['value']
        elif kind == 'uv':
            uv = inputs.get('uv%d' % src['channel'])
            if uv is None:
                raise ValueError('no UV channel %d given' % src['channel'])
            out[:, c] = uv[:, src['component']] * src['scale'] + src['bias']
        elif kind == 'color':
            out[:, c] = inputs['color'][:, src['component']] * src['scale'] + src['bias']
        elif kind in ('cameraVector', 'worldPosition', 'worldTangent', 'worldBinormal', 'worldNormal'):
            out[:, c] = inputs[kind][:, src['component']] * src.get('scale', 1.0)
        elif kind == 'tangentSign':
            out[:, c] = inputs.get('tangentSign', np.ones(n)) * src.get('scale', 1.0)
        elif kind == 'vFace':
            out[:, c] = inputs.get('vFace', np.ones(n))
        elif kind == 'vPos':
            out[:, c] = inputs['vPos'][:, src['component']] if src['component'] < 2 else 0
        else:
            raise ValueError('an input of kind %s' % kind)
    return out


def run(program, inputs, textures, engine=None, time=None, n=None):
    """{output name: array (n, its mask's length)} of the program on the samples given."""
    if n is None:
        n = next((len(v) for v in inputs.values()), 1)
    regs = {}
    for name, sources in program['inputs'].items():
        if any(s and s.get('kind') == 'refused' for s in sources):
            continue
        regs[name] = input_values(sources, inputs, n)
    for name, record in program['constants'].items():
        value = constant_value(record, time)
        if record.get('engine') and engine and record['engine'] in engine:
            value = engine[record['engine']]
        regs[name] = np.tile(np.asarray(value, dtype=np.float64), (n, 1))
    for row in program['code']:
        srcs = []
        sample = None
        for s in row['s']:
            if s['r'].startswith('t'):
                sample = textures[s['r']]
                srcs.append(np.zeros((n, 4)))
                continue
            value = regs.get(s['r'])
            if value is None:
                value = np.zeros((n, 4))
            srcs.append(_swizzled(value, s['w'], s.get('n'), s.get('a')))
        result = apply(row['op'], srcs, row.get('sat'), row.get('texld'), sample)
        dest = regs.setdefault(row['d'], np.zeros((n, 4)))
        for c in row['m']:
            k = COMPONENTS.index(c)
            dest[:, k] = result[:, k]
    out = {}
    for name, o in program['outputs'].items():
        if 'value' in o:
            out[name] = np.tile(np.asarray(o['value'], dtype=np.float64), (n, 1))
            continue
        value = regs.get(o['r'], np.zeros((n, 4)))
        out[name] = value[:, [COMPONENTS.index(c) for c in o['m']]]
    return out
