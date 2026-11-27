"""A material's program: the part of its compiled shaders that makes its colour, highlight, normal, glow, cut-out and
opacity, sliced out of the game's SM3 bytecode (the game-likeness plan, track A, stage A-S2; F-167).

The material's shader map (shader_cache.py) holds its shaders for each vertex factory. For a mesh (the local vertex
factory) this takes:
- the base pass without a lightmap (`TBasePassPixelShaderFNoLightMapPolicy...`, the fewest engine terms) for the
  colour, the glow, the cut-out and the opacity;
- a light pass (`TLightPixelShaderFPointLightPolicyFNoStaticShadowingPolicy...`) for the highlight and its power;
- the base pass with a lightmap texture (`...FDirectionalLightMapTexturePolicy...`) for the normal, which there is
  dotted with the lightmap's three fixed directions;
each with its paired vertex shader.

Where each output ends (`ENDS`):
- colour: the value the shader scales by `DiffuseOverrideParameter`'s w and adds its xyz to (the engine's override
  for its view modes), in whatever form (mad, mul then add);
- highlight: the same with `SpecularOverrideParameter`; its power is the exponent of the `pow` whose result scales it;
- normal: the register dotted with the lightmap basis constants;
- glow: the base pass's colour output with every engine light term set to zero and folded;
- cut-out: the value `texkill` tests in the base pass;
- opacity (a see-through material): the base pass's output alpha.

From each end the slice goes backward through the registers a component at a time (masks and swizzles followed)
to texture reads, the pixel shader's inputs, uniform vectors and scalars, and literals. Each pixel input is followed
through the vertex shader to what it is made of: a mesh UV channel times a constant, the vertex colour, the
tangent-space camera vector. What it can't follow (a branch, an instruction or input not supported, an engine
constant it has no value for, a cube texture) refuses that output with a reason; the export then draws the material
as today and says why.

  slice_material(cache, shader_map, values) -> program dict (PROGRAM_VERSION), or Refused
  evaluate_uniform(expr, values, time=0) -> [r, g, b, a]

A particle's material (game-likeness plan, track E, stage E1) is sliced the same way from its shaders for the
particle vertex factory its emitter draws with (`slice_material(..., factory=, particle=True)`): only the base pass
(colour, glow, cut-out, opacity), its streams named for what the particle gives (its colour, its sub-images' UVs and
blend, its dynamic parameter: `STREAMS`), and the screen's own inputs a soft particle reads: its clip-space position
and the scene's depth (`SceneColorTexture`'s alpha, and `MinZ_MaxZRatio`, given so that the shader's sum is the
depth itself).

The program's form is written down in research/editor-contracts.md ("A material's program").
"""
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'upk'))
import sm3  # noqa: E402

PROGRAM_VERSION = 1
FACTORY = 'FLocalVertexFactory'
COMPONENTS = 'xyzw'
FLOW = {'if', 'else', 'endif', 'loop', 'endloop', 'rep', 'endrep', 'call', 'callnz', 'ret', 'label', 'break'}
# Operations the page and shader_eval.py carry out, one for one.
SUPPORTED = {'mov', 'add', 'sub', 'mad', 'mul', 'rcp', 'rsq', 'dp3', 'dp4', 'min', 'max', 'slt', 'sge', 'exp', 'log',
             'lrp', 'frc', 'pow', 'abs', 'nrm', 'cmp', 'dp2add', 'texld', 'sincos', 'crs', 'sgn', 'dsx', 'dsy'}
COMPONENTWISE = {'mov', 'add', 'sub', 'mad', 'mul', 'min', 'max', 'slt', 'sge', 'lrp', 'frc', 'abs', 'cmp', 'sgn',
                 'dsx', 'dsy'}
SCALAR = {'rcp', 'rsq', 'exp', 'log', 'pow'}
# The lightmap's three fixed directions (the basis the normal is dotted with in the lightmap pass)
BASIS = (0.816496611, 0.577350259, -0.707106769, -0.408248305, 0.707106769)
# Engine constants a program may read, as the page gives them: (input name, value when sliced offline)
ENGINE = {
    'CameraWorldPos': ('cameraWorldPos', [0, 0, 0, 0]),
    'ObjectWorldPositionAndRadius': ('objectWorldPos', [0, 0, 0, 1]),
    'TwoSidedSign': ('twoSidedSign', [1, 1, 1, 1]),
    'ScreenPositionScaleBias': ('screenPositionScaleBias', [0.5, -0.5, 0.5, 0.5]),
}
# What a particle's shaders read of the screen (a soft particle's fade against what is behind it): the scene's depth
# is SceneColorTexture's alpha in UE3, turned into a distance by MinZ_MaxZRatio; with the ratio (-1, 1) that sum is
# 1 / the alpha, so the page gives the alpha as 1 / the depth behind (the offline value: nothing behind, no fade)
SCREEN_ENGINE = {'MinZ_MaxZRatio': ('minZMaxZRatio', [-1.0, 1.0, 0.0, 0.0])}
SCREEN_TEXTURES = {'SceneColorTexture': 'sceneDepth'}
# A particle vertex factory's streams (UE3's ParticleSpriteVertexFactory, ParticleSubUVVertexFactory and their
# dynamic-parameter and beam kin, read off their vertex shaders): texcoord0 is the corner's UV in the first sub-image
# (xy) and in the second (zw); the rest by name. A mesh particle draws with the mesh's own (local) vertex factory.
STREAMS = {
    'FParticleVertexFactory': {'texcoord1': 'particleColor'},
    'FParticleSubUVVertexFactory': {'texcoord1': 'particleColor', 'texcoord2': 'subImageLerp'},
    'FParticleDynamicParameterVertexFactory': {'texcoord1': 'particleColor', 'texcoord3': 'dynamic'},
    'FParticleSubUVDynamicParameterVertexFactory': {'texcoord1': 'particleColor', 'texcoord2': 'subImageLerp',
                                                    'texcoord3': 'dynamic'},
    'FParticleBeamTrailVertexFactory': {'texcoord1': 'particleColor'},
    'FParticleBeamTrailDynamicParameterVertexFactory': {'texcoord1': 'particleColor', 'texcoord2': 'dynamic'},
}
# A mesh particle's own values reach its material as vector parameters the engine sets each particle (UE3's mesh
# emitter): a particle slice reads them as the particle's inputs
MESH_PARTICLE = {'MeshEmitterVertexColor': 'particleColor', 'MeshEmitterDynamicParameter': 'dynamic'}
# The vertex shader's height fog constants: an interpolant made from them is the fog
FOG_CONSTANTS = {'FogInScattering', 'SharedFogParameter0', 'SharedFogParameter1', 'SharedFogParameter2',
                 'SharedFogParameter3', 'FogMaxHeight', 'bUseExponentialHeightFog', 'FogDistanceScale',
                 'FogExtinctionDistance', 'FogStartDistance', 'FogMinHeight'}
# Engine constants that are light or view terms: zero when the glow is worked out
LIGHT_TERMS = {'AmbientColorAndSkyFactor', 'UpperSkyColor', 'LowerSkyColor', 'LightColorAndFalloffExponent'}
# Engine constants that are neutral (identity) for the glow: the fog of war's tints and the fogs, the overrides
NEUTRAL = {'DiffuseOverrideParameter': [0, 0, 0, 1], 'SpecularOverrideParameter': [0, 0, 0, 1],
           # the fog of war as on a tile in view: TranslucentFOW's x is how much is seen (1), its y the have-seen
           # tint's share (0)
           'HaveSeenTintColor': [1, 1, 1, 1], 'OcclusionColor': [1, 1, 1, 1], 'TranslucentFOW': [1, 0, 0, 0],
           'ExponentialFog': [0, 0, 0, 1], 'OcclusionPercentage': [0, 0, 0, 0]}


class Refused(Exception):
    """An output the slice can't give, with its reason (a short code and what it found)."""

    def __init__(self, code, detail=''):
        super().__init__('%s: %s' % (code, detail) if detail else code)
        self.code, self.detail = code, detail


# ---------------------------------------------------------------------------------------------------------------
# Uniform expressions

def evaluate_uniform(expr, values, time=0.0):
    """An expression's value ([r, g, b, a]) with the material's parameter values ({'vectors', 'scalars'}) and the
    time. A kind it can't work out raises Refused."""
    k, f, a = expr.kind, expr.fields, expr.args
    ev = lambda e: evaluate_uniform(e, values, time)
    if k == 'Constant':
        return list(f['value'])
    if k == 'VectorParameter':
        v = (values.get('vectors') or {}).get(f['name'])
        return [float(x) for x in (v if v is not None else f['default'])][:4] + [0.0] * (4 - len(v if v is not None else f['default']))
    if k == 'ScalarParameter':
        v = (values.get('scalars') or {}).get(f['name'])
        return [float(v if v is not None else f['default'])] * 4
    if k == 'XComVectorParameter':
        return [1.0, 1.0, 1.0, 1.0]            # a unit's own colour: none on a map's pieces
    if k in ('Time', 'RealTime'):
        return [float(time)] * 4
    if k == 'Sine':
        x = ev(a[0])[0]
        s = math.cos(x) if f.get('cosine') else math.sin(x)
        return [s] * 4
    one = {'SquareRoot': lambda x: math.sqrt(max(x, 0.0)), 'Abs': abs, 'Floor': math.floor,
           'Frac': lambda x: x - math.floor(x), 'Periodic': lambda x: x - math.floor(x), 'Ceil': math.ceil}
    if k in one:
        return [float(one[k](x)) for x in ev(a[0])]
    if k == 'Length':
        x = ev(a[0])
        return [math.sqrt(sum(c * c for c in x[:3]))] * 4
    if k in ('Min', 'Max', 'Fmod'):
        x, y = ev(a[0]), ev(a[1])
        op = {'Min': min, 'Max': max, 'Fmod': lambda p, q: math.fmod(p, q) if q else 0.0}[k]
        return [float(op(p, q)) for p, q in zip(x, y)]
    if k == 'Clamp':
        x, lo, hi = ev(a[0]), ev(a[1]), ev(a[2])
        return [min(max(p, l), h) for p, l, h in zip(x, lo, hi)]
    if k == 'FoldedMath':
        x, y = ev(a[0]), ev(a[1])
        op = f['op']
        if op == 'add':
            return [p + q for p, q in zip(x, y)]
        if op == 'sub':
            return [p - q for p, q in zip(x, y)]
        if op == 'mul':
            return [p * q for p, q in zip(x, y)]
        if op == 'div':
            return [p / q if q else 0.0 for p, q in zip(x, y)]
        if op == 'dot':
            return [sum(p * q for p, q in zip(x[:3], y[:3]))] * 4
        raise Refused('uniform', 'folded maths %r' % op)
    if k == 'AppendVector':
        x, y = ev(a[0]), ev(a[1])
        n = f['componentsA']
        return (x[:n] + y)[:4] + [0.0] * max(0, 4 - n - len(y))
    raise Refused('uniform', 'an expression of kind %s' % k)


def uniform_name(expr):
    """A short name for a uniform expression: its parameter's, else its kind's (a program's uniform keeps it)."""
    if 'name' in expr.fields:
        return expr.fields['name']
    if expr.kind == 'XComVectorParameter':
        return 'XCom%d' % expr.fields['slot']
    inner = [uniform_name(a) for a in expr.args]
    return '%s(%s)' % (expr.kind, ','.join(inner)) if inner else expr.kind


def depends_on_time(expr):
    return expr.kind in ('Time', 'RealTime') or any(depends_on_time(a) for a in expr.args)


# ---------------------------------------------------------------------------------------------------------------
# Reading a shader's instructions

def reads(ins, comps):
    """[(register, component)] that the instruction reads to make the given components of its destination."""
    op, out = ins.op, []
    srcs = ins.srcs
    if op in COMPONENTWISE:
        for s in srcs:
            out += [(s.reg, s.swizzle[c]) for c in comps]
    elif op in SCALAR:
        out += [(s.reg, s.swizzle[0]) for s in srcs]
    elif op == 'dp3':
        for s in srcs:
            out += [(s.reg, s.swizzle[k]) for k in range(3)]
    elif op == 'dp4':
        for s in srcs:
            out += [(s.reg, s.swizzle[k]) for k in range(4)]
    elif op == 'dp2add':
        out += [(srcs[0].reg, srcs[0].swizzle[k]) for k in range(2)]
        out += [(srcs[1].reg, srcs[1].swizzle[k]) for k in range(2)]
        out.append((srcs[2].reg, srcs[2].swizzle[0]))
    elif op == 'nrm':
        out += [(srcs[0].reg, srcs[0].swizzle[k]) for k in range(3)]
    elif op == 'crs':
        for s in srcs:
            out += [(s.reg, s.swizzle[k]) for k in range(3)]
    elif op == 'sincos':
        out.append((srcs[0].reg, srcs[0].swizzle[0]))
    elif op in ('texld', 'texldl'):
        coords = (0, 1, 3) if (ins.project or ins.bias or op == 'texldl') else (0, 1)
        out += [(srcs[0].reg, srcs[0].swizzle[k]) for k in coords]
        out.append((srcs[1].reg, 0))
    else:
        raise Refused('instruction', op)
    for s in srcs:
        if s.relative is not None:
            raise Refused('instruction', 'an indexed read')
    return out


class Flow:
    """A shader's instructions with their nesting depth under branches and loops."""

    def __init__(self, shader):
        self.shader = shader
        self.code = [i for i in shader.instructions if i.op not in ('dcl', 'def', 'defi', 'defb')]
        self.depth, d = [], 0
        for ins in self.code:
            if ins.op in ('endif', 'endloop', 'endrep', 'else'):
                d -= 1
            self.depth.append(d)
            if ins.op in ('if', 'loop', 'rep', 'else'):
                d += 1
        self.literals = shader.literals()
        self.inputs = {}                         # register -> dcl instruction
        for ins in shader.declarations():
            self.inputs[ins.dest.reg] = ins

    def constant(self, reg):
        """The constant table entry of a c (or s, b, i) register, or None."""
        sets = {'c': 'float4', 's': 'sampler', 'b': 'bool', 'i': 'int4'}
        return self.shader.constant_at(sets.get(reg.kind, ''), reg.index)


def backward(flow, end, wanted, lod=False):
    """The instructions (indices, in order) that make `wanted` ({(register, component)}) as they stand before
    instruction `end`, and the registers and components read from outside them (the leaves). Refused on a branch,
    a predicate or an instruction not supported in the way; `lod`: a texture read at a level (`texldl`, a particle's
    read of the scene's depth) is followed too."""
    needed = set(wanted)
    kept = []
    for i in range(end - 1, -1, -1):
        ins = flow.code[i]
        if ins.dest is None or ins.op in FLOW or ins.op == 'texkill':
            continue
        reg = ins.dest.reg
        hit = [COMPONENTS.index(c) for c in ins.dest.mask if (reg, COMPONENTS.index(c)) in needed]
        if not hit:
            continue
        if flow.depth[i] > 0:
            raise Refused('branch', 'the slice runs through a branch or loop')
        if ins.predicate is not None:
            raise Refused('predicate')
        if ins.op not in SUPPORTED and not (lod and ins.op == 'texldl'):
            raise Refused('instruction', ins.op)
        if ins.op == 'sincos':
            hit = [c for c in hit]
        for c in hit:
            needed.discard((reg, c))
        needed |= set(reads(ins, hit))
        kept.append(i)
    kept.reverse()
    return kept, needed


# ---------------------------------------------------------------------------------------------------------------
# The vertex shader: what each output is made of

class Affine:
    """A sum of input components times constants, plus a constant; `inputs` {(usage, index, component): factor}."""
    __slots__ = ('terms', 'const')

    def __init__(self, terms=None, const=0.0):
        self.terms, self.const = dict(terms or {}), float(const)

    def scaled(self, k):
        return Affine({t: v * k for t, v in self.terms.items()}, self.const * k)

    def plus(self, other):
        terms = dict(self.terms)
        for t, v in other.terms.items():
            terms[t] = terms.get(t, 0.0) + v
        return Affine({t: v for t, v in terms.items() if v != 0.0}, self.const + other.const)

    def constant_value(self):
        return None if self.terms else self.const


class Complex:
    """A value the vertex shader makes from more than inputs and literals; `uses` what it reads (constant names,
    input usages)."""
    __slots__ = ('uses',)

    def __init__(self, uses=()):
        self.uses = frozenset(uses)


class Clip(Complex):
    """A copy of the clip-space position the vertex shader writes (its `component`), as an interpolant: what the
    pixel shader reads for its place on the screen."""
    __slots__ = ('component',)

    def __init__(self, component, uses=()):
        super().__init__(uses)
        self.component = component


def _join(*values):
    uses = set()
    for v in values:
        if isinstance(v, Complex):
            uses |= v.uses
        else:
            uses |= {('input', t[0]) for t in v.terms}
    return Complex(uses)


def vertex_outputs(vs, literal_abs=False):
    """{(usage, usage index, component): Affine or Complex} of a vertex shader's outputs, by running it on symbols.
    An output that is the position's own value (a copy of the register the position is written from) is a `Clip`.
    `literal_abs`: a literal read through abs() is the literal's size (a particle slice's: the local factory's
    see-through base pass reads its UVs times abs(1, 0); a piece's slice still refuses it)."""
    flow = Flow(vs)
    state = {}

    def value(reg, comp):
        if reg.kind == 'v':
            dcl = flow.inputs.get(reg)
            if dcl is None:
                return Complex({('input', 'undeclared')})
            return Affine({(dcl.usage, dcl.usage_index, comp): 1.0})
        if reg.kind == 'c':
            lit = flow.literals.get(reg)
            if lit is not None:
                return Affine(const=lit[comp])
            entry = flow.constant(reg)
            return Complex({('constant', entry.name if entry else 'c%d' % reg.index)})
        return state.get((reg, comp), Complex({('unset', reg.name())}))

    def src(s, comp):
        v = value(s.reg, s.swizzle[comp])
        if s.mod in ('neg',):
            return v.scaled(-1.0) if isinstance(v, Affine) else v
        if literal_abs and s.mod in ('abs', 'abs_neg') and isinstance(v, Affine) and v.constant_value() is not None:
            return Affine(const=-abs(v.const) if s.mod == 'abs_neg' else abs(v.const))
        if s.mod:
            return v if isinstance(v, Complex) else _join(v)
        return v

    def mul(a, b):
        if isinstance(a, Affine) and isinstance(b, Affine):
            if a.constant_value() is not None:
                return b.scaled(a.const)
            if b.constant_value() is not None:
                return a.scaled(b.const)
        return _join(a, b)

    def add(a, b):
        if isinstance(a, Affine) and isinstance(b, Affine):
            return a.plus(b)
        return _join(a, b)

    for i, ins in enumerate(flow.code):
        if ins.dest is None or ins.op in FLOW:
            continue
        mask = [COMPONENTS.index(c) for c in ins.dest.mask]
        results = {}
        for c in mask:
            if flow.depth[i] > 0 or ins.predicate is not None:
                parts = [src(sv, k) for sv in ins.srcs for k in range(4)]
                results[c] = Complex(_join(*parts).uses | {('branch', '')}) if parts else Complex({('branch', '')})
                continue
            s = ins.srcs
            if ins.op == 'mov':
                r = src(s[0], c)
            elif ins.op == 'add':
                r = add(src(s[0], c), src(s[1], c))
            elif ins.op == 'sub':
                r = add(src(s[0], c), src(s[1], c).scaled(-1) if isinstance(src(s[1], c), Affine) else src(s[1], c))
            elif ins.op == 'mul':
                r = mul(src(s[0], c), src(s[1], c))
            elif ins.op == 'mad':
                r = add(mul(src(s[0], c), src(s[1], c)), src(s[2], c))
            elif ins.op in ('dp3', 'dp4'):
                n = 3 if ins.op == 'dp3' else 4
                r = Affine()
                for k in range(n):
                    r = add(r, mul(src(s[0], k), src(s[1], k)))
            else:
                parts = []
                for sv in s:
                    parts += [src(sv, k) for k in range(4)]
                r = _join(*parts)
            if ins.dest.sat and isinstance(r, Affine) and r.terms:
                r = _join(r)
            results[c] = r
        for c, r in results.items():
            state[(ins.dest.reg, c)] = r
    out = {}
    for reg, dcl in flow.inputs.items():
        if reg.kind == 'o':
            for c in range(4):
                if (reg, c) in state:
                    out[(dcl.usage, dcl.usage_index, c)] = state[(reg, c)]
    position = [out.get(('position', 0, c)) for c in range(4)]
    for key, v in out.items():
        if key[0] != 'position' and isinstance(v, Complex):
            same = next((c for c, w in enumerate(position) if w is v), None)
            if same is not None:
                out[key] = Clip(same, v.uses)
    return out


def numeric_kinds(vs, samples=6, seed=845):
    """{(usage, usage index, component): input source} for the vertex shader's outputs that match a known engine
    value when the shader is run on random inputs and constants: the camera-relative world position
    (`worldPosition`, LocalToWorld times the position: the pixel shader adds CameraWorldPos for the absolute one),
    the tangent frame in the world (`worldTangent`, `worldBinormal`, `worldNormal`), its handedness
    (`tangentSign`) and the tangent-space camera vector (`cameraVector`). UE3's local vertex factory: the packed
    normal and tangent are bytes (b / 127.5 - 1), binormal = cross(normal, tangent) * normal.w, tangent made again
    as cross(binormal, normal) * normal.w."""
    import numpy as np
    import shader_eval
    rng = np.random.default_rng(seed)
    flow = Flow(vs)
    regs, by_usage = {}, {}
    for reg, dcl in flow.inputs.items():
        if reg.kind != 'v' or dcl.usage is None:
            continue
        if dcl.usage == 'position':
            v = np.concatenate([rng.uniform(-300, 300, (samples, 3)), np.ones((samples, 1))], axis=1)
        elif dcl.usage in ('tangent', 'normal', 'binormal'):
            v = rng.integers(0, 256, (samples, 4)).astype(np.float64)
        elif dcl.usage == 'color':
            v = rng.random((samples, 4))
        else:
            v = rng.uniform(-2, 2, (samples, 4))
        regs[reg] = v
        by_usage[dcl.usage] = v
    constants = {}
    for c in vs.constants.values():
        if c.set != 'float4':
            continue
        for k in range(c.count):
            reg = sm3.Register('c', c.index + k)
            value = np.tile(rng.uniform(-1, 1, (1, 4)), (samples, 1))
            regs[reg] = value
            constants.setdefault(c.name, []).append(value)
    for reg, values in flow.literals.items():
        if reg.kind == 'c':
            regs[reg] = np.tile(np.asarray(values[:4], dtype=np.float64), (samples, 1))
    for i, ins in enumerate(flow.code):
        if ins.dest is None or ins.op in FLOW:
            continue
        unknown = (flow.depth[i] > 0 or ins.predicate is not None or ins.op not in SUPPORTED
                   or ins.op in ('texld', 'texldl'))
        if unknown:
            dest = regs.setdefault(ins.dest.reg, np.zeros((samples, 4)))
            for c in ins.dest.mask:
                dest[:, COMPONENTS.index(c)] = np.nan
            continue
        srcs = []
        for s in ins.srcs:
            value = regs.get(s.reg, np.zeros((samples, 4)))
            if s.relative is not None:
                value = np.full((samples, 4), np.nan)
            value = value[:, list(s.swizzle)]
            if s.mod in ('abs', 'abs_neg'):
                value = np.abs(value)
            if s.mod in ('neg', 'abs_neg'):
                value = -value
            srcs.append(value)
        result = shader_eval.apply(ins.op, srcs, ins.dest.sat)
        dest = regs.setdefault(ins.dest.reg, np.zeros((samples, 4)))
        for c in ins.dest.mask:
            dest[:, COMPONENTS.index(c)] = result[:, COMPONENTS.index(c)]
    candidates = {}
    position = by_usage.get('position')
    local = constants.get('LocalToWorld')
    if position is not None and local and len(local) == 4:
        world = sum(local[k] * position[:, k:k + 1] for k in range(4))
        for c in range(4):
            candidates[('worldPosition', c)] = world[:, c]
        normal, tangent = by_usage.get('normal'), by_usage.get('tangent')
        if normal is not None and tangent is not None:
            z = normal / 127.5 - 1
            t = tangent / 127.5 - 1
            y = np.cross(z[:, :3], t[:, :3]) * z[:, 3:4]
            x = np.cross(y, z[:, :3]) * z[:, 3:4]
            for name, axis in (('worldTangent', x), ('worldBinormal', y), ('worldNormal', z[:, :3])):
                w = sum(local[k][:, :3] * axis[:, k:k + 1] for k in range(3))
                for c in range(3):
                    candidates[(name, c)] = w[:, c]
            flip = constants.get('LocalToWorldRotDeterminantFlip')
            if flip:
                candidates[('tangentSign', 0)] = z[:, 3] * flip[0][:, 0]
            camera = constants.get('CameraPositionVS')
            inverse = constants.get('WorldToLocal')
            if camera and inverse and len(inverse) >= 3:
                rel = camera[0][:, :3] - world[:, :3] * camera[0][:, 3:4]
                cl = sum(inverse[k][:, :3] * rel[:, k:k + 1] for k in range(3))
                for c, axis in enumerate((x, y, z[:, :3])):
                    candidates[('cameraVector', c)] = (axis * cl).sum(axis=1)
    # the clip-space position (what the shader writes as its position, copied to an interpolant for the screen's
    # place: a soft particle's read of the depth behind it), last, so that it names only what nothing else does
    for reg, dcl in flow.inputs.items():
        if reg.kind == 'o' and dcl.usage == 'position' and not dcl.usage_index and reg in regs:
            for c in range(4):
                if not np.isnan(regs[reg][:, c]).any():
                    candidates[('clipPosition', c)] = regs[reg][:, c].copy()
    out = {}
    for reg, dcl in flow.inputs.items():
        if reg.kind != 'o' or reg not in regs:
            continue
        for c in range(4):
            value = regs[reg][:, c]
            if np.isnan(value).any():
                continue
            for (kind, comp), cand in candidates.items():
                if np.allclose(value, cand, rtol=1e-6, atol=1e-6 * (1 + np.abs(cand).max())):
                    out[(dcl.usage, dcl.usage_index, c)] = {'kind': kind, 'component': comp}
                    break
                if np.allclose(value, -cand, rtol=1e-6, atol=1e-6 * (1 + np.abs(cand).max())) and np.abs(cand).max() > 0:
                    out[(dcl.usage, dcl.usage_index, c)] = {'kind': kind, 'component': comp, 'scale': -1.0}
                    break
    return out


def stream(factory, usage, index, comp):
    """A vertex stream's component as a program input source (before its scale and bias), or None: a mesh's UV
    channel or vertex colour (the local vertex factory), or what a particle factory's stream carries (`STREAMS`)."""
    named = STREAMS.get(factory)
    if named is None:
        if usage == 'texcoord':
            return {'kind': 'uv', 'channel': index, 'component': comp}
        if usage == 'color' and index == 1:
            return {'kind': 'color', 'component': comp}
        return None
    if usage == 'texcoord' and not index:
        return {'kind': 'uv', 'channel': comp // 2, 'component': comp % 2}
    kind = named.get('%s%s' % (usage, index or ''))
    return {'kind': kind, 'component': comp} if kind else None


def pixel_input(ps_dcl, comp, vs_out, part, kinds=None, factory=FACTORY, screen=False):
    """What a pixel shader input's component is, as a program input source: a stream's component (times a constant,
    plus one: `stream`), a constant, or one of numeric_kinds' engine values (`kinds`; the clip-space position only
    where the slice takes the screen's inputs, `screen`). Refused otherwise."""
    key = (ps_dcl.usage, ps_dcl.usage_index, comp)
    v = vs_out.get(key)
    if v is None:
        raise Refused('input', '%s%s.%s is not written by the vertex shader' % (ps_dcl.usage, ps_dcl.usage_index or '',
                                                                                 COMPONENTS[comp]))
    if isinstance(v, Affine):
        if not v.terms:
            return {'kind': 'const', 'value': v.const}
        if len(v.terms) == 1:
            (usage, index, c), k = next(iter(v.terms.items()))
            source = stream(factory, usage, index, c)
            if source is not None:
                return dict(source, scale=k, bias=v.const)
        raise Refused('input', '%s%s.%s mixes %s' % (ps_dcl.usage, ps_dcl.usage_index or '', COMPONENTS[comp],
                                                     sorted('%s%s' % (t[0], t[1] or '') for t in v.terms)))
    if screen and isinstance(v, Clip):
        return {'kind': 'clipPosition', 'component': v.component}
    if screen and factory in STREAMS and key[:2] == ('texcoord', 6) and comp < 3:
        # the base pass's slot for the tangent-space vector to the camera (numeric_kinds names it so for the local
        # factory; a particle factory's tangent frame is the sprite's own, which its relative reads hide from the run)
        return {'kind': 'cameraVector', 'component': comp}
    known = (kinds or {}).get(key)
    if known is not None and (screen or known['kind'] != 'clipPosition'):
        return dict(known)
    names = {u[1] for u in v.uses if u[0] == 'constant'}
    if names & FOG_CONSTANTS:
        # the height fog the vertex shader works out (colour in rgb, what is left of the scene in a): none here,
        # the editor draws the map's fog of its own (track C)
        return {'kind': 'const', 'value': 1.0 if comp == 3 else 0.0, 'fog': True}
    raise Refused('input', '%s%s.%s is made from %s' % (ps_dcl.usage, ps_dcl.usage_index or '', COMPONENTS[comp],
                                                        ', '.join(sorted(n for n in names)) or 'more than inputs'))


# ---------------------------------------------------------------------------------------------------------------
# A part: one end's slice as program instructions

class Part:
    """One pixel shader sliced from its ends: the kept instructions, renamed into the program's namespace."""

    def __init__(self, tag, flow, vs_out, uniforms, values, program, fold=None, kinds=None, factory=FACTORY,
                 screen=False):
        self.tag, self.flow, self.vs_out, self.uniforms = tag, flow, vs_out, uniforms
        self.kinds = kinds or {}
        self.factory, self.screen = factory, screen     # its streams' meaning; whether it takes the screen's inputs
        self.values, self.program, self.fold = values, program, fold or {}
        self.done = set()
        self.prefix = tag                         # the registers' prefix: the part's tag and the output's letter

    def name(self, reg):
        """The program's name for a register this part reads or writes."""
        if reg.kind == 'r':
            return '%sr%d' % (self.prefix, reg.index)
        if reg.kind in ('oC', 'oDepth'):           # an output written, read back as the glow or the opacity
            return '%so%d' % (self.prefix, reg.index)
        if reg.kind == 'v':
            return self.input(reg)
        if reg.kind in ('vFace', 'vPos'):
            return self.program_input(reg.kind, [{'kind': reg.kind, 'component': c} for c in range(4)])
        if reg.kind == 'c':
            return self.constant(reg)
        if reg.kind == 's':
            return self.texture(reg)
        raise Refused('register', reg.name())

    def program_input(self, key, sources):
        inputs = self.program['inputs']
        for name, have in inputs.items():
            if have == sources:
                return name
        name = 'i%d' % len(inputs)
        inputs[name] = sources
        return name

    def input(self, reg):
        dcl = self.flow.inputs.get(reg)
        if dcl is None or dcl.usage is None:
            raise Refused('input', 'undeclared %s' % reg.name())
        mask = [COMPONENTS.index(c) for c in dcl.dest.mask]
        sources = []
        for c in range(4):
            if c not in mask:
                sources.append(None)
                continue
            try:
                sources.append(pixel_input(dcl, c, self.vs_out, self.tag, self.kinds, self.factory, self.screen))
            except Refused as why:
                sources.append({'kind': 'refused', 'why': str(why)})
        return self.program_input(reg.name(), sources)

    def constant(self, reg):
        lit = self.flow.literals.get(reg)
        if lit is not None:
            return self.add_constant({'value': [float(x) for x in lit]})
        entry = self.flow.constant(reg)
        if entry is None:
            raise Refused('constant', 'c%d has no value' % reg.index)
        name = entry.name
        offset = reg.index - entry.index
        if name in self.fold:
            return self.add_constant({'value': list(self.fold[name])})
        if name.startswith('UniformPixelVector_'):
            n = int(name.rsplit('_', 1)[1]) + offset
            exprs = self.uniforms['pixelVectors']
            if n >= len(exprs):
                raise Refused('constant', '%s past the map\'s list' % name)
            e = exprs[n]
            if self.screen and e.kind == 'VectorParameter' and e.fields.get('name') in MESH_PARTICLE:
                kind = MESH_PARTICLE[e.fields['name']]
                return self.program_input(kind, [{'kind': kind, 'component': c} for c in range(4)])
            return self.add_uniform(e)
        if name.startswith('UniformPixelScalars_'):
            n = int(name.rsplit('_', 1)[1]) + offset
            exprs = self.uniforms['pixelScalars']
            parts = exprs[4 * n:4 * n + 4]
            value = [evaluate_uniform(e, self.values)[0] for e in parts] + [0.0] * (4 - len(parts))
            timed = [e.to_json() if depends_on_time(e) else None for e in parts]
            record = {'value': value, 'uniform': 'scalars%d' % n}
            if any(timed):
                record['scalars'] = timed
            return self.add_constant(record)
        if name in ENGINE:
            return self.add_constant({'value': list(ENGINE[name][1]), 'engine': ENGINE[name][0]})
        if self.screen and name in SCREEN_ENGINE:
            return self.add_constant({'value': list(SCREEN_ENGINE[name][1]), 'engine': SCREEN_ENGINE[name][0]})
        raise Refused('engine', name)

    def add_uniform(self, expr):
        # the material's own values stay uniforms (not folded), so that its instances share one program
        record = {'value': evaluate_uniform(expr, self.values), 'uniform': uniform_name(expr)}
        if depends_on_time(expr):
            record['vector'] = expr.to_json()
        return self.add_constant(record)

    def add_constant(self, record):
        constants = self.program['constants']
        for name, have in constants.items():
            if have == record:
                return name
        name = 'k%d' % len(constants)
        constants[name] = record
        return name

    def texture(self, reg):
        entry = self.flow.constant(reg)
        if entry is None:
            raise Refused('texture', 's%d is not named' % reg.index)
        name = entry.name
        if name.startswith('PixelTextureCube_'):
            raise Refused('cube', name)
        if self.screen and name in SCREEN_TEXTURES:
            record = {'engine': SCREEN_TEXTURES[name]}
        elif not name.startswith('PixelTexture2D_'):
            raise Refused('engine', name)
        else:
            n = int(name.rsplit('_', 1)[1])
            exprs = self.uniforms['textures2d']
            if n >= len(exprs):
                raise Refused('texture', '%s past the map\'s list' % name)
            e = exprs[n]
            record = {'index': e.fields.get('index')}
            if e.kind == 'TextureParameter':
                record['parameter'] = e.fields['name']
            elif e.kind != 'Texture':
                raise Refused('texture', e.kind)
        textures = self.program['textures']
        for key, have in textures.items():
            if have == record:
                return key
        key = 't%d' % len(textures)
        textures[key] = record
        return key

    def emit(self, indices):
        """The kept instructions written into the program's code."""
        code = self.program['code']
        for i in indices:
            if (self.prefix, i) in self.done:
                continue
            self.done.add((self.prefix, i))
            ins = self.flow.code[i]
            if ins.op in ('texld', 'texldl'):
                dcl = next((d for d in self.flow.shader.declarations() if d.dest.reg == ins.srcs[1].reg), None)
                if dcl is not None and dcl.sampler != '2d':
                    raise Refused('cube' if dcl.sampler == 'cube' else 'texture', 'a %s texture' % dcl.sampler)
            # (a read at a level of detail is a texld row read at that level, `texld: lod`)
            row = {'op': 'texld' if ins.op == 'texldl' else ins.op, 'd': self.name(ins.dest.reg), 'm': ins.dest.mask,
                   's': [self.source(s) for s in ins.srcs]}
            if ins.dest.sat:
                row['sat'] = 1
            if ins.op == 'texld' and (ins.project or ins.bias):
                row['texld'] = 'project' if ins.project else 'bias'
            if ins.op == 'texldl':
                row['texld'] = 'lod'
            code.append(row)

    def source(self, s):
        out = {'r': self.name(s.reg), 'w': ''.join(COMPONENTS[c] for c in s.swizzle)}
        if s.mod in ('neg', 'abs_neg'):
            out['n'] = 1
        if s.mod in ('abs', 'abs_neg'):
            out['a'] = 1
        if s.mod not in ('', 'neg', 'abs', 'abs_neg'):
            raise Refused('modifier', s.mod)
        return out

    def output(self, end, reg, comps, letter=''):
        """Slices `reg`'s components `comps` as they stand before instruction `end` and gives the output record.
        Each output's registers are named apart (`letter`), so that the slices of one shader, written one after
        the other, don't overwrite each other's values."""
        self.prefix = self.tag + letter
        kept, leaves = backward(self.flow, end, {(reg, c) for c in comps}, lod=self.screen)
        for leaf, c in sorted(leaves, key=lambda rc: (rc[0].kind, rc[0].index, rc[1])):   # (the same reason each run)
            if leaf.kind == 'r':
                raise Refused('register', '%s.%s read before it is written' % (leaf.name(), COMPONENTS[c]))
            if leaf.kind == 'v':
                dcl = self.flow.inputs.get(leaf)
                if dcl is None:
                    raise Refused('input', 'undeclared %s' % leaf.name())
                src = pixel_input(dcl, c, self.vs_out, self.tag, self.kinds, self.factory, self.screen)
                if src['kind'] == 'refused':
                    raise Refused('input', src['why'])
        self.emit(kept)                           # (names given in the instructions' order: the same every run)
        return {'r': self.name(reg), 'm': ''.join(COMPONENTS[c] for c in comps)}


# ---------------------------------------------------------------------------------------------------------------
# Finding the ends

def override_end(flow, name):
    """(instruction index, register, components) of the value scaled by the override constant `name` and added to
    its xyz, or None when the shader has no such constant. Refused when it is read in more than one place or in a
    form not recognised."""
    entry = flow.shader.constants.get(name)
    if entry is None:
        return None
    creg = sm3.Register('c', entry.index)
    uses = [i for i, ins in enumerate(flow.code) if any(s.reg == creg for s in ins.srcs)]
    if not uses:
        return None
    first = uses[0]
    ins = flow.code[first]
    if flow.depth[first] > 0:
        raise Refused('branch', '%s is applied under a branch' % name)
    srcs = ins.srcs
    others = [s for s in srcs if s.reg != creg]
    scale = [s for s in srcs if s.reg == creg and len(set(s.swizzle)) == 1 and s.swizzle[0] == 3]
    if ins.op == 'mad' and len(srcs) == 3 and srcs[2].reg == creg and scale and len(others) == 1:
        value, form = others[0], 'mad'
    elif ins.op == 'mul' and scale and len(others) == 1:
        value, form = others[0], 'mul'
    elif (ins.op == 'mul' and len(others) == 1 and name == 'SpecularOverrideParameter'
          and any(s.reg == creg and s.swizzle[:3] == (0, 1, 2) for s in srcs)):
        flow.form = 'none'                        # (0 * w + xyz) * the light: the material's highlight is black
        return first, None, None, None
    else:
        raise Refused('end', '%s is applied as %s' % (name, sm3.instruction_text(ins, flow.shader)))
    later = [i for i in uses[1:] if not (flow.code[i].op == 'add' and i > first)]
    if ins.op == 'mad' and later:
        raise Refused('end', '%s is read more than once' % name)
    comps = [COMPONENTS.index(c) for c in ins.dest.mask]
    flow.form = form
    return first, value.reg, [value.swizzle[c] for c in comps], comps


def pick(refs, starts, prefer):
    """The shader type of `refs` that starts with one of `starts`, the first of `prefer`'s endings that exists."""
    for start in starts:
        for end in prefer:
            for kind in refs:
                if kind.startswith(start) and kind.endswith(end):
                    return kind
        for kind in refs:
            if kind.startswith(start):
                return kind
    return None


_VERTEX = {}       # a vertex shader's outputs worked out once a process, by its ID and whether a particle's
BASE_PS = ('TBasePassPixelShaderFNoLightMapPolicyNoSkyLight', 'TBasePassPixelShaderFNoLightMapPolicySkyLight')
BASE_VS = ('TBasePassVertexShaderFNoLightMapPolicyFNoDensityPolicy',)
LIGHT_PS = ('TLightPixelShaderFPointLightPolicyFNoStaticShadowingPolicy',)
LIGHT_VS = ('TLightVertexShaderFPointLightPolicyFNoStaticShadowingPolicy',)
LMAP_PS = ('TBasePassPixelShaderFDirectionalLightMapTexturePolicyNoSkyLight',
           'TBasePassPixelShaderFDirectionalLightMapTexturePolicySkyLight')
LMAP_VS = ('TBasePassVertexShaderFDirectionalLightMapTexturePolicyFNoDensityPolicy',)
FOW = ('WithoutTranslucentFOW', 'WithTranslucentFOW', '')


def slice_material(cache, smap, values, translucent=False, factory=FACTORY, particle=False):
    """The material's program: {'version', 'shaders', 'inputs', 'constants', 'textures', 'code', 'outputs',
    'refused'}. `values` holds the material's parameter values ({'vectors': {name: [r, g, b, a]}, 'scalars':
    {name: x}}). Each output it can't give is named in 'refused' with its reason; Refused when no shader of the
    base pass is there or nothing can be given. `particle`: a particle's material, from `factory`'s shaders (a sprite
    emitter's particle factory, or a mesh emitter's local one): the base pass only, the screen's inputs taken
    (`SCREEN_ENGINE`, `SCREEN_TEXTURES`, the clip-space position)."""
    refs = cache.shader_refs(smap).get(factory)
    if not refs:
        raise Refused('shaders', 'no shaders for %s' % factory)
    uniforms = cache.uniforms(smap)
    program = {'version': PROGRAM_VERSION, 'shaders': {}, 'ends': {}, 'inputs': {}, 'constants': {},
               'textures': {}, 'code': [], 'outputs': {}, 'refused': {}}
    base_ps, base_vs = pick(refs, BASE_PS, FOW), pick(refs, BASE_VS, ('',))
    if not base_ps or not base_vs:
        raise Refused('shaders', 'no base pass without a lightmap')
    program['shaders'].update(base=base_ps, baseId=_hex(refs[base_ps]))
    if particle:
        program['shaders']['factory'] = factory
    if any(kind.startswith('TDistortion') for kind in refs):
        program['distortion'] = True              # the game draws it in its distortion pass: it bends what is behind

    def part(tag, ps_type, vs_type, fold=None):
        ps = cache.shader(refs[ps_type])
        vs_id = refs[vs_type]
        if (vs_id, particle) not in _VERTEX:
            vs = cache.shader(vs_id)
            _VERTEX[(vs_id, particle)] = (vertex_outputs(vs, literal_abs=particle), numeric_kinds(vs))
        vs_out, kinds = _VERTEX[(vs_id, particle)]
        return Part(tag, Flow(ps), vs_out, uniforms, values, program, fold, kinds, factory, particle)

    def attempt(output, work):
        mark = (len(program['code']), dict(program['inputs']), dict(program['constants']),
                dict(program['textures']))
        try:
            result = work()
            if result is not None:
                program['outputs'][output] = result
        except Refused as why:
            program['refused'][output] = str(why)
            del program['code'][mark[0]:]
            for key, kept in zip(('inputs', 'constants', 'textures'), mark[1:]):
                program[key] = kept

    base = part('b', base_ps, base_vs)

    def diffuse():
        found = override_end(base.flow, 'DiffuseOverrideParameter')
        if found is None:
            program['unlit'] = True               # its whole colour is its glow
            return None
        end, reg, comps, _ = found
        program.setdefault('ends', {})['diffuse'] = base.flow.form
        return base.output(end, reg, comps, 'd')
    attempt('diffuse', diffuse)

    def cutout():
        kills = [i for i, ins in enumerate(base.flow.code) if ins.op == 'texkill' and base.flow.depth[i] == 0]
        if not kills:
            return None
        last = None
        for i in kills:                           # the engine's own (screen-door fades, decals' clips) refuse
            ins = base.flow.code[i]
            mark = (len(program['code']), dict(program['inputs']), dict(program['constants']),
                    dict(program['textures']))
            try:
                return base.output(i, ins.dest.reg, [COMPONENTS.index(c) for c in ins.dest.mask], 'm')
            except Refused as why:
                last = why
                del program['code'][mark[0]:]
                for key, kept in zip(('inputs', 'constants', 'textures'), mark[1:]):
                    program[key] = kept
        raise last
    attempt('mask', cutout)

    def glow():
        fold = {n: [0.0] * 4 for n in LIGHT_TERMS}
        fold.update(NEUTRAL)
        g = part('g', base_ps, base_vs, fold)
        writes = [i for i, ins in enumerate(g.flow.code) if ins.dest is not None and ins.dest.reg.kind == 'oC'
                  and ins.dest.reg.index == 0 and set(ins.dest.mask) & set('xyz')]
        if not writes:
            raise Refused('end', 'no colour output')
        last = writes[-1]
        return g.output(last + 1, g.flow.code[last].dest.reg, [0, 1, 2])
    attempt('glow', glow)

    if translucent:
        def opacity():
            o = part('o', base_ps, base_vs, dict(NEUTRAL))
            writes = [i for i, ins in enumerate(o.flow.code) if ins.dest is not None
                      and ins.dest.reg.kind == 'oC' and ins.dest.reg.index == 0 and 'w' in ins.dest.mask]
            if not writes:
                raise Refused('end', 'no alpha output')
            last = writes[-1]
            return o.output(last + 1, o.flow.code[last].dest.reg, [3])
        attempt('opacity', opacity)

    if particle:
        # (a particle faces the camera: its highlight and its normal map are not drawn)
        fold(program)
        if not program['outputs']:
            raise Refused('nothing', '; '.join('%s %s' % kv for kv in program['refused'].items()))
        return program
    light_ps, light_vs = pick(refs, LIGHT_PS, ('',)), pick(refs, LIGHT_VS, ('',))
    if light_ps and light_vs:
        program['shaders'].update(light=light_ps, lightId=_hex(refs[light_ps]))
        light = part('s', light_ps, light_vs)

        def specular():
            found = override_end(light.flow, 'SpecularOverrideParameter')
            if found is None:
                return None
            end, reg, comps, dest_comps = found
            if reg is None:
                return {'value': [0.0, 0.0, 0.0]}
            out = light.output(end, reg, comps, 's')
            power = specular_power(light, end)
            if power is not None:
                program['outputs']['power'] = power
            return out
        attempt('specular', specular)
    else:
        program['refused']['specular'] = 'shaders: no light pass'

    lmap_ps, lmap_vs = pick(refs, LMAP_PS, FOW), pick(refs, LMAP_VS, ('',))
    if lmap_ps and lmap_vs:
        program['shaders'].update(lightmap=lmap_ps, lightmapId=_hex(refs[lmap_ps]))
        lmap = part('n', lmap_ps, lmap_vs)
        attempt('normal', lambda: normal_end(lmap))
    else:
        program['refused']['normal'] = 'shaders: no lightmap pass'
    fold(program)
    if not program['outputs']:
        raise Refused('nothing', '; '.join('%s %s' % kv for kv in program['refused'].items()))
    return program


def specular_power(light, end):
    """The power of the highlight: the exponent of the pow whose result scales the highlight (followed forward from
    its end through up to eight instructions), sliced; None when there is no such pow."""
    code = light.flow.code
    tracked = {code[end].dest.reg}

    def writer(reg, before):
        for j in range(before - 1, -1, -1):
            if code[j].dest is not None and code[j].dest.reg == reg:
                return j
        return None
    steps = 0
    for i in range(end + 1, len(code)):
        ins = code[i]
        if not any(s.reg in tracked for s in ins.srcs):
            continue
        for s in ins.srcs:
            if s.reg in tracked:
                continue
            j = writer(s.reg, i)
            if j is not None and code[j].op == 'pow':
                exponent = code[j].srcs[1]
                return light.output(j, exponent.reg, [exponent.swizzle[0]], 'p')
        if ins.dest is not None:
            tracked.add(ins.dest.reg)
        steps += 1
        if steps >= 8:
            break
    return None


def normal_end(lmap):
    """The normal: the register the lightmap pass dots with the basis constants (its xyz)."""
    flow = lmap.flow
    basis_regs = {reg for reg, values in flow.literals.items()
                  if any(abs(v - b) < 1e-6 for v in values for b in BASIS[:2])}
    for i, ins in enumerate(flow.code):
        if ins.op in ('dp3', 'dp2add') and any(s.reg in basis_regs for s in ins.srcs):
            other = [s for s in ins.srcs[:2] if s.reg not in basis_regs]
            if len(other) != 1:
                continue
            reg = other[0].reg
            return lmap.output(i, reg, [0, 1, 2])
    raise Refused('end', 'no normal dotted with the lightmap basis')


def _hex(sid):
    import struct
    return ''.join('%08x' % w for w in struct.unpack('<4I', sid))


# ---------------------------------------------------------------------------------------------------------------
# Folding: constants worked out, light terms set to zero dropped, code no output needs taken out

def expr_from_json(record):
    """A uniform expression back from its to_json form."""
    import shader_cache
    fields = {k: v for k, v in record.items() if k not in ('kind', 'args')}
    return shader_cache.Expr(record['kind'], fields, [expr_from_json(a) for a in record.get('args', [])])


def row_reads(row, comps):
    """[(source position, name, component)] a program row reads to make the destination components `comps`."""
    op, out = row['op'], []
    srcs = row['s']

    def sw(s, k):
        return COMPONENTS.index(s['w'][k])
    if op in COMPONENTWISE:
        for p, s in enumerate(srcs):
            out += [(p, s['r'], sw(s, c)) for c in comps]
    elif op in SCALAR or op == 'sincos':
        out += [(p, s['r'], sw(s, 0)) for p, s in enumerate(srcs)]
    elif op in ('dp3', 'nrm', 'crs'):
        for p, s in enumerate(srcs):
            out += [(p, s['r'], sw(s, k)) for k in range(3)]
    elif op == 'dp4':
        for p, s in enumerate(srcs):
            out += [(p, s['r'], sw(s, k)) for k in range(4)]
    elif op == 'dp2add':
        out += [(p, srcs[p]['r'], sw(srcs[p], k)) for p in (0, 1) for k in range(2)]
        out.append((2, srcs[2]['r'], sw(srcs[2], 0)))
    elif op == 'texld':
        coords = (0, 1, 3) if row.get('texld') else (0, 1)
        out += [(0, srcs[0]['r'], sw(srcs[0], k)) for k in coords]
        out.append((1, srcs[1]['r'], 0))
    else:
        raise Refused('instruction', op)
    return out


def fold(program):
    """The program with what is known worked out: constants (not those that move with time or that the page sets)
    carried through, a product with a known zero known to be zero, a mad whose factor is zero made a move, outputs
    that come out constant given as values (a glow of zero dropped), and code, inputs, constants and textures no
    output needs taken out."""
    import numpy as np
    import shader_eval
    known = {}
    for name, record in program['constants'].items():
        if not ({'vector', 'scalars', 'engine', 'uniform'} & set(record)):
            for c in range(4):
                known[(name, c)] = float(record['value'][c])
    for name, sources in program['inputs'].items():
        for c, src in enumerate(sources):
            if src and src.get('kind') == 'const':
                known[(name, c)] = float(src['value'])
    code = []
    held = set()                                  # (name, component): in its register as well as in `known`

    def new_constant(values):
        record = {'value': [float(v) for v in values]}
        for name, have in program['constants'].items():
            if have == record:
                return name
        name = 'k%d' % len(program['constants'])
        program['constants'][name] = record
        for c in range(4):
            known[(name, c)] = record['value'][c]
        return name

    def source_value(s):
        values = [known.get((s['r'], COMPONENTS.index(s['w'][k])), 0.0) for k in range(4)]
        v = np.array([values], dtype=np.float64)
        if s.get('a'):
            v = np.abs(v)
        if s.get('n'):
            v = -v
        return v

    def settle(dest, comps, row):
        value = shader_eval.apply(row['op'], [source_value(s) for s in row['s']], row.get('sat'))[0]
        for c in comps:
            known[(dest, c)] = float(value[c])
            held.discard((dest, c))

    for row in program['code']:
        comps = [COMPONENTS.index(c) for c in row['m']]
        dest = row['d']
        reads = row_reads(row, comps)
        unknown = [r for r in reads if (r[1], r[2]) not in known]
        if row['op'] != 'texld' and not unknown:
            settle(dest, comps, row)
            continue

        def zero(p, c):
            s = row['s'][p]
            return known.get((s['r'], COMPONENTS.index(s['w'][c]))) == 0.0
        if row['op'] == 'mul' and all(zero(0, c) or zero(1, c) for c in comps):
            for c in comps:
                known[(dest, c)] = 0.0
                held.discard((dest, c))
            continue
        def one(p, c):
            s = row['s'][p]
            v = known.get((s['r'], COMPONENTS.index(s['w'][c])))
            return v is not None and (-v if s.get('n') else v) == 1.0
        if row['op'] == 'mul' and not row.get('sat') and (all(one(0, c) for c in comps)
                                                            or all(one(1, c) for c in comps)):
            keep = 1 if all(one(0, c) for c in comps) else 0
            s = row['s'][keep]
            if s['r'] == dest and all(s['w'][c] == COMPONENTS[c] for c in comps) and not s.get('n') and not s.get('a'):
                continue                          # a register times one: itself
            row = dict(row, op='mov', s=[s])
        if row['op'] == 'mad' and all(zero(0, c) or zero(1, c) for c in comps):
            row = dict(row, op='mov', s=[row['s'][2]])
            reads = row_reads(row, comps)
            if not [r for r in reads if (r[1], r[2]) not in known]:
                settle(dest, comps, row)
                continue
        # registers it reads that are known but not held in their register get a move first
        for _, n, c in reads:
            if (n, c) in known and not n.startswith(('k', 't')) and (n, c) not in held:
                values = [known.get((n, k), 0.0) for k in range(4)]
                mask = ''.join(COMPONENTS[k] for k in range(4) if (n, k) in known and (n, k) not in held)
                code.append({'op': 'mov', 'd': n, 'm': mask, 's': [{'r': new_constant(values), 'w': 'xyzw'}]})
                held.update((n, k) for k in range(4) if (n, k) in known)
        code.append(row)
        for c in comps:
            known.pop((dest, c), None)
            held.discard((dest, c))
    outputs = {}
    for name, o in program['outputs'].items():
        if 'value' in o:
            outputs[name] = o
            continue
        comps = [COMPONENTS.index(c) for c in o['m']]
        if all((o['r'], c) in known and (o['r'], c) not in held for c in comps):
            value = [known[(o['r'], c)] for c in comps]
            if name == 'glow' and not any(value):
                continue                          # no glow
            outputs[name] = {'value': value}
            continue
        loose = [c for c in range(4) if (o['r'], c) in known and (o['r'], c) not in held]
        if loose:
            values = [known.get((o['r'], k), 0.0) for k in range(4)]
            code.append({'op': 'mov', 'd': o['r'], 'm': ''.join(COMPONENTS[c] for c in loose),
                         's': [{'r': new_constant(values), 'w': 'xyzw'}]})
        outputs[name] = o
    program['outputs'] = outputs
    needed = set()
    for o in outputs.values():
        if 'r' in o:
            needed |= {(o['r'], COMPONENTS.index(c)) for c in o['m']}
    kept = []
    for row in reversed(code):
        comps = [COMPONENTS.index(c) for c in row['m'] if (row['d'], COMPONENTS.index(c)) in needed]
        if not comps:
            continue
        for c in comps:
            needed.discard((row['d'], c))
        needed |= {(n, c) for _, n, c in row_reads(row, comps)}
        kept.append(dict(row, m=''.join(COMPONENTS[c] for c in comps)))
    kept.reverse()
    program['code'] = kept
    used = {s['r'] for row in kept for s in row['s']} | {o['r'] for o in outputs.values() if 'r' in o}
    for key in ('inputs', 'constants', 'textures'):
        program[key] = {k: v for k, v in program[key].items() if k in used}
    return program
