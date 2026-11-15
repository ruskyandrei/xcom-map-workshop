"""Every name and object reference in an export's tagged properties, by the game's own property types
(private/plans/done/cross-map-assets-implementation-plan.md, X1).

  python -B tools/upk/typed_props.py <map.upk> [<map.upk> ...]      (the walk over every export: counts, what failed)

fields(p, index, schema) gives the places, from the start of the export's data, of:
- what stands before the properties: a state frame's two object references (an object with a stack), a component's
  template owner class and, for a template, its template name;
- each property tag's names (the property, its kind, a struct's or an enum's name);
- each value that is a name (a name property, an enum's value) or an object reference (object, component, class and
  interface properties, a delegate's object and function name), inside structs and arrays to any depth: an array's
  element kind and a struct property's struct come from the schema (schema.py), a struct saved as plain bytes is read
  member by member.

The export's net index (the 4 bytes before its properties) is not a field: it is a number of the package's own.
A property the schema doesn't know is walked by what its tag says; only an array (its element kind unknown) or a map
property is reported as untyped, with its place, and nothing in it is listed. `p` is a viewer Package (package.py).
"""
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'viewer'))
import props as legacy_props  # noqa: E402
import schema as schema_module  # noqa: E402

NAME, OBJECT = 'name', 'object'
HAS_STACK = 0x02000000
REFERENCES = ('ObjectProperty', 'ComponentProperty', 'ClassProperty', 'InterfaceProperty')
PLAIN = {'IntProperty': 4, 'FloatProperty': 4}
# the cooked component puts a counted WORD array before everything else (package.LEADING_SHADOW_MAP)
LEADING_WORDS = ('DominantDirectionalLightComponent',)


class WalkError(ValueError):
    pass


class Fields:
    """What fields() returns: `fields` [(offset, 'name' | 'object')] in order, `start` and `end` of the tagged
    properties (end: after the closing None, where native data begins), `net_index` (its offset), `untyped`
    [(property path, offset, size)]."""

    def __init__(self):
        self.fields, self.untyped = [], []
        self.start = self.end = self.net_index = None


class _Walk:
    def __init__(self, p, schema, data, out):
        self.p, self.schema, self.b, self.out = p, schema, data, out
        self.names = p.names

    def name(self, at):
        i, number = struct.unpack_from('<ii', self.b, at)
        if not 0 <= i < len(self.names) or number < 0:
            raise WalkError('no name at %d' % at)
        self.out.fields.append((at, NAME))
        return self.names[i] + ('_%d' % (number - 1) if number else '')

    def tagged(self, at, end, owner, path):
        """The tagged properties from `at`, of the class or struct `owner` (a schema path, or None); returns the
        offset after the closing None."""
        b = self.b
        while at + 8 <= end:
            pname = self.name(at)
            if pname == 'None':
                return at + 8
            if at + 24 > end:
                break
            kind = self.name(at + 8)
            size, _ = struct.unpack_from('<ii', b, at + 16)
            at += 24
            known = self.schema.prop(owner, pname) if owner else None
            if known is not None and known['kind'] != kind:
                known = None            # another property of the same name (a subclass's): go by the tag
            here = path + pname
            if kind == 'BoolProperty':
                at += 1
                continue
            if size < 0 or at + size > end:
                raise WalkError('%s: a value of %d bytes runs past its container' % (here, size))
            if kind == 'StructProperty':
                short = self.name(at)
                at += 8
                which = known['struct'] if known else self.schema.struct_named(short)
                if which is None or which not in self.schema.structs:
                    # a struct the schema lacks: plain bytes unless it reads as tagged properties
                    which = None
                stop = self.struct(at, at + size, which, here + '.')
                if stop != at + size:
                    raise WalkError('%s: struct %s ends at %d of %d bytes' % (here, short, stop - at, size))
            elif kind == 'ByteProperty':
                self.name(at)
                at += 8
                if size == 8:
                    self.name(at)
                elif size != 1:
                    raise WalkError('%s: a byte property of %d bytes' % (here, size))
            elif kind in REFERENCES:
                if size not in (4, 8):
                    raise WalkError('%s: a reference of %d bytes' % (here, size))
                self.out.fields.append((at, OBJECT))
            elif kind == 'NameProperty':
                self.name(at)
            elif kind == 'DelegateProperty':
                self.out.fields.append((at, OBJECT))
                self.name(at + 4)
            elif kind == 'ArrayProperty':
                inner = known.get('inner') if known else None
                if inner is None:
                    if size > 4:
                        self.out.untyped.append((here, at, size))
                else:
                    count = struct.unpack_from('<i', b, at)[0]
                    stop = at + 4
                    for k in range(count):
                        stop = self.item(stop, at + size, inner, '%s(%d).' % (here, k))
                    if stop != at + size:
                        raise WalkError('%s: %d elements end at %d of %d bytes' % (here, count, stop - at, size))
            elif kind in ('IntProperty', 'FloatProperty', 'StrProperty'):
                pass
            else:
                self.out.untyped.append((here, at, size))
            at += size
        raise WalkError('%sno closing None' % path)

    def struct(self, at, end, which, path):
        """A struct's value from `at`; returns where it ends."""
        if which is not None and self.schema.is_raw(which):
            for name, member in self.schema.members(which):
                for _ in range(member.get('dim', 1)):
                    at = self.item(at, end, member, path + name + '.')
            return at
        if which is None and not self.looks_tagged(at, end):
            return end
        return self.tagged(at, end, which, path)

    def looks_tagged(self, at, end):
        if at + 8 > end:
            return False
        i, number = struct.unpack_from('<ii', self.b, at)
        if not 0 <= i < len(self.names) or number < 0:
            return False
        if self.names[i] == 'None':
            return number == 0 and at + 8 == end
        if at + 24 > end:
            return False
        k = struct.unpack_from('<i', self.b, at + 8)[0]
        return 0 <= k < len(self.names) and self.names[k] in legacy_props.PROP_TYPES

    def item(self, at, end, prop, path):
        """One untagged value of the property `prop` (an array's element, a plain-bytes struct's member); returns
        where it ends."""
        kind = prop['kind']
        if kind in PLAIN:
            size = PLAIN[kind]
        elif kind in REFERENCES:
            self.out.fields.append((at, OBJECT))
            size = 4
        elif kind == 'NameProperty':
            self.name(at)
            size = 8
        elif kind == 'ByteProperty':
            if prop.get('enum'):
                self.name(at)
            size = 8 if prop.get('enum') else 1
        elif kind == 'BoolProperty':
            size = 1                # as a tagged bool's value (a skeletal mesh's LODInfo.bEnableShadowCasting)
        elif kind == 'StrProperty':
            n = struct.unpack_from('<i', self.b, at)[0]
            size = 4 + (n if n >= 0 else -2 * n)
        elif kind == 'DelegateProperty':
            self.out.fields.append((at, OBJECT))
            self.name(at + 4)
            size = 12
        elif kind == 'StructProperty':
            which = prop.get('struct')
            if which not in self.schema.structs:
                raise WalkError('%s: struct %s is not in the schema' % (path, which))
            return self.struct(at, end, which, path)
        elif kind == 'ArrayProperty':
            count = struct.unpack_from('<i', self.b, at)[0]
            at += 4
            for k in range(count):
                at = self.item(at, end, prop['inner'], '%s(%d).' % (path, k))
            return at
        else:
            raise WalkError('%s: an untagged %s' % (path, kind))
        if at + size > end:
            raise WalkError('%s: a value runs past its container' % path)
        return at + size


def class_path(p, index):
    """The schema path of export `index`'s class (its import's path), or None for a class the package holds itself."""
    c = p.exports[index - 1]['cls']
    return p.name(c) if c < 0 else None


def fields(p, index, schema):
    """The names and object references of export `index` up to the end of its tagged properties: a Fields."""
    e = p.exports[index - 1]
    data = p.data[e['off']:e['off'] + e['size']]
    out = Fields()
    lead = 0
    if p.cls(index) in LEADING_WORDS:
        lead = 4 + 2 * struct.unpack_from('<i', data, 0)[0]
    shifted = dict(e, off=e['off'] + lead, size=e['size'] - lead)
    start = legacy_props.props_start(p.data, shifted, p.names) - e['off']
    at = lead
    if (e['flags'] >> 32) & HAS_STACK:
        out.fields += [(at, OBJECT), (at + 4, OBJECT)]
        at += 18 + (4 if struct.unpack_from('<i', data, at)[0] else 0)
    before = start - 4 - at
    if before == 4:
        out.fields.append((at, OBJECT))
    elif before == 12:
        out.fields.append((at, OBJECT))
        i, number = struct.unpack_from('<ii', data, at + 4)
        if not 0 <= i < len(p.names):
            raise WalkError('%s: no template name before its properties' % p.name(index))
        out.fields.append((at + 4, NAME))
    elif before:
        raise WalkError('%s: %d unknown bytes before its properties' % (p.name(index), before))
    out.start, out.net_index = start, start - 4
    walk = _Walk(p, schema, data, out)
    try:
        out.end = walk.tagged(start, len(data), class_path(p, index), '')
    except (WalkError, struct.error) as error:
        raise WalkError('%s (%s): %s' % (p.name(index), p.cls(index), error)) from None
    return out


def survey(p, schema):
    """The walk over every export of `p`: dict(exports, fields, names, objects, failed [(path, class, why)],
    untyped {class.property: count}, noClass {class: count})."""
    import collections
    out = dict(exports=len(p.exports), names=0, objects=0, failed=[], untyped=collections.Counter(),
               noClass=collections.Counter())
    for index in range(1, len(p.exports) + 1):
        cls = class_path(p, index)
        if cls not in schema.structs and p.cls(index) not in ('Package', 'Class'):
            out['noClass'][cls or p.cls(index)] += 1
        try:
            f = fields(p, index, schema)
        except WalkError as error:
            out['failed'].append((p.name(index), p.cls(index), str(error)))
            continue
        out['names'] += sum(1 for _, k in f.fields if k == NAME)
        out['objects'] += sum(1 for _, k in f.fields if k == OBJECT)
        for path_, _, _ in f.untyped:
            # the property's name without the element numbers of the arrays it lies in
            import re
            out['untyped'][p.cls(index) + '.' + re.sub(r'\(\d+\)', '', path_)] += 1
    out['untyped'], out['noClass'] = dict(out['untyped']), dict(out['noClass'])
    return out


def main():
    from package import Package
    sch = None
    for path in sys.argv[1:]:
        if sch is None:
            sch = schema_module.Schema(schema_module.build(Path(path).parent))
        p = Package(path)
        s = survey(p, sch)
        print(Path(path).stem, {k: (v if not isinstance(v, list) else len(v)) for k, v in s.items()})
        for row in s['failed'][:12]:
            print('   failed:', row)


if __name__ == '__main__':
    main()
