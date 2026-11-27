"""The install's compiled material shaders: RefShaderCache-PC-D3D-SM3.upk read as an index (the game-likeness plan,
track A; the layout measured in F-168).

The package holds one ShaderCache export. After its empty properties and nine bytes come:
- the shaders: a count, then a record each: its type (a name), its ID (16 bytes), a hash (20), the file offset of
  the next record, a counted array of 16-bit words, two bytes (frequency, platform), then the counted SM3 bytecode;
- the material shader maps: a count, then a record each: its key (a static parameter set: the base material's ID,
  its switches, component masks, normal parameters and a fourth list), the package's two versions, the file offset
  of the next record, and its body.

A map's body: the material-level shaders (a count of type and shader pairs), the mesh shader maps (a count, each a
shader list and its vertex factory's type), the material's ID, its name, its static parameter set again, and its
uniform expressions in six lists (pixel vectors, pixel scalars, 2D textures, cube textures, vertex vectors, vertex
scalars), each expression a small tree (`Expr`).

  open_cache(path) -> Cache                   the index (the package is decompressed once: about 4.5 s)
  cache.shader_code(id), cache.shader(id)     a shader's bytecode, and its sm3.Shader
  cache.find_maps(base_id, switches=None)     the maps of a base material (with these switch values)
  cache.shader_refs(map)                      {vertex factory: {shader type: shader id}} ('' for the material's own)
  cache.uniforms(map)                         {'pixelVectors': [...], ...}: Expr lists; FormatError if unreadable
  cache.name(map)                             the material's name as its map gives it

Every read is bounded by the record's offsets: a damaged or unknown map is a FormatError for that map, not the cache.
"""
import hashlib
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from package import Package, FormatError  # noqa: E402
import sm3  # noqa: E402  (beside this file)

FILE_NAME = 'RefShaderCache-PC-D3D-SM3.upk'
VERSIONS = (845, 64)
UNIFORM_LISTS = ('pixelVectors', 'pixelScalars', 'textures2d', 'texturesCube', 'vertexVectors', 'vertexScalars')
# FMaterialUniformExpressionFoldedMath's operations
FOLDED = {0: 'add', 1: 'sub', 2: 'mul', 3: 'div', 4: 'dot'}


def cache_path(install):
    """The shader cache of an install (its folder): XEW's cooked folder, Enemy Within's."""
    return Path(install) / 'XEW' / 'XComGame' / 'CookedPCConsole' / FILE_NAME


def guid_text(raw):
    """A 16-byte ID as the four little-endian words in hex, as the plan and the register write them."""
    return ''.join('%08x' % w for w in struct.unpack('<4I', raw))


class Expr:
    """A uniform expression: its kind (the class name without FMaterialUniformExpression), its fields (parameter
    names, defaults, an index, an operation) and its operands (Expr)."""
    __slots__ = ('kind', 'fields', 'args')

    def __init__(self, kind, fields=None, args=()):
        self.kind, self.fields, self.args = kind, fields or {}, list(args)

    def to_json(self):
        out = {'kind': self.kind, **self.fields}
        if self.args:
            out['args'] = [a.to_json() for a in self.args]
        return out

    def __repr__(self):
        inner = ', '.join(['%s=%r' % kv for kv in self.fields.items()] + [repr(a) for a in self.args])
        return '%s(%s)' % (self.kind, inner)


class _Cursor:
    """Bounded reads over the package's bytes."""

    def __init__(self, data, at, end, names):
        self.d, self.at, self.end, self.names = data, at, end, names

    def take(self, n):
        if self.at + n > self.end:
            raise FormatError('a read of %d bytes past the record at %d' % (n, self.at))
        out = self.d[self.at:self.at + n]
        self.at += n
        return out

    def i32(self):
        return struct.unpack('<i', self.take(4))[0]

    def u8(self):
        return self.take(1)[0]

    def f32s(self, n):
        return list(struct.unpack('<%df' % n, self.take(4 * n)))

    def count(self, limit=100000):
        n = self.i32()
        if not 0 <= n <= limit:
            raise FormatError('a count of %d at %d' % (n, self.at - 4))
        return n

    def name(self):
        index, number = struct.unpack('<ii', self.take(8))
        if not 0 <= index < len(self.names):
            raise FormatError('a name index %d at %d' % (index, self.at - 8))
        return self.names[index] + ('_%d' % (number - 1) if number else '')

    def guid(self):
        return bytes(self.take(16))

    def string(self):
        n = self.i32()
        if n == 0:
            return ''
        if n > 0:
            if n > 4096:
                raise FormatError('a string of %d bytes' % n)
            return bytes(self.take(n)).rstrip(b'\0').decode('latin-1')
        if -n > 4096:
            raise FormatError('a string of %d characters' % -n)
        return bytes(self.take(-2 * n)).decode('utf-16-le').rstrip('\0')


def _static_parameters(c):
    """A static parameter set: (base id, switches, masks, normals, fourth list's raw entries)."""
    base = c.guid()
    switches = []
    for _ in range(c.count(4096)):
        name = c.name()
        value, override = c.i32(), c.i32()
        c.take(16)
        switches.append((name, bool(value), bool(override)))
    masks = []
    for _ in range(c.count(4096)):
        name = c.name()
        rgba = tuple(bool(c.i32()) for _ in range(4))
        override = bool(c.i32())
        c.take(16)
        masks.append((name, rgba, override))
    normals = []
    for _ in range(c.count(4096)):
        name = c.name()
        compression = c.u8()
        override = bool(c.i32())
        c.take(16)
        normals.append((name, compression, override))
    terrain = []
    for _ in range(c.count(4096)):          # never seen with entries: its size is the engine's terrain layer weight
        name = c.name()
        index, override = c.i32(), c.i32()
        c.take(16)
        terrain.append((name, index, bool(override)))
    return base, switches, masks, normals, terrain


def _expr(c, depth=0):
    if depth > 64:
        raise FormatError('a uniform expression nested too deep')
    full = c.name()
    if not full.startswith('FMaterialUniformExpression'):
        raise FormatError('not a uniform expression: %s' % full)
    kind = full[len('FMaterialUniformExpression'):]
    sub = lambda: _expr(c, depth + 1)
    if kind == 'Constant':
        value = c.f32s(4)
        return Expr(kind, {'value': value, 'valueType': c.u8()})
    if kind == 'VectorParameter':
        return Expr(kind, {'name': c.name(), 'default': c.f32s(4)})
    if kind == 'XComVectorParameter':          # one byte: which of the game's own colours (a unit's paint) it is
        return Expr(kind, {'slot': c.u8()})
    if kind == 'ScalarParameter':
        return Expr(kind, {'name': c.name(), 'default': c.f32s(1)[0]})
    if kind == 'TextureParameter':
        name = c.name()
        return Expr(kind, {'name': name, 'index': c.i32()})
    if kind in ('Texture', 'FlipBookTextureParameter'):     # the flip book's: a vector (its frame's scale and offset)
        return Expr(kind, {'index': c.i32()})
    if kind in ('Time', 'RealTime'):
        return Expr(kind)
    if kind == 'Sine':
        x = sub()
        return Expr(kind, {'cosine': bool(c.i32())}, [x])
    if kind in ('SquareRoot', 'Abs', 'Floor', 'Frac', 'Periodic', 'Ceil', 'Length'):
        return Expr(kind, {}, [sub()])
    if kind == 'Clamp':
        return Expr(kind, {}, [sub(), sub(), sub()])
    if kind in ('Min', 'Max', 'Fmod'):
        return Expr(kind, {}, [sub(), sub()])
    if kind == 'FoldedMath':
        a, b = sub(), sub()
        op = c.u8()
        return Expr(kind, {'op': FOLDED.get(op, op)}, [a, b])
    if kind == 'AppendVector':
        a, b = sub(), sub()
        return Expr(kind, {'componentsA': c.i32()}, [a, b])
    raise FormatError('a uniform expression of a kind not read: %s' % kind)


class Cache:
    """The index of a RefShaderCache package (open_cache)."""

    def __init__(self, path, package=None):
        self.path = Path(path)
        p = package or Package(self.path)
        self.package = p
        self.data, self.names = p.data, p.names
        exports = [e for i, e in enumerate(p.exports, 1) if p.cls(i) == 'ShaderCache']
        if len(exports) != 1:
            raise FormatError('%d ShaderCache exports, not one' % len(exports))
        e = exports[0]
        self.start, self.end = e['off'], e['off'] + e['size']
        c = _Cursor(self.data, self.start, self.end, self.names)
        c.take(4)                             # the export's net index
        if c.name() != 'None':                # its properties: none
            raise FormatError('the shader cache has properties')
        if any(c.take(9)):
            raise FormatError('the shader cache does not start as measured')
        self.shaders = {}
        n = c.count(1000000)
        for _ in range(n):
            record = c.at
            kind = c.name()
            sid = c.guid()
            c.take(20)
            skip = c.i32()
            if not record < skip <= self.end:
                raise FormatError('a shader record\'s next offset %d at %d' % (skip, record))
            c.take(2 * c.count(1000000))
            frequency, platform = c.u8(), c.u8()
            size = c.count(1 << 24)
            if c.at + size > skip:
                raise FormatError('a shader\'s bytecode runs past its record at %d' % record)
            self.shaders[sid] = (kind, c.at, size, frequency)
            c.at = skip
        self.maps = []
        n = c.count(1000000)
        for _ in range(n):
            record = c.at
            base, switches, masks, normals, terrain = _static_parameters(c)
            versions = (c.i32(), c.i32())
            if versions != VERSIONS:
                raise FormatError('a shader map at %d has versions %s' % (record, versions))
            skip = c.i32()
            if not c.at <= skip <= self.end:
                raise FormatError('a shader map\'s next offset %d at %d' % (skip, record))
            self.maps.append(ShaderMap(len(self.maps), base, switches, masks, normals, terrain, c.at, skip))
            c.at = skip
        self.by_base = {}
        for m in self.maps:
            self.by_base.setdefault(m.base, []).append(m)

    def shader_code(self, sid):
        kind, at, size, _ = self.shaders[sid]
        return bytes(self.data[at:at + size])

    def shader_type(self, sid):
        return self.shaders[sid][0]

    def shader(self, sid):
        return sm3.decode(self.shader_code(sid))

    def find_maps(self, base, switches=None):
        """The maps of a base material ID (16 bytes, or its guid_text), those whose switches have the values given
        ({name: bool}) when `switches` is given (a switch the map doesn't name counts as off)."""
        if isinstance(base, str):
            base = struct.pack('<4I', *(int(base[k:k + 8], 16) for k in range(0, 32, 8)))
        found = self.by_base.get(base, [])
        if switches is None:
            return list(found)
        want = {k: bool(v) for k, v in switches.items() if v}
        return [m for m in found if {n: v for n, v, _ in m.switches if v} == want]

    def _body(self, m):
        """(cursor after the mesh shader maps, {vertex factory: {type: id}})."""
        c = _Cursor(self.data, m.body, m.end, self.names)
        refs = {}

        def shader_list():
            out = {}
            for _ in range(c.count(4096)):
                kind = c.name()
                sid = c.guid()
                again = c.name()
                if again == 'None':           # a type the cooker left without a shader
                    continue
                if again != kind:
                    raise FormatError('a shader reference names %s then %s' % (kind, again))
                out[kind] = sid
            return out

        own = shader_list()
        if own:
            refs[''] = own
        for _ in range(c.count(4096)):
            shaders = shader_list()
            factory = c.name()
            refs[factory] = shaders
        return c, refs

    def shader_refs(self, m):
        return self._body(m)[1]

    def name(self, m):
        c, _ = self._body(m)
        c.guid()
        return c.string()

    def material_id(self, m):
        c, _ = self._body(m)
        return c.guid()

    def uniforms(self, m):
        """{list name: [Expr]} of the map's uniform expressions (UNIFORM_LISTS)."""
        c, _ = self._body(m)
        c.guid()
        c.string()
        _static_parameters(c)
        out = {}
        for key in UNIFORM_LISTS:
            out[key] = [_expr(c) for _ in range(c.count(4096))]
        return out


class ShaderMap:
    """A material shader map's key and its body's bounds in the package."""
    __slots__ = ('index', 'base', 'switches', 'masks', 'normals', 'terrain', 'body', 'end')

    def __init__(self, index, base, switches, masks, normals, terrain, body, end):
        self.index, self.base, self.switches, self.masks = index, base, switches, masks
        self.normals, self.terrain, self.body, self.end = normals, terrain, body, end

    @property
    def base_id(self):
        return guid_text(self.base)

    def __repr__(self):
        return 'ShaderMap(%d, %s, %s)' % (self.index, self.base_id, self.switches)


_OPEN = {}


def open_cache(path):
    """The index of the shader cache at `path`, kept for the process (one per file's size and time)."""
    path = Path(path)
    st = path.stat()
    key = (str(path.resolve()).lower(), st.st_size, st.st_mtime_ns)
    if key not in _OPEN:
        _OPEN[key] = Cache(path)
    return _OPEN[key]


def file_hash(path):
    """The SHA-256 of the cache file: the same file in every install names one kept copy."""
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
