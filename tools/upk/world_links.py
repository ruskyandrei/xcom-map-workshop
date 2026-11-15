"""
Reads and edits the pathing links (tile neighbour lists) baked in a map's XComWorldDataContainer (EXP-07).

A moved or copied ladder keeps its climb links at the old tiles: they are baked in the container, and the game's
runtime rebuild doesn't recreate them. This lists every link and moves one path object's links to new tiles.

The layout is in research/native-code-notes.md ("The rest of the container"). In short: a 12-byte header, then nine
chunked tile stores (two u32 fields sit between the eighth and the ninth). Each store is
  u32 chunk count (all chunks of the grid), TArray<i32> chunk list (the chunks saved), i32 NumX, NumY, NumZ,
  then per saved chunk, in ascending chunk index: u32 index, u32 present tiles, i32 X, Y, Z (tile origin), u32 18,
  then 18 x (element, u8 present), tile i = (X%3) + 3 * ((Y%3) + 3 * (Z%2)).
Store 3 holds FloorTileData, whose Neighbors list is an array of PathingTraversalData:
  i32 TileX, TileY, TileZ, f32 cost, i32 PathObject (export index, 0 = none),
  TArray<u8> TraversalTypes, TArray<FVector> Positions.

  python world_links.py layout <map.upk | container.bin>
  python world_links.py list   <map.upk | container.bin> [--all] [--object NAME_OR_INDEX]
  python world_links.py move   <map.upk | container.bin> <out.upk | out.bin> --object NAME_OR_INDEX
                               (--pivot X Y Z --location X Y Z [--yaw DEG] | --spec links.json)
                               [--origin X Y Z] [--tile SX SY SZ]

move: with --pivot/--location/--yaw, a point p goes to location + turn(p - pivot), turn by yaw in 90 degree steps
((dx, dy) -> (-dy, dx) for +90), as the project's copies do; a tile goes where its centre goes. --spec gives each
link's new tiles and positions instead, as a JSON list of
  {"from": [x, y, z], "to": [x, y, z], "new_from": [x, y, z], "new_to": [x, y, z], "positions": [[x, y, z], ...]}
("from"/"to" pick the link; the other keys are optional and default to the old values).
A link whose source tile changes leaves the old tile's list and is appended to the new one's. Every other byte is
kept, and the container keeps its size. The new source tiles must already have floor data (a present tile in a
saved chunk); the tool refuses otherwise rather than grow the container. A .upk output is the input package with
only the container's changed 128 KB blocks re-encoded (as literal LZO1X runs, like seed_tiles.py); the container
must be the package's last compressed chunk and the last thing in the file. Both outputs are read back and checked.
The default grid is URB_Bar's: origin (-2784, -1920, 0), tiles 96 x 96 x 64.
"""
import argparse, json, math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HEADER = 12          # NetIndex, then the FName None that ends the (empty) property list
CHUNK = (3, 3, 2)    # tiles per chunk
KINDS = ('flags', 'flags', 'floor', 'vector', 'interact', 'empty', 'empty', 'empty', 'empty')
NAMES = ('static flags', 'cover flags (likely)', 'floor data and neighbours', 'cover locations', 'interact points',
         'unknown, empty (fire?)', 'unknown, empty (smoke?)', 'unknown, empty (poison?)', 'unknown, empty')
FLOOR_STORE = 2
MIDDLE_AFTER = 8     # two u32 fields follow the eighth store
TRAVERSAL = ['None', 'Normal', 'ClimbOver', 'ClimbOnto', 'ClimbLadder', 'DropDown', 'Grapple', 'Landing',
             'BreakWindow', 'KickDoor', 'WallClimb', 'JumpUp', 'Ramp', 'BreakWall', 'Unreachable']
ORIGIN = (-2784.0, -1920.0, 0.0)
TILE = (96.0, 96.0, 64.0)


# ---------------------------------------------------------------------------------------------------------- parsing

def parse_link(b, o):
    """One PathingTraversalData at o: (dict, end offset)."""
    x, y, z, cost, obj = struct.unpack_from('<iiifi', b, o)
    p = o + 20
    nt = struct.unpack_from('<I', b, p)[0]; p += 4
    types = list(b[p:p + nt]); p += nt
    nv = struct.unpack_from('<I', b, p)[0]; p += 4
    pos = [struct.unpack_from('<3f', b, p + 12 * i) for i in range(nv)]; p += 12 * nv
    return dict(off=o, end=p, to=(x, y, z), cost=cost, obj=obj, types=types, pos=pos), p


def encode_link(l):
    out = struct.pack('<iiifi', l['to'][0], l['to'][1], l['to'][2], l['cost'], l['obj'])
    out += struct.pack('<I', len(l['types'])) + bytes(l['types'])
    out += struct.pack('<I', len(l['pos'])) + b''.join(struct.pack('<3f', *v) for v in l['pos'])
    return out


def parse_element(kind, b, o):
    """One tile's element of a store kind at o (the present byte not included): (value, end offset)."""
    if kind == 'flags':
        return struct.unpack_from('<I', b, o)[0], o + 4
    if kind == 'vector':
        return struct.unpack_from('<3f', b, o), o + 12
    if kind == 'floor':
        loc = struct.unpack_from('<3f', b, o); nrm = struct.unpack_from('<3f', b, o + 12)
        lo = o + 24
        n = struct.unpack_from('<I', b, lo)[0]; p = lo + 4
        links = []
        for _ in range(n):
            l, p = parse_link(b, p); links.append(l)
        ramp = b[p]; actor, volume = struct.unpack_from('<ii', b, p + 1)
        return dict(loc=loc, normal=nrm, links=links, list_off=lo, list_end=p, ramp=ramp, actor=actor,
                    volume=volume), p + 9
    if kind == 'interact':
        n = struct.unpack_from('<I', b, o)[0]; p = o + 4
        pts = []
        for _ in range(n):
            loc = struct.unpack_from('<3f', b, p); rot = struct.unpack_from('<3i', b, p + 12)
            actor, sock, sock_n, flags = struct.unpack_from('<iiii', b, p + 24)
            pts.append(dict(loc=loc, rot=rot, actor=actor, socket=(sock, sock_n), flags=flags)); p += 40
        return pts, p
    raise ValueError('no element format known for store kind %r (only seen empty)' % kind)


def chunk_index(x, y, z, dims):
    nx, ny = -(-dims[0] // CHUNK[0]), -(-dims[1] // CHUNK[1])
    return x // CHUNK[0] + nx * (y // CHUNK[1] + ny * (z // CHUNK[2]))


def parse_store(b, o, kind, name=''):
    """A chunked tile store at o. Checks the chunk list, every chunk header and every present count."""
    start = o
    nchunks, n = struct.unpack_from('<II', b, o); o += 8
    order = list(struct.unpack_from('<%di' % n, b, o)); o += 4 * n
    dims = struct.unpack_from('<3i', b, o); o += 12
    total = (-(-dims[0] // 3)) * (-(-dims[1] // 3)) * (-(-dims[2] // 2))
    if nchunks != total:
        raise ValueError('store at %d: chunk count %d, grid has %d' % (start, nchunks, total))
    chunks, last = [], -1
    for k in range(n):
        h = o
        seq, cnt, x, y, z, m = struct.unpack_from('<IIiiiI', b, o); o += 24
        if m != 18 or seq <= last or x % 3 or y % 3 or z % 2 or chunk_index(x, y, z, dims) != seq:
            raise ValueError('store at %d: bad chunk header %d at %d' % (start, k, h))
        last = seq
        tiles, present = [], 0
        for i in range(18):
            t0 = o
            v, o = parse_element(kind, b, o)
            p = b[o]; o += 1
            if p > 1:
                raise ValueError('store at %d: present byte %d at %d' % (start, p, o - 1))
            present += p
            tiles.append(dict(tile=(x + i % 3, y + (i // 3) % 3, z + i // 9), off=t0, end=o, present=p, value=v))
        if present != cnt:
            raise ValueError('store at %d: chunk %d says %d present tiles, has %d' % (start, seq, cnt, present))
        chunks.append(dict(seq=seq, count=cnt, origin=(x, y, z), off=h, end=o, tiles=tiles))
    if sorted(order) != [c['seq'] for c in chunks]:
        raise ValueError('store at %d: chunk list does not match the saved chunks' % start)
    return dict(kind=kind, name=name, off=start, end=o, nchunks=nchunks, order=order, dims=dims, chunks=chunks)


def parse_container(blob):
    """The whole XComWorldDataContainer export. Raises unless every store parses and the blob ends exactly."""
    netindex, none_i, none_n = struct.unpack_from('<iii', blob, 0)
    o, stores, middle = HEADER, [], None
    for k, kind in enumerate(KINDS):
        if k == MIDDLE_AFTER:
            middle = dict(off=o, values=struct.unpack_from('<II', blob, o)); o += 8
        s = parse_store(blob, o, kind, NAMES[k]); stores.append(s); o = s['end']
        if s['dims'] != stores[0]['dims']:
            raise ValueError('store %d has other dimensions' % (k + 1))
    if o != len(blob):
        raise ValueError('parsed to %d, the container has %d bytes' % (o, len(blob)))
    tiles = {}
    for c in stores[FLOOR_STORE]['chunks']:
        for t in c['tiles']:
            if t['present']:
                tiles[t['tile']] = t
            elif t['value']['links']:
                raise ValueError('absent tile %s has links' % (t['tile'],))
    return dict(size=len(blob), header=(netindex, none_i, none_n), stores=stores, middle=middle,
                dims=stores[0]['dims'], floor=tiles)


def all_links(wd):
    """Every link: dicts with 'from' (the tile whose list holds it), its index there, and the record fields."""
    out = []
    for key in sorted(wd['floor'], key=lambda t: (t[2], t[1], t[0])):
        for i, l in enumerate(wd['floor'][key]['value']['links']):
            out.append(dict(l, **{'from': key, 'index': i}))
    return out


def self_check(blob, wd):
    """Re-encodes every present floor tile's neighbour list and compares it with the saved bytes."""
    for t in wd['floor'].values():
        v = t['value']
        enc = struct.pack('<I', len(v['links'])) + b''.join(encode_link(l) for l in v['links'])
        if enc != blob[v['list_off']:v['list_end']]:
            raise ValueError('re-encoding tile %s does not reproduce its bytes' % (t['tile'],))


# ------------------------------------------------------------------------------------------------- package access

def read_input(path):
    """(blob, names or None, package info or None). names maps export index -> object name."""
    if not path.lower().endswith('.upk'):
        return open(path, 'rb').read(), None, None
    import upkinfo, decomp
    raw = open(path, 'rb').read()
    h = upkinfo.summary(raw)
    full, _ = decomp.decompress_pkg(path)
    _, imps, exps = upkinfo.tables(full, h)
    conts = [e for e in exps if upkinfo.clsname(e['cls'], imps, exps) == 'XComWorldDataContainer']
    if len(conts) != 1:
        raise ValueError('expected one XComWorldDataContainer, found %d' % len(conts))
    ce = conts[0]
    names = {i + 1: e['name'] for i, e in enumerate(exps)}
    return full[ce['off']:ce['off'] + ce['size']], names, dict(raw=raw, h=h, full=full, cont=ce)


def resolve_object(spec, names):
    if str(spec).lstrip('-').isdigit():
        return int(spec)
    if not names:
        raise SystemExit('give the path object as an export index, or read a .upk to use names')
    hits = [i for i, n in names.items() if n == spec]
    if len(hits) != 1:
        raise SystemExit('%d exports are named %s' % (len(hits), spec))
    return hits[0]


def write_package(pkg, dst, newblob):
    """Writes dst: the package pkg (from read_input) with its container replaced by newblob of the same size.

    Only the container chunk's changed blocks are re-encoded; the chunk table entry gets the new compressed size.
    The written file is decoded again and compared with the intended bytes."""
    import upkinfo, decomp, lzo1x, seed_tiles
    raw, h, full, ce = pkg['raw'], pkg['h'], pkg['full'], pkg['cont']
    if len(newblob) != ce['size']:
        raise ValueError('the container changed size; this writer cannot update the package for that')
    ci = [i for i, (uo, us, co, cs) in enumerate(h['chunks']) if uo == ce['off'] and us == ce['size']]
    if not ci:
        raise ValueError('the container is not a compressed chunk of its own')
    ci = ci[0]
    uo, us, co, cs = h['chunks'][ci]
    if co + cs != len(raw):
        raise ValueError('the container chunk is not the last thing in the file; offsets would shift')
    r = upkinfo.R(raw, co)
    tag, bsz, csum, usum = r.u32(), r.u32(), r.u32(), r.u32()
    nb = (usum + bsz - 1) // bsz
    blocks = [(r.u32(), r.u32()) for _ in range(nb)]
    p, newblocks, payload = r.o, [], b''
    for k, (c, u) in enumerate(blocks):
        old = raw[p:p + c]; p += c
        part = bytes(newblob[k * bsz:k * bsz + u])
        if part == full[uo + k * bsz:uo + k * bsz + u]:
            enc = old
        else:
            enc = seed_tiles.lzo_literals(part)
            if lzo1x.decompress(enc, u) != part:
                raise ValueError('literal LZO round trip failed on block %d' % k)
        newblocks.append((len(enc), u)); payload += enc
    newchunk = struct.pack('<IIII', tag, bsz, sum(c for c, u in newblocks), usum)
    newchunk += b''.join(struct.pack('<II', c, u) for c, u in newblocks) + payload
    out = bytearray(raw[:co] + newchunk)
    t = seed_tiles.chunk_table_offset(raw)
    ent = t + 4 + 16 * ci
    if struct.unpack_from('<I', raw, t)[0] != len(h['chunks']) or struct.unpack_from('<IIII', raw, ent) != (uo, us, co, cs):
        raise ValueError('chunk table not where expected')
    struct.pack_into('<IIII', out, ent, uo, us, co, len(newchunk))
    open(dst, 'wb').write(out)
    full2, h2 = decomp.decompress_pkg(dst)
    expect = bytearray(full)
    struct.pack_into('<IIII', expect, ent, uo, us, co, len(newchunk))
    expect[uo:uo + us] = newblob
    if bytes(full2) != bytes(expect):
        raise ValueError('verification failed: the written package does not decode to the intended bytes')
    if [c for i, c in enumerate(h2['chunks']) if i != ci] != [c for i, c in enumerate(h['chunks']) if i != ci]:
        raise ValueError('verification failed: other chunk table entries changed')
    return len(newchunk) - cs


# ------------------------------------------------------------------------------------------------------ moving

def turn(dx, dy, yaw):
    k = int(round(yaw / 90.0)) % 4
    return [(dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)][k]


def transform(pivot, location, yaw):
    if abs(yaw / 90.0 - round(yaw / 90.0)) > 1e-6:
        raise ValueError('yaw must be a multiple of 90 degrees')

    def f(p):
        dx, dy = turn(p[0] - pivot[0], p[1] - pivot[1], yaw)
        return (location[0] + dx, location[1] + dy, p[2] + location[2] - pivot[2])
    return f


def tile_mover(f, origin=ORIGIN, size=TILE):
    """Maps a tile to the tile its centre moves to. Refuses a move that doesn't take centres to centres."""
    def g(t):
        c = [origin[i] + (t[i] + 0.5) * size[i] for i in range(3)]
        m = f(c)
        u = [(m[i] - origin[i]) / size[i] - 0.5 for i in range(3)]
        if any(abs(v - round(v)) > 1e-3 for v in u):
            raise ValueError('the move takes tile %s off the grid (centre to %s); give the tiles with --spec'
                             % (t, tuple(round(v, 2) for v in m)))
        return tuple(int(round(v)) for v in u)
    return g


def plan_from_transform(links, f, g):
    return [dict(l, new_from=g(l['from']), new_to=g(l['to']), new_pos=[f(p) for p in l['pos']]) for l in links]


def plan_from_spec(links, spec):
    out, used = [], set()
    for s in spec:
        hits = [k for k, l in enumerate(links) if list(l['from']) == list(s['from']) and list(l['to']) == list(s['to'])]
        if len(hits) != 1:
            raise ValueError('spec entry %s/%s matches %d links of the object' % (s['from'], s['to'], len(hits)))
        k = hits[0]
        if k in used:
            raise ValueError('two spec entries pick the same link')
        used.add(k)
        l = links[k]
        pos = [tuple(float(v) for v in p) for p in s.get('positions', l['pos'])]
        out.append(dict(l, new_from=tuple(s.get('new_from', l['from'])), new_to=tuple(s.get('new_to', l['to'])),
                        new_pos=pos))
    return out


def move_links(blob, obj, plan):
    """The container blob with the planned links moved. plan: links of obj (from all_links) with new_from, new_to
    and new_pos. Returns (new blob, list of (old link, new link) dicts with offsets in the new blob)."""
    wd = parse_container(blob)
    dims = wd['dims']
    lists = {}          # tile -> list of record bytes, for every tile whose list changes

    def get(key):
        if key not in lists:
            t = wd['floor'].get(key)
            if t is None:
                raise ValueError('tile %s has no floor data (absent tile or chunk); refusing to add one' % (key,))
            lists[key] = [blob[l['off']:l['end']] for l in t['value']['links']]
        return lists[key]

    for m in plan:
        if m['obj'] != obj:
            raise ValueError('plan holds a link of another object')
        for key in (m['new_from'], m['new_to']):
            if not all(0 <= key[i] < dims[i] for i in range(3)):
                raise ValueError('tile %s is outside the world' % (key,))
        if len(m['new_pos']) != len(m['pos']):
            raise ValueError('a moved link must keep its number of positions (the container keeps its size)')
    picked = {}         # (tile, index in its list) -> plan entry number
    for k, m in enumerate(plan):
        if (m['from'], m['index']) in picked:
            raise ValueError('the plan moves one link twice')
        picked[(m['from'], m['index'])] = k
    new_rec = [encode_link(dict(m, to=m['new_to'], pos=m['new_pos'])) for m in plan]
    # Links that stay on their tile are replaced in place; the others leave their tile and go to the end of the new one.
    for key in sorted(set(m['from'] for m in plan)):
        keep = []
        for i, rec in enumerate(get(key)):
            k = picked.get((key, i))
            if k is None:
                keep.append(rec)
            elif plan[k]['new_from'] == key:
                keep.append(new_rec[k])
        lists[key] = keep
    for k, m in enumerate(plan):
        if m['new_from'] != m['from']:
            get(m['new_from']).append(new_rec[k])

    edits = []
    for key, recs in lists.items():
        v = wd['floor'][key]['value']
        edits.append((v['list_off'], v['list_end'], struct.pack('<I', len(recs)) + b''.join(recs)))
    out = bytearray(blob)
    for a, e, data in sorted(edits, reverse=True):
        out[a:e] = data
    out = bytes(out)
    if len(out) != len(blob):
        raise ValueError('internal: the container changed size')
    check_move(blob, out, obj, plan, set(lists))
    wd2 = parse_container(out)
    pairs = []
    for m in plan:
        t = wd2['floor'][m['new_from']]['value']['links']
        hit = [l for l in t if l['obj'] == obj and l['to'] == m['new_to']]
        pairs.append((m, dict(hit[0], **{'from': m['new_from']})))
    return out, pairs


def check_move(old, new, obj, plan, touched):
    """Re-parses the moved container and checks that only the planned links changed."""
    a, b = parse_container(old), parse_container(new)
    for k, (s, t) in enumerate(zip(a['stores'], b['stores'])):
        if (s['off'], s['end']) != (t['off'], t['end']):
            raise ValueError('check: store %d moved' % (k + 1))
        if k != FLOOR_STORE and old[s['off']:s['end']] != new[t['off']:t['end']]:
            raise ValueError('check: store %d changed' % (k + 1))
    if old[:HEADER] != new[:HEADER] or old[a['middle']['off']:a['middle']['off'] + 8] != new[a['middle']['off']:a['middle']['off'] + 8]:
        raise ValueError('check: header or middle fields changed')
    fs, ft = a['stores'][FLOOR_STORE], b['stores'][FLOOR_STORE]
    if (old[fs['off']:fs['chunks'][0]['off']] != new[ft['off']:ft['chunks'][0]['off']]
            or len(fs['chunks']) != len(ft['chunks'])):
        raise ValueError('check: floor store header or chunk list changed')
    for c, d in zip(fs['chunks'], ft['chunks']):
        if old[c['off']:c['off'] + 24] != new[d['off']:d['off'] + 24]:
            raise ValueError('check: chunk header %d changed' % c['seq'])
        for s, t in zip(c['tiles'], d['tiles']):
            sb, tb = old[s['off']:s['end']], new[t['off']:t['end']]
            if s['tile'] not in touched:
                if sb != tb:
                    raise ValueError('check: tile %s changed' % (s['tile'],))
                continue
            sv, tv = s['value'], t['value']
            # Everything but the list is kept byte for byte.
            if (old[s['off']:sv['list_off']] != new[t['off']:tv['list_off']]
                    or old[sv['list_end']:s['end']] != new[tv['list_end']:t['end']]):
                raise ValueError('check: tile %s changed outside its list' % (s['tile'],))
    key = lambda l: (l['from'], l['to'], l['cost'], l['obj'], tuple(l['types']), tuple(l['pos']))
    others = lambda wd: sorted(key(l) for l in all_links(wd) if l['obj'] != obj)
    if others(a) != others(b):
        raise ValueError('check: links of other objects changed')
    want = sorted(key(dict(m, **{'from': m['new_from'], 'to': m['new_to'],
                                  'pos': [struct.unpack('<3f', struct.pack('<3f', *p)) for p in m['new_pos']]}))
                  for m in plan)
    want += sorted(key(l) for l in all_links(a) if l['obj'] == obj
                   and not any(l['from'] == m['from'] and l['index'] == m['index'] for m in plan))
    got = sorted(key(l) for l in all_links(b) if l['obj'] == obj)
    if sorted(want) != got:
        raise ValueError('check: the moved links are not as planned')


# ------------------------------------------------------------------------------------------------------- output

def fmt_vec(v):
    return '(%s)' % ', '.join('%g' % round(c, 3) for c in v)


def fmt_link(l, names=None):
    nm = (names or {}).get(l['obj'], '') if l['obj'] else ''
    types = ','.join(TRAVERSAL[t] if t < len(TRAVERSAL) else str(t) for t in l['types'])
    return '\t'.join([str(tuple(l['from'])), str(tuple(l['to'])), '%.3f' % l['cost'], str(l['obj']), nm, types,
                      ' '.join(fmt_vec(p) for p in l['pos']), str(l['off'])])


LIST_HEAD = 'from\tto\tcost\tobject\tname\ttypes\tpositions\toffset'


def cmd_layout(args):
    blob, names, _ = read_input(args.input)
    wd = parse_container(blob)
    self_check(blob, wd)
    print('container: %d bytes, header NetIndex %d, FName (%d, %d); grid %s' % ((wd['size'],) + wd['header'] + (wd['dims'],)))
    for k, s in enumerate(wd['stores']):
        if k == MIDDLE_AFTER:
            print('  %9d  u32 %d, u32 %d (unknown)' % ((wd['middle']['off'],) + wd['middle']['values']))
        pres = sum(c['count'] for c in s['chunks'])
        print('  %9d-%9d  store %d %-26s %4d of %d chunks saved, %5d tiles present'
              % (s['off'], s['end'], k + 1, s['name'], len(s['chunks']), s['nchunks'], pres))
    links = all_links(wd)
    print('floor tiles with data: %d; links: %d, %d with a path object; parsed to the end; lists re-encode exactly'
          % (len(wd['floor']), len(links), sum(1 for l in links if l['obj'])))


def cmd_list(args):
    blob, names, _ = read_input(args.input)
    wd = parse_container(blob)
    links = all_links(wd)
    if args.object is not None:
        obj = resolve_object(args.object, names)
        links = [l for l in links if l['obj'] == obj]
    elif not args.all:
        links = [l for l in links if l['obj']]
    print(LIST_HEAD)
    for l in links:
        print(fmt_link(l, names))


def cmd_move(args):
    if os.path.abspath(args.output) == os.path.abspath(args.input):
        raise SystemExit('refusing to overwrite the input')
    blob, names, pkg = read_input(args.input)
    wd = parse_container(blob)
    obj = resolve_object(args.object, names)
    links = [l for l in all_links(wd) if l['obj'] == obj]
    if not links:
        raise SystemExit('no links use path object %s' % args.object)
    if args.spec:
        plan = plan_from_spec(links, json.load(open(args.spec)))
    else:
        if not (args.pivot and args.location):
            raise SystemExit('give --pivot and --location (and --yaw), or --spec')
        f = transform(args.pivot, args.location, args.yaw)
        plan = plan_from_transform(links, f, tile_mover(f, args.origin, args.tile))
    out, pairs = move_links(blob, obj, plan)
    if args.output.lower().endswith('.upk'):
        if not pkg:
            raise SystemExit('a .upk output needs a .upk input')
        grow = write_package(pkg, args.output, out)
        back, _, _ = read_input(args.output)
        note = 'package written and decoded again; container chunk %+d compressed bytes' % grow
    else:
        open(args.output, 'wb').write(out)
        back = open(args.output, 'rb').read()
        note = 'container written'
    if back != out:
        raise SystemExit('read-back mismatch')
    parse_container(back)
    print('before\t' + LIST_HEAD)
    for m, _ in pairs:
        print('before\t' + fmt_link(m, names))
    for _, n in pairs:
        print('after\t' + fmt_link(n, names))
    print('moved %d link(s) of %s; %s; re-parsed, all other bytes kept, size unchanged (%d)'
          % (len(pairs), names.get(obj, obj) if names else obj, note, len(out)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('layout'); p.add_argument('input'); p.set_defaults(func=cmd_layout)
    p = sub.add_parser('list'); p.add_argument('input'); p.add_argument('--all', action='store_true')
    p.add_argument('--object'); p.set_defaults(func=cmd_list)
    p = sub.add_parser('move'); p.add_argument('input'); p.add_argument('output'); p.add_argument('--object', required=True)
    p.add_argument('--pivot', nargs=3, type=float); p.add_argument('--location', nargs=3, type=float)
    p.add_argument('--yaw', type=float, default=0.0); p.add_argument('--spec')
    p.add_argument('--origin', nargs=3, type=float, default=list(ORIGIN))
    p.add_argument('--tile', nargs=3, type=float, default=list(TILE))
    p.set_defaults(func=cmd_move)
    args = ap.parse_args()
    try:
        args.func(args)
    except ValueError as e:
        raise SystemExit('error: %s' % e)


if __name__ == '__main__':
    main()
