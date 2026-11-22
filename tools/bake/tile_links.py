"""The game's neighbour links: the link step of its tile build for one tile (0x905780 and its callees) and the ladders'
links (0x777580), as research/native/neighbour-links.md reads them (findings register F-154). Checked against the
install's maps by research/evidence/neighbour-links-check.py: 99.96% of 2,140,357 baked links, every typed link.

  Map(p)                      a map's baked tile data as the link step reads it (static and cover flags, floor
                              records, cover locations, interact points); a Build's computed tiles fill the same
                              fields (diagonal_keep.py)
  Predictor(m, world, p)      .tile(t): a floor tile's links in the build's order; .ladders(lists): the ladders'
                              links added; .stand2x2(t): bit 0x100000; .drop_bits: the tiles that get 0x200000

world is a tile_world.World of the map's pieces, for the build's traces (the diagonal sweep, the path objects' lines).
"""
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))

TILE = (96.0, 96.0, 64.0)
FLOOR, RAMP, OCCUPIED, PARTLY = 0x2000, 0x4000, 0x8000, 0x10000
UP_BLOCKED, DOWN_BLOCKED = 0x40, 0x20
STAND2X2, DROP2 = 0x100000, 0x200000
NORMAL, CLIMB_OVER, CLIMB_ONTO, LADDER, DROP_DOWN, LANDING, KICK_DOOR, WALL_CLIMB, JUMP_UP = 1, 2, 3, 4, 5, 7, 9, 10, 11
NAMES = {(): 'plain', (2, 7): 'ClimbOver', (3, 7): 'ClimbOnto', (4, 7): 'ClimbLadder', (5, 7): 'DropDown',
         (9, 7): 'KickDoor', (10, 7): 'WallClimb', (11, 7): 'JumpUp'}

# 0x905780's table of the eight directions (a stack table built at its start): (dx, dy), A = the tile's own pathing
# bit toward the neighbour, B = the neighbour's bit back, C = the ClimbOver cover bit, D = the ClimbOnto cover bit,
# E = the cover bit, F = the low cover bit (cover-build.md section 4's table: E is toward -X, W toward +X)
DIRS = [
    ((-1, 0), 0x02, 0x04, 0x800000, 0x80000, 0x4, 0x40),
    ((1, 0), 0x04, 0x02, 0x1000000, 0x100000, 0x8, 0x80),
    ((0, -1), 0x08, 0x10, 0x400000, 0x40000, 0x2, 0x20),
    ((0, 1), 0x10, 0x08, 0x200000, 0x20000, 0x1, 0x10),
    ((-1, 1), 0x12, 0x0C, 0x800000, 0x80000, 0x4, 0x40),
    ((1, 1), 0x14, 0x0A, 0x1000000, 0x100000, 0x8, 0x80),
    ((1, -1), 0x0C, 0x12, 0x400000, 0x40000, 0x2, 0x20),
    ((-1, -1), 0x0A, 0x14, 0x200000, 0x20000, 0x1, 0x10),
]
DIAGONAL_SWEEP = (24.0, 24.0, 4.0)      # 0x905780: the MultiLineCheck's box (half-size), 24 over each floor
DESTRUCTIBLE = ('XComDestructibleActor', 'XComCollectible', 'XComDestructibleDebrisActor',
                'XComDestructibleSkeletalMeshActor', 'XComFriendlyDestructibleActor',
                'XComFriendlyDestructibleSkeletalMeshActor', 'XComInteractiveLevelActor', 'XComRadarArrayActor')


def full(f):
    return bool(f & OCCUPIED) and not f & PARTLY


class Map:
    """A map's baked tile data as the link step reads it."""

    def __init__(self, p):
        import native_copy
        import world_grid
        import world_links
        self.p = p
        grid = native_copy.level_grid(p)
        self.corner = (grid['tx'], grid['ty'], grid['tz'])
        _, blob = world_grid.container_of(p)
        wd = world_links.parse_container(blob)
        self.dims = tuple(wd['dims'])

        def store(k):
            return {t['tile']: t['value'] for c in wd['stores'][k]['chunks'] for t in c['tiles'] if t['present']}
        self.static, self.cover, self.floor, self.coverloc, self.interact = (store(k) for k in range(5))

    def flag(self, t):
        return self.static.get(tuple(t), 0)

    def wrapped(self, t):
        """The tile a store read of `t` lands on when nothing checks the grid first (0x745380 and its inline copies):
        the chunk index (z/2)*L + (y/3)*R + x/3 (R chunks a row, L a layer) runs on into the next row or layer, so x
        = NX with NX a multiple of 3 reads (0, y + 3, z); a slot outside the grid, or an index past the last chunk,
        reads as absent (None)."""
        x, y, z = t
        if min(x, y, z) < 0:
            return None
        r = -(-self.dims[0] // 3)
        layer = r * -(-self.dims[1] // 3)
        idx = (z // 2) * layer + (y // 3) * r + x // 3
        if idx >= layer * -(-self.dims[2] // 2):
            return None
        cz, rem = divmod(idx, layer)
        cy, cx = divmod(rem, r)
        w = (cx * 3 + x % 3, cy * 3 + y % 3, cz * 2 + z % 2)
        return w if self.inside(w) else None

    def raw_flag(self, t):
        w = self.wrapped(t)
        return 0 if w is None else self.flag(w)

    def cov(self, t):
        return self.cover.get(tuple(t), 0)

    def inside(self, t):
        return all(0 <= t[k] < self.dims[k] for k in range(3))

    def position(self, t):
        """0xD5B5E0: the corner + (96x + 48, 96y + 48, 64z + 32)."""
        return np.array([self.corner[k] + TILE[k] * t[k] + TILE[k] / 2 for k in range(3)])

    def at(self, point):
        return tuple(int(math.floor((point[k] - self.corner[k]) / TILE[k])) for k in range(3))

    def floor_z(self, t):
        rec = self.floor.get(tuple(t))
        return rec['loc'][2] if rec else None


def link(to, cost=1.0, types=(), obj=0, pos=()):
    return dict(to=tuple(to), cost=cost, types=tuple(types), obj=obj, pos=[tuple(float(c) for c in q) for q in pos])


class Predictor:
    """0x905780 and its callees for every tile, then the ladders (0x777580), as the full build runs them."""

    def __init__(self, m, world, p):
        self.m, self.world, self.p = m, world, p
        self.why = []            # (tile, neighbour, kind, cause) of every link not made where a plain rule might
        self.sweeps = {}         # (tile, neighbour) -> the diagonal sweep's hit piece name or None
        self.drop_bits = set()
        self.notes = Counter()
        self._iactor = {}

    # ---------------------------------------------------------------- one tile (0x905780)
    def tile(self, t):
        m = self.m
        st = m.flag(t)
        cf = m.cov(t)
        out = []
        if not st & FLOOR:
            return out
        x, y, z = t
        nz = m.dims[2]
        frec = m.floor[t]
        ramp = bool(st & RAMP)
        above = m.flag((x, y, z + 1)) if z + 1 < nz else None
        for dz in (-1, 0, 1):
            for i, ((dx, dy), A, B, C, D, E, F) in enumerate(DIRS):
                n = (x + dx, y + dy, z + dz)
                if not m.inside(n):
                    continue
                stn = m.flag(n)
                diag = i > 3
                # F+50: the tile above has its own bit that way (no tile above: always); units are not read here
                head = True if above is None else bool(above & A)
                # F+44: the tile's bit toward the neighbour, the neighbour's bit back
                blocked = bool(st & A) or bool(stn & B)
                if stn & FLOOR:
                    step_ok = True
                    hit = None
                    if diag:
                        hit = self.diagonal(t, n)
                        blocked = blocked or hit is not None
                    if dz:
                        nrec = m.floor[n]
                        if not ramp:
                            dot = sum(frec['normal'][k] * nrec['normal'][k] for k in range(3))
                            step_ok = bool(stn & RAMP) or (dot > 0.996 and abs(frec['loc'][2] - nrec['loc'][2]) < 32)
                    if not blocked and not head:
                        if step_ok:
                            out.append(link(n, 1.414 if diag else 1.0))
                        else:
                            self.why.append((t, n, 'plain', 'step'))
                    else:
                        cause = ('own bit' if st & A else 'target bit' if stn & B else
                                 'diagonal sweep' if hit is not None else '') + \
                                (' head' if head else '')
                        self.why.append((t, n, 'plain', cause.strip()))
                        if not diag:
                            out += self.climb(t, n, (dx, dy), cf, C & cf, D & cf)
                            if dz == 0 or abs(m.floor[n]['loc'][2] - frec['loc'][2]) < 32:
                                out += self.kick_door(t, n, (dx, dy, dz), (E & cf) == 0)
                    if not diag and dz == 0:
                        out += self.jump_up(t, n, (dx, dy))
                else:
                    if not diag and dz == 0:
                        if z > 0:
                            c = E & cf
                            if (not c and not head) or (c and F & cf):
                                out += self.drop_down(t, n, (dx, dy), st)
                            out += self.climb(t, n, (dx, dy), cf, C & cf, D & cf)
                        out += self.jump_up(t, n, (dx, dy))
        return out

    def diagonal(self, t, n):
        """The diagonal's MultiLineCheck: a box (24, 24, 4) from 24 over the tile's floor to 24 over the neighbour's,
        flags 0x860D3 (taken as tile_world's 'engine': level geometry). The hit piece's name, or None."""
        m = self.m
        a = m.position(t)
        b = m.position(n)
        a[2] = m.floor_z(t) + 24.0
        b[2] = m.floor_z(n) + 24.0
        h = self.world.trace(a, b, DIAGONAL_SWEEP, 'engine')
        self.sweeps[(t, n)] = (a, b, h)
        self.notes['diagonal sweeps'] += 1
        if h is not None:
            self.notes['diagonal sweeps that met a piece'] += 1
        return None if h is None else h['piece'].name

    # ---------------------------------------------------------------- ClimbOver / ClimbOnto (0x78B680)
    def climb(self, t, n, d, cf, over, onto):
        if not over and not onto:
            return []
        m = self.m
        cl = m.coverloc.get(t, (0.0, 0.0, 0.0))
        off = (108.0 * d[0], 108.0 * d[1], 0.0) if over else (80.0 * d[0], 80.0 * d[1], 68.0)
        far = (cl[0] + off[0], cl[1] + off[1], cl[2] + off[2])
        target = m.at(far) if over else n       # (GetTileCoordinatesFromPosition: not checked against the grid)
        if not m.raw_flag(target) & FLOOR:
            self.notes['climb: target without floor'] += 1
            return []
        zt, zg = m.floor_z(t), m.floor_z(m.wrapped(target))
        if zg is None:
            self.notes['climb: target without record'] += 1
            return []
        if over and not abs(zg) - abs(zt) < 32:
            self.notes['climb over: target 32 or more higher'] += 1
            return []
        if not over and not zg - zt > 32:
            self.notes['climb onto: target not more than 32 higher'] += 1
            return []
        # the path object: a SingleLineCheck (0x860C0) at 96 over the tile's position, from 135.744 (cover flags in
        # their low 16 bits) or 124 out back to the tile: an XComDestructibleActor that is bInteractive
        p = m.position(t)
        length = 135.744 if cf & 0xFFFF else 124.0
        start = p + (length * d[0], length * d[1], 96.0)
        end = p + (0.0, 0.0, 96.0)
        obj = self.interactive_hit(start, end, False)
        if obj:
            self.notes['climb: path object (an interactive destructible on the line)'] += 1
        return [link(target, 1.0, (CLIMB_OVER if over else CLIMB_ONTO, LANDING), obj, (cl, far))]

    def interactive_hit(self, start, end, not_door):
        h = self.world.trace(start, end, (0.0, 0.0, 0.0), 'engine')
        if h is None:
            return 0
        pc = h['piece']
        if pc.cls in DESTRUCTIBLE and pc.flags.get('bInteractive') and \
                not (not_door and pc.cls == 'XComInteractiveLevelActor'):
            return pc.actor
        return 0

    # ---------------------------------------------------------------- KickDoor (0xC0DE50)
    def iactor(self, a):
        """(skipped, why) for an interact point's actor: more than 6 InteractionPoints (+0x374 read as that array's
        count) or bTouchActivated (+0x398 bit 4)."""
        if a not in self._iactor:
            import tile_world
            rv = self.world.resolver or tile_world.Resolver(self.p)
            raw = rv.value(a, 'InteractionPoints') if a > 0 else None
            count = int.from_bytes(raw[:4], 'little') if isinstance(raw, (bytes, bytearray)) and len(raw) >= 4 else 0
            touch = bool(rv.value(a, 'bTouchActivated', False)) if a > 0 else False
            self._iactor[a] = (count > 6 or touch, count, touch)
        return self._iactor[a]

    def kick_door(self, t, n, delta, no_cover):
        m = self.m
        out = []
        pt_ = m.position(t)
        pn = m.position(n)
        v = pn - pt_
        v = v / max(np.linalg.norm(v), 1e-8)
        second = tuple(pn + 8.0 * v)
        for ip in m.interact.get(t, []) or []:
            skipped, count, touch = self.iactor(ip['actor'])
            f = ip['flags']
            if not f:
                continue
            way = f & 2 and delta[0] < 0 or f & 4 and delta[0] > 0 or f & 8 and delta[1] < 0 or f & 0x10 and delta[1] > 0
            if skipped:
                if way:
                    self.notes['kick door: point passed by (%s)' % ('touch activated' if touch else
                                                                    'more than 6 InteractionPoints')] += 1
                continue
            if way:
                self.notes['kick door: from an interact point'] += 1
                out.append(link(n, 1.0, (KICK_DOOR, LANDING), ip['actor'], (pt_, second)))
                break
        if no_cover:
            rec = m.floor[t]
            fl = np.array(rec['loc'], float)
            end = fl + (0.0, 0.0, 96.0)
            start = end + 124.0 * np.array(delta, float)
            obj = self.interactive_hit(start, end, True)
            if obj:
                self.notes['kick door: from an interactive destructible on the line'] += 1
                out.append(link(n, 1.0, (KICK_DOOR, LANDING), obj, (pt_, second)))
        return out

    # ---------------------------------------------------------------- DropDown (0xD8F610)
    def drop_down(self, t, n, d, st):
        m = self.m
        nz = m.dims[2]
        found = None
        for k in range(0, -11, -1):
            zz = n[2] + k
            if zz <= -1:
                continue
            tt = (n[0], n[1], zz)
            f = m.flag(tt)
            up = min(zz + 1, nz - 1)
            above = m.flag((n[0], n[1], up)) if up != zz else 0
            if full(f) or f & UP_BLOCKED or above & DOWN_BLOCKED:
                return []
            if k < -1:
                self.drop_bits.add(t)
            if f & FLOOR:
                found = tt
                break
        if found is None:
            return []
        if st & RAMP and not t[2] - found[2] > 1:
            return []
        zt, zf = m.floor_z(t), m.floor_z(found)
        if not abs(zt - zf) > 32:
            self.notes['drop: 32 or less'] += 1
            return []
        a = m.position(t) + (20.0 * d[0], 20.0 * d[1], -4.0)
        b = m.position(found) + (16.0 * d[0], 16.0 * d[1], -4.0)
        return [link(found, 1.0, (DROP_DOWN, LANDING), 0, (a, b))]

    # ---------------------------------------------------------------- JumpUp / WallClimb (0xAA88C0)
    def jump_up(self, t, n, d):
        m = self.m
        nz = m.dims[2]
        if d[0] > 0:
            A, B, oc, ol = 0x4, 0x2, 0x4, 0x40
        elif d[0] < 0:
            A, B, oc, ol = 0x2, 0x4, 0x8, 0x80
        elif d[1] > 0:
            A, B, oc, ol = 0x10, 0x8, 0x2, 0x20
        else:
            A, B, oc, ol = 0x8, 0x10, 0x1, 0x10
        wall, count, prev = True, 0, None
        for k in range(11):
            if n[2] + k + 1 >= nz:
                continue
            tk = (t[0], t[1], t[2] + k)
            nk = (n[0], n[1], n[2] + k)
            ft = m.flag(tk)
            if full(ft):
                return []
            if k > 0 and (ft & DOWN_BLOCKED or (prev or 0) & UP_BLOCKED):
                return []
            fn, cn = m.flag(nk), m.cov(nk)
            above_n = m.flag((n[0], n[1], n[2] + k + 1))
            above_t = m.flag((t[0], t[1], t[2] + k + 1))
            if fn & FLOOR and count > 1:
                head = bool(above_t & A) or bool(above_n & B)
                c = cn & oc
                if (not c and not head) or (c and cn & ol):
                    pos = (m.position(t), m.position(nk))
                    out = [link(nk, 1.0, (JUMP_UP, LANDING), 0, pos)]
                    if wall:
                        out.append(link(nk, 1.0, (WALL_CLIMB, LANDING), 0, pos))
                    return out
            wall = wall and (bool(ft & A) or bool(fn & B))
            prev = ft
            count += 1
        return []

    # ---------------------------------------------------------------- ladders (0x777580, once for all after every tile)
    def ladder_frame(self, a):
        """(matrix, height) of a ladder: its mesh component's world matrix (the actor's LocalToWorld when the
        component sits at the actor) and GetHeight, max(Bounds.Max.Z, Location.Z) - min(Bounds.Min.Z, Location.Z),
        its Bounds as UE3's UStaticMeshComponent::UpdateBounds makes them: the mesh's bounds box united with its
        collision's box, in the world, grown by 1 on every side."""
        import lightmap_texels
        import tile_world
        p = self.p
        for c in tile_world.World._components(self.world, a):
            mi = p.effective(c, 'StaticMesh', 0)
            mtx = lightmap_texels.world_matrix(p, c)
            ox, oy, oz, ex, ey, ez, _ = p.native(mi).unpack('7f')
            pts = [np.array([[ox + sx * ex, oy + sy * ey, oz + sz * ez] for sx in (-1, 1) for sy in (-1, 1)
                             for sz in (-1, 1)])]
            pts += [verts for verts, _f, _e, _b in self.world._mesh(mi).solids]
            z = np.vstack(pts) @ mtx[:3, :3].T[:, 2] + mtx[2, 3]
            loc_z = (p.effective(a, 'Location', [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0])[2]
            return mtx, max(float(z.max()) + 1.0, loc_z) - min(float(z.min()) - 1.0, loc_z)
        return None, None

    def ladders(self, lists):
        import native_copy
        m, p = self.m, self.p
        nz = m.dims[2]
        for a in native_copy.level_actors(p):
            if a <= 0 or p.cls(a) != 'XComLadder':
                continue
            mtx, h = self.ladder_frame(a)
            if h is None:
                self.notes['ladder without mesh'] += 1
                continue
            # top (76, 0, h + 8) and foot (-16, 0, 8) in the ladder's frame
            top = tuple(float(v) for v in mtx[:3, :3] @ (76.0, 0.0, h + 8.0) + mtx[:3, 3])
            foot = tuple(float(v) for v in mtx[:3, :3] @ (-16.0, 0.0, 8.0) + mtx[:3, 3])
            # (only z is checked against the grid; x and y are read as they come)
            tt = m.at(top)
            ok = -1 < tt[2] < nz and m.raw_flag(tt) & FLOOR
            if not ok:
                tt = (tt[0], tt[1], tt[2] - 1)
                ok = 0 < tt[2] < nz and m.raw_flag(tt) & FLOOR
            bt = m.at(foot)
            if not ok or not (-1 < bt[2] < nz and m.raw_flag(bt) & FLOOR):
                self.notes['ladder without both floors'] += 1
                continue
            down = link(bt, 1.0, (LADDER, LANDING), a, (top, foot))
            lst = lists.setdefault(m.wrapped(tt), [])     # (the store is written where the read wraps to)
            # the first DropDown link of the top tile goes (the loop ends at the first it removes), then the down link
            k = next((k for k, x in enumerate(lst) if x['types'] and x['types'][0] == DROP_DOWN), None)
            if k is not None:
                del lst[k]
            lst.append(down)
            zt = m.floor_z(m.wrapped(tt))
            up = link(tt, 1.0, (LADDER, LANDING), a, (foot, (top[0], top[1], zt)))
            lists.setdefault(m.wrapped(bt), []).append(up)

    # ---------------------------------------------------------------- 0x100000 (0x905780's start)
    def stand2x2(self, t):
        m = self.m
        x, y, z = t
        if m.flag(t) & 0xC:
            return False
        for (dx, dy), mask in (((1, 0), 0x12), ((0, 1), 0x14), ((1, 1), 0x0A)):
            f = m.raw_flag((x + dx, y + dy, z))     # read with no grid check: wraps at the grid's +X and +Y edges
            if not f & FLOOR or f & mask:
                return False
        return True
