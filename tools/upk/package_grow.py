"""Growing edits of a compressed v845 package, by appending (UDK-removal plan U2; baker plan L4, gate C6).

The fixed-size writer (package_edit.py) keeps every logical offset. Growing a package that way is impossible: a new
export needs a new export-table entry, and the table sits in the header, before all export data. This writer
appends instead:
- fixed-size edits are made in place, as package_edit.py makes them (literal-LZO blocks, chunks moved);
- new exports' data, and the data of exports that grow (relocated: the old bytes stay, unreferenced), go after the
  logical end of the package (a new export's entry is a copy of a template export's, add_export, or made from its
  class, outer, name, archetype and flags alone, new_export, or one made elsewhere and given whole, adopt_export);
- after them, a new export table (the old entries, with relocated ones' size and offset changed, then the new
  entries) and a new depends map (one empty array per export, as the cooked maps have), and a new name table when
  names are added, and a new import table when imports are added (the old entries, then the new: no import index
  changes);
- all of it in new chunks after the last, as literal-LZO blocks of the original block size. A chunk is cut only
  where an export's data or a table starts, never inside one: the game's loader can't serve a read that crosses a
  chunk boundary, and hangs (EXP-20 run 4, findings register T-14). The cooked maps keep that rule too: none of
  their exports' data or table entries crosses one. A table or an export's data bigger than CHUNK_UNCOMPRESSED gets a
  chunk to itself;
- the summary points at the new tables, with the new counts (also its generation's export, name and net object
  counts), and its
  chunk table gains the new chunks, so the physical summary grows by 16 bytes a chunk. Logical offsets don't depend
  on it: the cooked maps already have physical and logical offsets 416 bytes apart (their chunk table).

A package stored uncompressed (DLC2_3_Furies.upk as Long War Rebalance ships it) is read in the compressed cooked
maps' layout (package_edit.compressed_layout: its logical bytes in literal-LZO chunks), so it is written compressed
like the others.

Nothing that was in the package moves, so no export data needs relocating and inline bulk data keeps its absolute
offsets. A relocated or new export that holds inline bulk data must have those offsets fixed by its caller, from
`next_offset()` (tools/bake/lightmap_textures.py's clone_texture does it for texture mips).

The game reads tables after the export data, beyond the summary's header size: gate C6 passed
(research/experiments/EXP-20-growing-writer.md), and every Build that adds an actor, a name or an import writes its
map this way.

  python -B tools/upk/package_grow.py <in.upk> <out.upk>      (a growing write with no change: the tables move)
"""
import argparse
import bisect
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decomp  # noqa: E402
import package_edit  # noqa: E402
import upkinfo  # noqa: E402

HAS_STACK = 0x02000000          # RF_HasStack, in the high half of an export's object flags
FORCED_EXPORT = 0x1             # EF_ForcedExport, in an export's export flags
CHUNK_UNCOMPRESSED = package_edit.CHUNK_UNCOMPRESSED   # appended chunks hold up to this much, unless one item is bigger


def net_index_at(object_flags, data):
    """Where a plain object's NetIndex lies in its data: first, or after the state frame of an object that has one.
    A component's comes after its template owner class (4 bytes) instead: in every case the NetIndex is the 4 bytes
    just before the tagged properties, which a caller that finds those should use."""
    if (object_flags >> 32) & HAS_STACK:
        node = struct.unpack_from('<i', data, 0)[0]
        return 4 + 4 + 8 + 2 + (4 if node else 0)
    return 0


def header_fields(raw):
    """Physical offsets of the summary fields this writer changes, and of the chunk table (count) and what follows."""
    r = upkinfo.R(raw)
    r.u32(); r.u16(); r.u16()
    at = dict(headerSize=r.o)
    r.u32(); r.fstr(); r.u32()
    for key in ('nameCount', 'nameOffset', 'exportCount', 'exportOffset', 'importCount', 'importOffset',
                'dependsOffset', 'importExportGuidsOffset', 'importGuidsCount', 'exportGuidsCount',
                'thumbnailOffset'):
        at[key] = r.o
        r.u32()
    r.o += 16
    count = r.u32()
    if count < 1:
        raise ValueError('the summary has no generation')
    at['generation0'] = r.o           # export count, name count, net object count
    r.o += 12 * count
    r.u32(); r.u32()
    at['compressionFlags'] = r.o
    r.u32()
    at['chunkTable'] = r.o
    return at


class Entry:
    """One export-table entry, kept as its bytes, with the fields this writer reads or changes."""
    def __init__(self, data):
        self.data = bytearray(data)
        if len(data) < 68:
            raise ValueError('short export entry')

    @classmethod
    def read(cls, b, at):
        r = upkinfo.R(b, at + 44)
        n = r.u32()
        size = 68 + 4 * n
        return cls(b[at:at + size]), size

    def get(self, fmt, at):
        return struct.unpack_from(fmt, self.data, at)[0]

    def put(self, fmt, at, value):
        struct.pack_into(fmt, self.data, at, value)

    cls = property(lambda s: s.get('<i', 0))
    outer = property(lambda s: s.get('<i', 8))
    name_index = property(lambda s: s.get('<i', 12))
    name_number = property(lambda s: s.get('<i', 16))
    size = property(lambda s: s.get('<I', 32))
    offset = property(lambda s: s.get('<I', 36))


class Grower:
    def __init__(self, src):
        self.src = src
        self.raw = package_edit.package_bytes(src)     # an uncompressed map in the compressed layout
        self.h = upkinfo.summary(self.raw)
        self.chunks = [tuple(c) for c in self.h['chunks']]
        package_edit.check_layout(self.raw, self.chunks)
        self.full, _ = decomp.decompress_pkg(src)
        self.end = self.chunks[-1][0] + self.chunks[-1][1]
        if len(self.full) != self.end:
            raise ValueError('the chunks do not end the logical package')
        self.names = []
        r = upkinfo.R(self.full, self.h['nameoff'])
        self.name_entries = []
        for _ in range(self.h['namecount']):
            s = r.o
            self.names.append(r.fstr())
            r.u64()
            self.name_entries.append(self.full[s:r.o])
        self.entries = []
        at = self.h['expoff']
        for _ in range(self.h['expcount']):
            e, size = Entry.read(self.full, at)
            self.entries.append(e)
            at += size
        self.imports = [self.full[self.h['impoff'] + 28 * k:self.h['impoff'] + 28 * (k + 1)]
                        for k in range(self.h['impcount'])]
        self.added_imports = 0
        depends = self.full[self.h['dependsoff']:self.h['dependsoff'] + 4 * self.h['expcount']]
        if depends != bytes(4 * self.h['expcount']):
            raise ValueError('the depends map is not all empty arrays; this writer would drop it')
        self.edits = {}                 # logical offset -> bytes, fixed size, inside the old package
        self.edit_starts = []           # the edits' offsets in order (an overlap is looked for among neighbours only)
        self.tail = bytearray()         # logical bytes after self.end, export data first
        self.marks = []                 # where in the tail each placed export's data starts (chunks are cut only there)
        self.added = 0
        self.new_names = []
        self.net_objects = self.h['gens'][0][2]     # the generation's net object count (a new actor takes the next)

    # -- what can be changed --------------------------------------------------------------------------------------
    def edit(self, offset, data):
        data = bytes(data)
        if offset < self.chunks[0][0] or offset + len(data) > self.end:
            raise ValueError(f'edit at {offset} is outside the compressed chunks')
        if not data:
            raise ValueError(f'empty edit at {offset}')     # (the writer refuses one: package_edit.normalise_edits)
        o = package_edit.overlapping(self.edits, self.edit_starts, offset, len(data))
        if o is not None:
            raise ValueError(f'edit at {offset} overlaps one at {o}')
        self.edits[offset] = data
        bisect.insort(self.edit_starts, offset)

    def name(self, text):
        """The name table index of `text`, adding it when it is new."""
        if text in self.names:
            return self.names.index(text)
        self.names.append(text)
        self.new_names.append(text)
        flags = struct.unpack_from('<Q', self.name_entries[0], len(self.name_entries[0]) - 8)[0]
        raw = text.encode('latin1') + b'\0'
        self.name_entries.append(struct.pack('<i', len(raw)) + raw + struct.pack('<Q', flags))
        return len(self.names) - 1

    def name_of(self, index, number):
        return self.names[index] + (f'_{number - 1}' if number else '')

    def find_import(self, class_name, object_name, outer=None):
        """The (negative) index of the import of class `class_name` named `object_name` (with `outer` when given),
        or None."""
        for k, raw in enumerate(self.imports):
            _, _, cn, cnn, o, on, onn = struct.unpack('<iiiiiii', raw)
            if (self.name_of(cn, cnn) == class_name and self.name_of(on, onn) == object_name
                    and (outer is None or o == outer)):
                return -(k + 1)
        return None

    def add_import(self, class_package, class_name, outer, object_name):
        """The import of `outer`'s object `object_name`, of class `class_package`.`class_name`, adding it when the
        package has none. Returns its (negative) index."""
        found = self.find_import(class_name, object_name, outer)
        if found is not None:
            return found
        raw = struct.pack('<iiiiiii', self.name(class_package), 0, self.name(class_name), 0, outer,
                          self.name(object_name), 0)
        self.imports.append(raw)
        self.added_imports += 1
        return -len(self.imports)

    def next_offset(self):
        """The logical offset the next placed export data will get (for data holding absolute offsets of itself,
        such as inline bulk data)."""
        return self.end + len(self.tail)

    def place(self, data):
        """Append export data; returns its logical offset."""
        at = self.next_offset()
        self.marks.append(len(self.tail))
        self.tail += data
        return at

    def unused_number(self, name_index):
        """An FName number no export with this name index uses (the number is the suffix plus one)."""
        used = {e.name_number for e in self.entries if e.name_index == name_index}
        return max(used | {0}) + 1

    def add_export(self, template, data, number=None, name_index=None):
        """A new export: a copy of export `template`'s entry (class, outer, flags) with its own name number, holding
        `data` (placed at the end). Returns its export index (1-based)."""
        e = Entry(self.entries[template - 1].data)
        if name_index is not None:
            e.put('<i', 12, name_index)
        e.put('<i', 16, number if number is not None else self.unused_number(e.name_index))
        e.put('<I', 32, len(data))
        e.put('<I', 36, self.place(data))
        self.entries.append(e)
        self.added += 1
        return len(self.entries)

    def new_export(self, cls, outer, name, data, archetype=0, flags=0, number=None):
        """A new export with no template (editor lights plan, 4.9): an entry of class `cls` (an import's negative or
        an export's positive index), under export `outer` (0 for a top-level object), named `name` (text; the name is
        added when the package has none) with FName number `number` (else an unused one, unused_number), archetype
        `archetype` (an object index, or 0 for the class default object, as the cooked maps' placed actors have it)
        and 64-bit object flags `flags`, holding `data` (placed at the end). Bounded to plain objects: no super
        field, no export flags (so no forced-export package), no net object counts, a zero package GUID and package
        flags. The caller builds `data` whole, its preamble and net index (next_net_index) included. Returns its
        export index (1-based)."""
        def valid(ref, what, zero=True):
            if not isinstance(ref, int) or isinstance(ref, bool):
                raise ValueError(f'{what} must be an object index, not {ref!r}')
            if ref == 0 and not zero or not -len(self.imports) <= ref <= len(self.entries):
                raise ValueError(f'{what} {ref} is not an object of the package')
        valid(cls, 'class', zero=False)
        valid(archetype, 'archetype')
        valid(outer, 'outer')
        if outer < 0:
            raise ValueError(f'outer {outer} is an import: a new export goes under an export of the package')
        if not isinstance(name, str) or not name or name == 'None':
            raise ValueError(f'invalid export name {name!r}')
        if not isinstance(flags, int) or not 0 <= flags < 1 << 64:
            raise ValueError(f'object flags {flags!r} are not 64-bit')
        index = self.name(name)
        if number is None:
            number = self.unused_number(index)
        if not isinstance(number, int) or number < 0:
            raise ValueError(f'invalid name number {number!r}')
        data = bytes(data)
        entry = struct.pack('<iiiiiiQIIII', cls, 0, outer, index, number, archetype, flags, len(data), 0, 0, 0)
        e = Entry(entry + bytes(16) + struct.pack('<I', 0))
        e.put('<I', 36, self.place(data))
        self.entries.append(e)
        self.added += 1
        return len(self.entries)

    def adopt_export(self, entry, data):
        """A new export whose entry was made elsewhere (tools/bake/transplant.py: another package's entry with its
        class, super, outer, name and archetype already in this package's numbering): everything else of `entry` (the
        object flags, export flags, net object counts, package GUID and flags) is kept, its size and offset set for
        `data` (placed at the end). The references may point at exports adopted after it; the caller checks them once
        all are in. Returns its export index (1-based)."""
        e = Entry(entry)
        if len(e.data) != 68 + 4 * e.get('<I', 44):
            raise ValueError('an export entry whose length disagrees with its net object counts')
        if not 0 <= e.name_index < len(self.names) or e.name_number < 0:
            raise ValueError('an export entry with a name outside the name table')
        for what, at in (('class', 0), ('super', 4), ('outer', 8), ('archetype', 20)):
            if e.get('<i', at) < -len(self.imports):
                raise ValueError(f'an export entry whose {what} is not an import of the package')
        if e.outer < 0:
            raise ValueError('an export entry under an import')
        data = bytes(data)
        e.put('<I', 32, len(data))
        e.put('<I', 36, self.place(data))
        self.entries.append(e)
        self.added += 1
        return len(self.entries)

    def _net_counted(self, index, what):
        """Refuses `index` when it, or an export it lies in, is a forced-export package (those count their own net
        objects, in their export entries)."""
        while index > 0:
            e = self.entries[index - 1]
            if e.get('<I', 40) & FORCED_EXPORT:
                raise ValueError(f'{what} lies inside a forced-export package, with net objects of its own')
            index = e.outer

    def next_net_index(self, outer):
        """The package's next net object index, for a new object under export `outer` (new_export's): the count
        grows by one. As fresh_net_index, the outer must not lie inside a forced-export package."""
        self._net_counted(outer, f'export {outer}')
        index = self.net_objects
        self.net_objects += 1
        return index

    def fresh_net_index(self, template, data, at=None):
        """`data` (a bytearray: the data of a new export cloned from export `template`) with a net index of its own
        when the template has one: the package's next net object. Net objects are counted per top-level package, and
        this count is the map's own, so the template must not lie inside a forced-export package (those count their
        own, in their export entries). An index of 0 is kept: in URB_Bar 1,948 objects share it and the game takes
        none of them for a duplicate, while the map's other indices are unique and below the count. `at` is where the
        index lies in `data` (just before the tagged properties); without it, a plain object's place (net_index_at),
        which is wrong for a component (EXP-20 run 5)."""
        self._net_counted(template, f'export {template}')
        if at is None:
            at = net_index_at(self.entries[template - 1].get('<Q', 24), data)
        if struct.unpack_from('<i', data, at)[0] > 0:
            struct.pack_into('<i', data, at, self.net_objects)
            self.net_objects += 1
        return data

    def relocate(self, index, data):
        """Give export `index` new data (of any size), placed at the end; its old bytes stay, unreferenced."""
        e = self.entries[index - 1]
        e.put('<I', 32, len(data))
        e.put('<I', 36, self.place(data))

    def export_data(self, index):
        e = self.entries[index - 1]
        if e.offset >= self.end:
            return bytes(self.tail[e.offset - self.end:e.offset - self.end + e.size])
        return self.full[e.offset:e.offset + e.size]

    # -- writing --------------------------------------------------------------------------------------------------
    chunk_cuts = staticmethod(package_edit.chunk_cuts)

    def write(self, dst):
        if os.path.abspath(self.src) == os.path.abspath(dst):
            raise ValueError('refusing to overwrite the input')
        tail = bytearray(self.tail)
        starts = list(self.marks)
        name_offset, name_count = self.h['nameoff'], self.h['namecount']
        if self.new_names:
            name_offset, name_count = self.end + len(tail), len(self.names)
            starts.append(len(tail))
            tail += b''.join(self.name_entries)
        import_offset, import_count = self.h['impoff'], self.h['impcount']
        if self.added_imports:
            import_offset, import_count = self.end + len(tail), len(self.imports)
            starts.append(len(tail))
            tail += b''.join(self.imports)
        export_offset = self.end + len(tail)
        starts.append(len(tail))
        tail += b''.join(bytes(e.data) for e in self.entries)
        depends_offset = self.end + len(tail)
        starts.append(len(tail))
        tail += bytes(4 * len(self.entries))
        logical = bytearray(self.full)
        for o, d in self.edits.items():
            logical[o:o + len(d)] = d
        logical += tail

        # the old chunks: as package_edit.py writes them, with the fixed-size edits; the temporary file goes beside the
        # output, never beside the input (which can be in the game install, read only)
        mid = str(dst) + '.grow-tmp'
        if self.edits:
            # (not verified by itself: the check below reads back the final file, which holds these chunks, and
            # decodes the blocks they re-encoded)
            package_edit.write_edited(self.src, mid, sorted(self.edits.items()), verify=False, raw=self.raw)
            with open(mid, 'rb') as f:
                base = f.read()
            os.remove(mid)
        else:
            base = self.raw
        hb = upkinfo.summary(base)
        old_chunks = [tuple(c) for c in hb['chunks']]
        bodies = [base[co:co + cs] for _, _, co, cs in old_chunks]
        bsz = package_edit.read_chunk(base, old_chunks[0][2])[1]
        entries = [(uo, us) for uo, us, _, _ in old_chunks]
        for start, stop in self.chunk_cuts(starts, len(tail)):
            bodies.append(package_edit.literal_chunk(bytes(tail[start:stop]), bsz))
            entries.append((self.end + start, stop - start))

        at = header_fields(base)
        table = at['chunkTable']
        n_old = struct.unpack_from('<I', base, table)[0]
        after_table = base[table + 4 + 16 * n_old:old_chunks[0][2]]
        head = bytearray(base[:table])
        for key, value in (('nameCount', name_count), ('nameOffset', name_offset),
                           ('importCount', import_count), ('importOffset', import_offset),
                           ('exportCount', len(self.entries)), ('exportOffset', export_offset),
                           ('dependsOffset', depends_offset)):
            struct.pack_into('<I', head, at[key], value)
        struct.pack_into('<III', head, at['generation0'], len(self.entries), name_count, self.net_objects)
        first = len(head) + 4 + 16 * len(entries) + len(after_table)
        table_bytes = struct.pack('<I', len(entries))
        co = first
        for (uo, us), body in zip(entries, bodies):
            table_bytes += struct.pack('<IIII', uo, us, co, len(body))
            co += len(body)
        out = bytes(head) + table_bytes + after_table + b''.join(bodies)
        with open(dst, 'wb') as f:
            f.write(out)

        # check: read back from disk, it decodes to the intended logical bytes, with the intended tables. The blocks
        # the file keeps from the source (their packed bytes the source's at the same place) are the source's decoded
        # bytes; the blocks this write made, and any that differ, are decoded (decomp.decompress_written)
        full2, h2 = decomp.decompress_written(dst, self.raw, self.h, self.full)
        lo = self.chunks[0][0]
        if full2[lo:] != bytes(logical[lo:]):
            raise ValueError('verification failed: the written package does not decode to the intended bytes')
        names2, imps2, exps2 = upkinfo.tables(full2, h2)
        if len(exps2) != len(self.entries) or names2 != self.names or len(imps2) != len(self.imports):
            raise ValueError('verification failed: the tables read back differently')
        for k, (e, x) in enumerate(zip(self.entries, exps2)):
            if (x['size'], x['off']) != (e.size, e.offset):
                raise ValueError(f'verification failed: export {k + 1} reads back at another place')
        # no export's data and no table may cross a chunk boundary (the loader hangs on such a read)
        bounds = sorted(uo for uo, _, _, _ in h2['chunks'])
        def crosses(a, b):
            return any(a < c < b for c in bounds)
        spans = [(f'export {k + 1}', x['off'], x['off'] + x['size']) for k, x in enumerate(exps2) if x['size']]
        spans += [('the name table', name_offset, name_offset + sum(map(len, self.name_entries))),
                  ('the import table', import_offset, import_offset + 28 * import_count),
                  ('the export table', export_offset, depends_offset),
                  ('the depends map', depends_offset, depends_offset + 4 * len(self.entries))]
        for what, a, b in spans:
            if crosses(a, b):
                raise ValueError(f'verification failed: {what} crosses a compressed chunk boundary')
        return dict(exports=len(self.entries), added=self.added, names=len(self.names), newNames=self.new_names,
                    imports=len(self.imports), addedImports=self.added_imports, importOffset=import_offset,
                    netObjects=self.net_objects,
                    exportOffset=export_offset, dependsOffset=depends_offset, nameOffset=name_offset,
                    appendedBytes=len(tail), chunks=len(entries), editsInPlace=len(self.edits),
                    sizeChange=len(out) - os.path.getsize(self.src))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src')
    a.add_argument('dst')
    args = a.parse_args()
    g = Grower(args.src)
    print(g.write(args.dst))


if __name__ == '__main__':
    main()
