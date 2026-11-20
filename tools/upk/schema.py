"""The game's property types, read from its script packages (private/plans/done/cross-map-assets-implementation-plan.md, X1).

A tagged property says its kind, but not what an array holds or which struct a struct property is: 4 bytes of an array
can be an object reference or a number. The script packages say, in their export tables alone: a class or struct is
an export, each of its properties an export under it whose class is the property's kind; an array property's element
is the property export its data ends with (its Inner), a struct property's struct the export its data ends with, a
byte property's enum likewise. A struct's flags say whether it is saved as plain bytes (immutable) or as tagged
properties, and its field chain (Children, then each field's Next) gives its members in the order they are saved.

  python -B tools/upk/schema.py <CookedPCConsole> [<out.json>]      (counts; the schema as JSON when a file is named)

build(cooked) reads the packages; load(cache, cooked) keeps the result as <cache>/schema/<digest>.json, the digest
over the script packages' hashes. Schema answers the questions the typed walker (typed_props.py) asks.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo  # noqa: E402

VERSION = 1
# the script packages the maps' classes come from (those an install has are read)
SCRIPT_PACKAGES = ('Core', 'Engine', 'GameFramework', 'GFxUI', 'XComGame', 'XComStrategyGame', 'XComUIShell')
OWNERS = ('Class', 'ScriptStruct')
# a struct with either flag is saved as its members' plain bytes, in order, with no tags (cooked data)
STRUCT_IMMUTABLE, STRUCT_IMMUTABLE_WHEN_COOKED = 0x20, 0x80


def _read(path):
    data, header = upkinfo.load(str(path))
    names, imports, exports = upkinfo.tables(data, header)
    return data, names, imports, exports


def build(cooked, packages=SCRIPT_PACKAGES):
    """The schema of the script packages in the folder `cooked`:
    dict(version, packages {name: sha16}, structs {path: dict(kind, super, flags, props {name: property},
    order [property names as saved])}, raw [paths of the structs saved as plain bytes]).
    A property is dict(kind, [dim], [struct: path], [enum: True], [inner: property])."""
    cooked = Path(cooked)
    structs, hashes = {}, {}
    for package in packages:
        path = cooked / (package + '.upk')
        if not path.is_file():
            continue
        hashes[package] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        data, names, imports, exports = _read(path)
        cls = [upkinfo.clsname(e['cls'], imports, exports) for e in exports]

        def full(index, package=package, imports=imports, exports=exports):
            if index == 0:
                return None
            path_ = upkinfo.objname(index, imports, exports)
            return path_ if index < 0 else package + '.' + path_

        def body(n, exports=exports, data=data):
            e = exports[n]
            return data[e['off']:e['off'] + e['size']]

        def last(n):
            d = body(n)
            return struct.unpack_from('<i', d, len(d) - 4)[0]

        def after_none(n, names=names, cls=cls):
            """Where an export's native data starts: after its net index and the closing None of its (no) tagged
            properties."""
            d = body(n)
            if cls[n] == 'Class':
                return d, 4             # a class has no tagged properties, and no closing None
            if len(d) < 12 or names[struct.unpack_from('<i', d, 4)[0]] != 'None':
                raise ValueError('%s: a field with tagged properties of its own' % full(n + 1))
            return d, 12

        def prop(n, cls=cls):
            kind = cls[n]
            d, at = after_none(n)
            dim = struct.unpack_from('<i', d, at + 4)[0] & 0xFFFF
            out = dict(kind=kind)
            if dim != 1:
                out['dim'] = dim
            if kind == 'StructProperty':
                out['struct'] = full(last(n))
            elif kind == 'ByteProperty':
                if last(n):
                    out['enum'] = True
            elif kind == 'ArrayProperty':
                inner = last(n)
                if inner <= 0:
                    raise ValueError('%s: an array property with no element export' % full(n + 1))
                out['inner'] = prop(inner - 1)
            return out

        kids = {}
        for n, e in enumerate(exports):
            kids.setdefault(e['outer'], []).append(n)
        for n, e in enumerate(exports):
            if cls[n] not in OWNERS:
                continue
            d, at = after_none(n)
            # UField.Next, UStruct: SuperField (in the entry: 0 here), ScriptText, Children, CppText, Line, TextPos,
            # the two script sizes and the script; then a ScriptStruct's flags
            child = struct.unpack_from('<i', d, at + 12)[0]
            entry = dict(kind=cls[n], super=full(e['sup']), props={}, order=[])
            if cls[n] == 'ScriptStruct':
                sizes = struct.unpack_from('<ii', d, at + 28)
                entry['flags'] = struct.unpack_from('<I', d, at + 36 + sizes[1])[0]
            seen = set()
            while child > 0:
                if child in seen:
                    raise ValueError('%s: its field chain loops' % full(n + 1))
                seen.add(child)
                k = child - 1
                if exports[k]['outer'] != n + 1:
                    raise ValueError('%s: a field of its chain lies under another object' % full(n + 1))
                if cls[k].endswith('Property'):
                    entry['props'][exports[k]['name']] = prop(k)
                    entry['order'].append(exports[k]['name'])
                child = struct.unpack_from('<i', *after_none(k))[0]
            # a property export under it that the chain doesn't reach is still a property a tag can name (Long War
            # took m_arrAlloyProjects out of a checkpoint record's chain); a plain-bytes struct must have them all
            for k in kids.get(n + 1, ()):
                if cls[k].endswith('Property') and exports[k]['name'] not in entry['props']:
                    if entry.get('flags', 0) & (STRUCT_IMMUTABLE | STRUCT_IMMUTABLE_WHEN_COOKED):
                        raise ValueError('%s: property %s is not in its field chain'
                                         % (full(n + 1), exports[k]['name']))
                    entry['props'][exports[k]['name']] = prop(k)
            structs[full(n + 1)] = entry
    raw =sorted(p for p, e in structs.items()
                 if e.get('flags', 0) & (STRUCT_IMMUTABLE | STRUCT_IMMUTABLE_WHEN_COOKED))
    return dict(version=VERSION, packages=hashes, structs=structs, raw=raw)


def digest(cooked, packages=SCRIPT_PACKAGES):
    h = hashlib.sha256(('schema %d' % VERSION).encode())
    for package in packages:
        path = Path(cooked) / (package + '.upk')
        if path.is_file():
            h.update(package.encode() + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()[:16]


def load(cache, cooked):
    """The Schema of the install whose packages are in `cooked`, built once and kept in <cache>/schema."""
    path = Path(cache) / 'schema' / (digest(cooked) + '.json')
    if path.is_file():
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc.get('version') == VERSION:
            return Schema(doc)
    doc = build(cooked)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix('.json.part')
    part.write_text(json.dumps(doc, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')
    os.replace(part, path)
    return Schema(doc)


class Schema:
    def __init__(self, doc):
        self.doc = doc
        self.structs = doc['structs']
        self.raw = set(doc['raw'])
        self._props = {}
        self._members = {}
        self.short = {}
        for path_, entry in self.structs.items():
            if entry['kind'] == 'ScriptStruct':
                self.short.setdefault(path_.rsplit('.', 1)[-1], []).append(path_)

    def chain(self, owner):
        """`owner` and its supers, nearest first."""
        seen = []
        while owner is not None and owner in self.structs and owner not in seen:
            seen.append(owner)
            owner = self.structs[owner]['super']
        return seen

    def prop(self, owner, name):
        """The property `name` of the class or struct `owner` (a path), its supers' included, or None."""
        key = (owner, name)
        if key not in self._props:
            self._props[key] = next((self.structs[o]['props'][name] for o in self.chain(owner)
                                     if name in self.structs[o]['props']), None)
        return self._props[key]

    def is_raw(self, path_):
        return path_ in self.raw

    def members(self, path_):
        """A plain-bytes struct's members in the order they are saved: its own, then its supers'."""
        if path_ not in self._members:
            self._members[path_] = [(name, self.structs[o]['props'][name]) for o in self.chain(path_)
                                    for name in self.structs[o]['order']]
        return self._members[path_]

    def struct_named(self, short):
        """The path of the one struct with this short name (the name a struct tag carries), or None."""
        found = self.short.get(short, [])
        return found[0] if len(found) == 1 else None

    def counts(self):
        props = [q for e in self.structs.values() for q in e['props'].values()]
        return dict(structs=len(self.structs), classes=sum(1 for e in self.structs.values() if e['kind'] == 'Class'),
                    properties=len(props), arrays=sum(1 for q in props if q['kind'] == 'ArrayProperty'),
                    raw=len(self.raw))


def main():
    doc = build(sys.argv[1])
    print(Schema(doc).counts(), doc['packages'])
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
