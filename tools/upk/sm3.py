"""Shader Model 3 bytecode (Direct3D 9's vs_3_0 and ps_3_0, and the 2_x forms) decoded: its constant table, its
declarations and its instructions, and listed back in the form Windows' disassembler (D3DCompiler_47) writes, which
is this module's tests' oracle. Nothing here needs the DLL.

The game's compiled shaders (the RefShaderCache's records, shader_cache.py) are read with it to work out what a
material draws (the game-likeness plan, track A). The format is Direct3D 9's documented token stream: a version
token, then instruction tokens each followed by their parameter tokens (the count in bits 24 to 27 of the
instruction), comments (the constant table, `CTAB`) and an end token.

  decode(code) -> Shader         a shader's parts; FormatError on bytes it can't read
  listing(shader) -> str         its instructions, one a line, as the disassembler writes them
"""
import struct


class FormatError(ValueError):
    pass


OPS = {
    0: 'nop', 1: 'mov', 2: 'add', 3: 'sub', 4: 'mad', 5: 'mul', 6: 'rcp', 7: 'rsq', 8: 'dp3', 9: 'dp4', 10: 'min',
    11: 'max', 12: 'slt', 13: 'sge', 14: 'exp', 15: 'log', 16: 'lit', 17: 'dst', 18: 'lrp', 19: 'frc', 20: 'm4x4',
    21: 'm4x3', 22: 'm3x4', 23: 'm3x3', 24: 'm3x2', 25: 'call', 26: 'callnz', 27: 'loop', 28: 'ret', 29: 'endloop',
    30: 'label', 31: 'dcl', 32: 'pow', 33: 'crs', 34: 'sgn', 35: 'abs', 36: 'nrm', 37: 'sincos', 38: 'rep',
    39: 'endrep', 40: 'if', 41: 'if', 42: 'else', 43: 'endif', 44: 'break', 45: 'break', 46: 'mova', 47: 'defb',
    48: 'defi', 64: 'texcoord', 65: 'texkill', 66: 'texld', 67: 'texbem', 68: 'texbeml', 69: 'texreg2ar',
    70: 'texreg2gb', 71: 'texm3x2pad', 72: 'texm3x2tex', 73: 'texm3x3pad', 74: 'texm3x3tex', 76: 'texm3x3spec',
    77: 'texm3x3vspec', 78: 'expp', 79: 'logp', 80: 'cnd', 81: 'def', 82: 'texreg2rgb', 83: 'texdp3tex',
    84: 'texm3x2depth', 85: 'texdp3', 86: 'texm3x3', 87: 'texdepth', 88: 'cmp', 89: 'bem', 90: 'dp2add', 91: 'dsx',
    92: 'dsy', 93: 'texldd', 94: 'setp', 95: 'texldl', 96: 'break',
}
# operations whose first parameter is not written (no destination)
NO_DEST = {'nop', 'call', 'callnz', 'loop', 'ret', 'endloop', 'label', 'rep', 'endrep', 'if', 'else', 'endif',
           'break', 'texkill'}
COMPARE = {1: 'gt', 2: 'eq', 3: 'ge', 4: 'lt', 5: 'ne', 6: 'le'}
USAGE = {0: 'position', 1: 'blendweight', 2: 'blendindices', 3: 'normal', 4: 'psize', 5: 'texcoord', 6: 'tangent',
         7: 'binormal', 8: 'tessfactor', 9: 'positiont', 10: 'color', 11: 'fog', 12: 'depth', 13: 'sample'}
SAMPLER = {1: '1d', 2: '2d', 3: 'cube', 4: 'volume'}
SOURCE_MOD = {0: '', 1: 'neg', 2: 'bias', 3: 'bias_neg', 4: 'bx2', 5: 'bx2_neg', 6: 'comp', 7: 'x2', 8: 'x2_neg',
              9: 'dz', 10: 'dw', 11: 'abs', 12: 'abs_neg', 13: 'not'}
COMPONENTS = 'xyzw'
REGISTER_SETS = {0: 'bool', 1: 'int4', 2: 'float4', 3: 'sampler'}


class Constant:
    """A constant table entry: a name, its register set (bool, int4, float4, sampler), its first register and how
    many it takes."""
    __slots__ = ('name', 'set', 'index', 'count')

    def __init__(self, name, set, index, count):
        self.name, self.set, self.index, self.count = name, set, index, count

    def __repr__(self):
        return 'Constant(%r, %s, %d, %d)' % (self.name, self.set, self.index, self.count)


class Register:
    """A register: its kind (r, v, c, s, o, oC, oDepth, i, b, aL, p, a, t, vPos, vFace, oPos, oFog, oPts, oD) and
    number."""
    __slots__ = ('kind', 'index')

    def __init__(self, kind, index):
        self.kind, self.index = kind, index

    def name(self):
        if self.kind in ('vPos', 'vFace', 'oFog', 'oPts', 'aL', 'oDepth'):
            return self.kind
        return '%s%d' % (self.kind, self.index)

    def __eq__(self, other):
        return isinstance(other, Register) and (self.kind, self.index) == (other.kind, other.index)

    def __hash__(self):
        return hash((self.kind, self.index))

    def __repr__(self):
        return self.name()


class Dest:
    """A written register, with its write mask (a string of xyzw) and result modifiers (saturate, partial precision,
    centroid)."""
    __slots__ = ('reg', 'mask', 'sat', 'pp', 'centroid', 'relative')

    def __init__(self, reg, mask, sat=False, pp=False, centroid=False, relative=None):
        self.reg, self.mask, self.sat, self.pp, self.centroid, self.relative = reg, mask, sat, pp, centroid, relative

    def __repr__(self):
        return '%s%s' % (self.reg.name(), '.' + self.mask if self.mask != 'xyzw' else '')


class Src:
    """A read register, with its swizzle (four component numbers), its modifier (SOURCE_MOD's names) and, for an
    indexed read, the register that indexes it (with its one component)."""
    __slots__ = ('reg', 'swizzle', 'mod', 'relative')

    def __init__(self, reg, swizzle=(0, 1, 2, 3), mod='', relative=None):
        self.reg, self.swizzle, self.mod, self.relative = reg, tuple(swizzle), mod, relative

    def __repr__(self):
        return '%s%s.%s' % ('-' if 'neg' in self.mod else '', self.reg.name(), ''.join(COMPONENTS[c] for c in self.swizzle))


class Instruction:
    """An operation: its name, its comparison (ifc, breakc, setp), a predicate it is done under, its destination
    and sources; a dcl's usage (with its index) or sampler kind, a def's values."""
    __slots__ = ('op', 'opcode', 'compare', 'predicate', 'dest', 'srcs', 'usage', 'usage_index', 'sampler',
                 'values', 'project', 'bias')

    def __init__(self, op, opcode):
        self.op, self.opcode = op, opcode
        self.compare = self.predicate = self.dest = self.usage = self.sampler = self.values = None
        self.usage_index = 0
        self.srcs = []
        self.project = self.bias = False

    def __repr__(self):
        return '%s %s' % (self.op, ', '.join(map(repr, ([self.dest] if self.dest else []) + self.srcs)))


class Shader:
    """A decoded shader: its kind (vs or ps), version, constant table ({name: Constant}), the constant table's
    creator and target strings, and its instructions (dcl and def included, in their order)."""

    def __init__(self, kind, major, minor):
        self.kind, self.major, self.minor = kind, major, minor
        self.constants = {}
        self.creator = self.target = None
        self.instructions = []

    @property
    def version(self):
        return '%s_%d_%d' % (self.kind, self.major, self.minor)

    def constant_at(self, set_name, index):
        """The constant table entry that holds register `index` of a set (float4, sampler...), or None."""
        for c in self.constants.values():
            if c.set == set_name and c.index <= index < c.index + c.count:
                return c
        return None

    def declarations(self):
        return [i for i in self.instructions if i.op == 'dcl']

    def literals(self):
        """{register: values} of the def, defi and defb instructions."""
        return {i.dest.reg: i.values for i in self.instructions if i.op in ('def', 'defi', 'defb')}


def register(kind_code, index, shader_kind):
    if kind_code == 0:
        return Register('r', index)
    if kind_code == 1:
        return Register('v', index)
    if kind_code in (2, 11, 12, 13):
        return Register('c', index + {2: 0, 11: 2048, 12: 4096, 13: 6144}[kind_code])
    if kind_code == 3:
        return Register('a' if shader_kind == 'vs' else 't', index)
    if kind_code == 4:
        return Register(('oPos', 'oFog', 'oPts')[index] if index < 3 else 'oPos', index)
    if kind_code == 5:
        return Register('oD', index)
    if kind_code == 6:
        return Register('o' if shader_kind == 'vs' else 'oT', index)
    if kind_code == 7:
        return Register('i', index)
    if kind_code == 8:
        return Register('oC', index)
    if kind_code == 9:
        return Register('oDepth', index)
    if kind_code == 10:
        return Register('s', index)
    if kind_code == 14:
        return Register('b', index)
    if kind_code == 15:
        return Register('aL', index)
    if kind_code == 16:
        return Register('half', index)
    if kind_code == 17:
        return Register(('vPos', 'vFace')[index] if index < 2 else 'misc', index)
    if kind_code == 18:
        return Register('l', index)
    if kind_code == 19:
        return Register('p', index)
    raise FormatError('register type %d' % kind_code)


def _reg_parts(token, shader_kind):
    kind = ((token >> 28) & 7) | ((token >> 8) & 0x18)
    return register(kind, token & 0x7FF, shader_kind)


def _dest(token, shader_kind):
    mask = ''.join(COMPONENTS[k] for k in range(4) if token & (1 << (16 + k)))
    mod = (token >> 20) & 0xF
    return Dest(_reg_parts(token, shader_kind), mask, bool(mod & 1), bool(mod & 2), bool(mod & 4))


def _src(token, shader_kind):
    swizzle = tuple((token >> (16 + 2 * k)) & 3 for k in range(4))
    return Src(_reg_parts(token, shader_kind), swizzle, SOURCE_MOD.get((token >> 24) & 0xF, '?'))


def _ctab(body):
    """(creator, target, {name: Constant}) of a constant table comment's body (after its CTAB tag)."""
    def text(at):
        end = body.index(b'\0', at)
        return body[at:end].decode('latin-1')
    try:
        size, creator, version, count, info, flags, target = struct.unpack_from('<7I', body, 0)
        constants = {}
        for k in range(count):
            name, rset, index, rcount, _, type_info, default = struct.unpack_from('<IHHHHII', body, info + 20 * k)
            n = text(name)
            constants[n] = Constant(n, REGISTER_SETS.get(rset, str(rset)), index, rcount)
        return text(creator), text(target), constants
    except (struct.error, ValueError) as error:
        raise FormatError('constant table: %s' % error) from None


def decode(code):
    """A Shader from SM2/SM3 bytecode."""
    if len(code) < 8 or len(code) % 4:
        raise FormatError('%d bytes: not a shader' % len(code))
    words = struct.unpack('<%dI' % (len(code) // 4), code)
    version = words[0]
    kind = {0xFFFF: 'ps', 0xFFFE: 'vs'}.get(version >> 16)
    if kind is None:
        raise FormatError('version token %08x' % version)
    shader = Shader(kind, (version >> 8) & 0xFF, version & 0xFF)
    at, n = 1, len(words)
    while at < n:
        token = words[at]
        opcode = token & 0xFFFF
        if opcode == 0xFFFF:
            return shader
        if opcode == 0xFFFE:
            size = (token >> 16) & 0x7FFF
            body = code[4 * (at + 1):4 * (at + 1 + size)]
            if body[:4] == b'CTAB':
                shader.creator, shader.target, shader.constants = _ctab(body[4:])
            at += 1 + size
            continue
        length = (token >> 24) & 0xF
        if at + 1 + length > n:
            raise FormatError('an instruction runs past the end at token %d' % at)
        params = words[at + 1:at + 1 + length]
        op = OPS.get(opcode)
        if op is None:
            raise FormatError('opcode %d at token %d' % (opcode, at))
        ins = Instruction(op, opcode)
        controls = (token >> 16) & 0xFF
        if opcode in (41, 45, 94):
            ins.compare = COMPARE.get(controls & 7, '?')
        if opcode == 66:
            ins.project, ins.bias = bool(controls & 1), bool(controls & 2)
        k = 0
        if op == 'dcl':
            usage = params[0]
            ins.dest = _dest(params[1], kind)
            if ins.dest.reg.kind == 's':
                ins.sampler = SAMPLER.get((usage >> 27) & 0xF, '?')
            elif ins.dest.reg.kind not in ('vPos', 'vFace'):
                ins.usage, ins.usage_index = USAGE.get(usage & 0x1F, '?'), (usage >> 16) & 0xF
            k = 2
        elif op in ('def', 'defi', 'defb'):
            ins.dest = _dest(params[0], kind)
            raw = struct.pack('<%dI' % (length - 1), *params[1:])
            ins.values = list(struct.unpack('<%d%s' % (length - 1, 'f' if op == 'def' else 'i'), raw))
            if op == 'defb':
                ins.values = [bool(ins.values[0])]
            k = length
        else:
            if token & (1 << 28):        # predicated: the predicate register is the last parameter
                pred = params[-1]
                ins.predicate = _src(pred, kind)
                params = params[:-1]
            if op not in NO_DEST and op != 'texkill' and params:
                ins.dest = _dest(params[0], kind)
                k = 1
                if params[0] & (1 << 13):
                    ins.dest.relative = _src(params[1], kind)
                    k = 2
            elif op == 'texkill':
                ins.dest = _dest(params[0], kind)
                k = 1
            while k < len(params):
                s = _src(params[k], kind)
                k += 1
                if params[k - 1] & (1 << 13):
                    if shader.major >= 2 and k < len(params):
                        s.relative = _src(params[k], kind)
                        k += 1
                    else:
                        s.relative = Src(Register('a', 0), (0, 0, 0, 0))
                ins.srcs.append(s)
        shader.instructions.append(ins)
        at += 1 + length
    raise FormatError('no end token')


# ---------------------------------------------------------------------------------------------------------------
# The listing, as D3DCompiler_47's disassembly writes it

def number(value):
    """A def's float as the disassembler writes it: up to nine significant digits, a negative zero kept, exponents
    of three digits (MSVC's printf)."""
    if value == 0:
        return '-0' if str(value).startswith('-') else '0'
    if value == int(value) and abs(value) < 1e16:
        return '%d' % value
    text = '%.9g' % value
    if 'e' in text:
        mantissa, exp = text.split('e')
        sign = exp[0] if exp[0] in '+-' else '+'
        digits = exp.lstrip('+-').lstrip('0') or '0'
        text = '%se%s%s' % (mantissa, sign, digits.rjust(3, '0'))
    return text


def swizzle_text(swizzle):
    if swizzle == (0, 1, 2, 3):
        return ''
    letters = [COMPONENTS[c] for c in swizzle]
    if len(set(letters)) == 1:
        return '.' + letters[0]
    return '.' + ''.join(letters)


def src_text(s):
    name = s.reg.name()
    if s.relative is not None:
        rel = s.relative
        inner = rel.reg.name() if rel.reg.kind == 'aL' else '%s.%s' % (rel.reg.name(), COMPONENTS[rel.swizzle[0]])
        name = '%s[%s]' % (name, inner)
    text = name + swizzle_text(s.swizzle)
    mod = s.mod
    if mod in ('', None):
        return text
    if mod == 'neg':
        return '-' + text
    if mod == 'abs':
        return text.replace(name, name + '_abs', 1)
    if mod == 'abs_neg':
        return '-' + text.replace(name, name + '_abs', 1)
    if mod == 'not':
        return '!' + text
    if mod.endswith('_neg'):
        return '-' + text.replace(name, name + '_' + mod[:-4], 1)
    return text.replace(name, name + '_' + mod, 1)


def dest_text(d):
    text = d.reg.name()
    if d.relative is not None:
        text = '%s[%s.%s]' % (text, d.relative.reg.name(), COMPONENTS[d.relative.swizzle[0]])
    return text + ('.' + d.mask if d.mask != 'xyzw' else '')


def instruction_text(ins, shader):
    if ins.op == 'dcl':
        d = ins.dest
        if d.reg.kind == 's':
            return 'dcl_%s %s' % (ins.sampler, d.reg.name())
        if d.reg.kind in ('vPos', 'vFace'):
            return 'dcl %s' % dest_text(d)
        name = 'dcl_%s%s' % (ins.usage, ins.usage_index or '')
        if d.pp:
            name += '_pp'
        if d.centroid:
            name += '_centroid'
        return '%s %s' % (name, dest_text(d))
    if ins.op in ('def', 'defi', 'defb'):
        values = ins.values
        if ins.op == 'def':
            shown = ', '.join(number(v) for v in values)
        elif ins.op == 'defi':
            shown = ', '.join('%d' % v for v in values)
        else:
            shown = 'true' if values[0] else 'false'
        return '%s %s, %s' % (ins.op, ins.dest.reg.name(), shown)
    name = ins.op
    if ins.compare:
        name += '_' + ins.compare
    if ins.op == 'texld':
        name = 'texldp' if ins.project else 'texldb' if ins.bias else 'texld'
    if ins.dest is not None and ins.op != 'texkill':
        if ins.dest.sat:
            name += '_sat'
        if ins.dest.pp:
            name += '_pp'
        if ins.dest.centroid:
            name += '_centroid'
    parts = []
    if ins.dest is not None:
        parts.append(dest_text(ins.dest))
    parts += [src_text(s) for s in ins.srcs]
    text = name + (' ' + ', '.join(parts) if parts else '')
    if ins.predicate is not None:
        p = ins.predicate
        text = '(%s%s%s) %s' % ('!' if p.mod == 'not' else '', p.reg.name(), swizzle_text(p.swizzle), text)
    return text


def listing(shader):
    """The shader's version and instructions, one a line, as D3DCompiler_47 writes them (without its comments)."""
    return '\n'.join([shader.version] + [instruction_text(i, shader) for i in shader.instructions])


def oracle(code):
    """D3DCompiler_47's disassembly of `code` (Windows only), as text; None where the DLL can't be loaded."""
    try:
        import ctypes
        dll = ctypes.WinDLL('D3DCompiler_47.dll')
    except (OSError, AttributeError):
        return None
    dll.D3DDisassemble.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_char_p,
                                   ctypes.POINTER(ctypes.c_void_p)]
    blob = ctypes.c_void_p()
    if dll.D3DDisassemble(code, len(code), 0, None, ctypes.byref(blob)) != 0:
        raise FormatError('the disassembler refused the shader')
    table = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    pointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(table[3])(blob)
    size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(table[4])(blob)
    text = ctypes.string_at(pointer, size).decode('latin-1')
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(blob)      # Release
    return text.rstrip('\0')


def oracle_lines(text):
    """The instruction lines of a disassembly (its comments and blank lines left out)."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        out.append(' '.join(line.split()))
    return out
