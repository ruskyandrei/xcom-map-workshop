"""The helpers the upk suite's tests share (review finding 58: a fixtures module per suite, rather than tests that
import other tests). Named for its suite, as file names are unique across the repository (the bake suite's is
fixtures.py)."""
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decomp  # noqa: E402
import package_edit  # noqa: E402
import upkinfo  # noqa: E402


def fstring(text):
    data = text.encode('latin1') + b'\0'
    return struct.pack('<i', len(data)) + data


def made_up_package(objects=(('Texture2D', 'URB_Bar', 0, b''),), additional=('Extra',)):
    """A small uncompressed v845 package (EW's licensee 64) made from nothing: (its bytes, where its parts are).
    `objects` are its exports, each (class name, object name, outer export index or 0, body bytes); each class is an
    import, Engine.<class>, after the Engine package's own (import -1). Every field the summary and the tables hold
    has a value: one generation, no chunks, the `additional` packages named, a net object index in each export.
    The places: 'folder' (the folder name's length), 'counts' (the summary's name, export and import counts), 'gens',
    'chunks' and 'addpkgs' (those counts), the tables ('names', 'imports', 'exports', 'depends'), each name's and
    each export's entry ('name_at', 'export_at') and the tables' end ('end', where the bodies start)."""
    names = ['None', 'Core', 'Engine', 'Package', 'Class']
    classes = list(dict.fromkeys(c for c, _, _, _ in objects))
    for n in classes + [o for _, o, _, _ in objects]:
        if n not in names:
            names.append(n)
    index = {n: i for i, n in enumerate(names)}

    def fname(n):
        return struct.pack('<ii', index[n], 0)

    places = {}

    def summary(name_at, import_at, export_at, depends_at, header_size):
        s = struct.pack('<IHHI', 0x9E2A83C1, 845, 64, header_size)
        places['folder'] = len(s)
        s += fstring('None') + struct.pack('<I', 0)
        places['counts'] = dict(names=len(s), exports=len(s) + 8, imports=len(s) + 16)
        s += struct.pack('<7I', len(names), name_at, len(objects), export_at, 1 + len(classes), import_at, depends_at)
        s += struct.pack('<4I', 0, 0, 0, 0) + bytes(range(16))         # GUID tables, thumbnails; the package's GUID
        places['gens'] = len(s)
        s += struct.pack('<4I', 1, len(objects), len(names), len(objects))
        s += struct.pack('<3I', 8916, 0, 0)                             # engine, cooker, compression flags
        places['chunks'] = len(s)
        s += struct.pack('<I', 0) + struct.pack('<I', 0x5EED)           # no chunks; the package source
        places['addpkgs'] = len(s)
        s += struct.pack('<I', len(additional)) + b''.join(fstring(a) for a in additional)
        return s

    name_table = b''
    places['name_at'] = []
    head = len(summary(0, 0, 0, 0, 0))
    for n in names:
        places['name_at'].append(head + len(name_table))
        name_table += fstring(n) + struct.pack('<Q', 0x0007001000000000)
    imports = fname('Core') + fname('Package') + struct.pack('<i', 0) + fname('Engine')
    for c in classes:
        imports += fname('Core') + fname('Class') + struct.pack('<i', -1) + fname(c)
    entry = 68 + 4                                                       # one net object index each
    name_at, import_at = head, head + len(name_table)
    export_at = import_at + len(imports)
    depends_at = export_at + entry * len(objects)
    end = depends_at + 4 * len(objects)
    exports, off = b'', end
    for c, o, outer, body in objects:
        exports += struct.pack('<iii', -2 - classes.index(c), 0, outer) + fname(o) + struct.pack('<i', 0)
        exports += struct.pack('<QIII', 0, len(body), off, 0) + struct.pack('<Ii', 1, 0) + bytes(16)
        exports += struct.pack('<I', 0)
        off += len(body)
    data = (summary(name_at, import_at, export_at, depends_at, end) + name_table + imports + exports
            + bytes(4 * len(objects)) + b''.join(body for _, _, _, body in objects))
    places.update(names=name_at, imports=import_at, exports=export_at, depends=depends_at, end=end,
                  export_at=[export_at + entry * k for k in range(len(objects))])
    return data, places


def uncompressed(path):
    """The package at `path` as it would be stored uncompressed (DLC2_3_Furies.upk as LWR ships it): the summary with
    no chunks, PKG_StoreCompressed and the compression flags cleared, then the logical bytes."""
    raw = Path(path).read_bytes()
    h = upkinfo.summary(raw)
    full, _ = decomp.decompress_pkg(str(path))
    table = package_edit.chunk_table_offset(raw, h['chunks'])
    r = upkinfo.R(raw)
    r.u32(); r.u16(); r.u16(); r.u32(); r.fstr()
    head = bytearray(raw[:table])
    struct.pack_into('<I', head, r.o, int(h['flags'], 16) & ~package_edit.STORE_COMPRESSED)
    struct.pack_into('<I', head, table - 4, 0)
    lo = h['chunks'][0][0]
    out = bytes(head) + struct.pack('<I', 0) + raw[table + 4 + 16 * len(h['chunks']):h['chunks'][0][2]]
    if len(out) != lo:
        raise ValueError('the summary is not where the first chunk starts')
    return out + full[lo:]
