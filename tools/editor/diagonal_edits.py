"""Diagonal cover placed by hand in a project (private/plans/done/diagonal-cover-by-hand-and-views-plan.md, stage M2;
KNOWN-BUGS.md KB-20), for the compiler.

The project's `diagonalCover` (schema 7): {"marks": [{"at": [x, y, z], "toward": [[sx, sy], ...], "low"?: [[sx, sy], ...],
"from"?: [x, y, z]}], "removed": [[x, y, z], ...]}. Each place is a point in a tile, its middle, in the world: the game's tile corner
(tileGrid.tiles) counts the tiles, so a grid grown by whole tiles leaves a place on its tile.
- A mark gives its tile diagonal cover toward its corners ((sx, sy), each +1 or -1, game axes: the diagonal table's
  N (-1, 1), S (1, -1), E (-1, -1) and W (1, 1); research/native/cover-build.md, section 4), in place of whatever the
  map has there. `low` names the corners that are half cover (the panel's Cover: Half), the others full: the game
  keeps a low bit for each corner. `from` names the map's marked tile it was (a map's mark moved or turned), which
  loses its own.
- `removed` names the map's marked tiles (the export's tactical.diagonalCover) the project takes diagonal cover from.
Other fields of a mark are the page's (what it follows, how it came) and are not read here.

The Build gives a mark's tile what the game's build gives a seeded tile, along the marked corners only, each corner
as high or low as the mark says, and a marked corner with no wall cover as marked (tools/bake/diagonal_keep.py
mark_cover): what a corner's wall gives besides (the step-outs, the cover location) is known at the Build, not here.

A DiagonalEdits works for one Compiler, as the other families do: it reads the document and the scene from it and
says what it finds through its leave_out, warn and note. `lane` is the spec's `diagonalCover` (compiler.native_split
hands it to the Build: tools/bake/native_copy.py diagonal_edit): {marks [{at, toward, low?}], removed [at]}, or None.
"""
import json
import math

from compiler_tables import TILE, tile_corner

LEVEL = 64.0
CORNERS = ((-1, 1), (1, -1), (-1, -1), (1, 1))
# a mark this close to an added piece's box (a quarter tile, as the Build counts a change's tiles) may stand on a floor
# the piece gives
MARGIN = 24.0


def _place(value):
    """A place [x, y, z] of finite numbers, or None."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        out = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    return out if all(math.isfinite(v) for v in out) else None


def _corners(value):
    """A mark's corners as a sorted list of distinct (sx, sy), or None when it names none or something else."""
    if not isinstance(value, list) or not value:
        return None
    out = set()
    for d in value:
        if not isinstance(d, (list, tuple)) or len(d) != 2 or tuple(d) not in CORNERS:
            return None
        out.add((int(d[0]), int(d[1])))
    return sorted(out)


def words(corners):
    """A mark's corners in words: 'toward (1, -1) and (-1, 1)'."""
    return 'toward ' + ' and '.join('(%d, %d)' % c for c in corners)


class DiagonalEdits:
    def __init__(self, compiler):
        self.c = compiler
        self.lane = None            # the spec's `diagonalCover`, or None
        self.counts = dict(marks=0, removed=0)

    def tile(self, at):
        """The tile a place is in, counted from the game's tile corner as the export has it."""
        corner = tile_corner(self.c.scene.get('tileGrid') or {})
        size = (TILE, TILE, LEVEL)
        return tuple(int(math.floor((at[k] - corner[k]) / size[k])) for k in range(3))

    def marks(self):
        """The project's `diagonalCover` checked and resolved into the lane: a map's marked tile a mark names as its
        `from`, or `removed` names, or a mark `gone` with its piece, loses its own; marks on one tile join their
        corners. A mark or a place that can't be read is left out (diagonal-mark), the rest builds. A project of
        schema 7 or later has the lane's pageCarries even with no mark (page_carries)."""
        self.lane = None
        rec = self.c.doc.get('diagonalCover')
        if rec is None or rec == {}:
            if self.page_carries():
                self.lane = dict(pageCarries=True)
            return
        where = dict(record='diagonalCover')
        if not isinstance(rec, dict):
            self.c.leave_out('diagonal-mark', 'The project\'s diagonal cover must be {"marks": [...], "removed": [...]}; '
                             'it has %s, which this editor can\'t build: it is left out, and the map keeps its own '
                             'diagonal cover' % json.dumps(rec)[:160], **where)
            return
        grid = self.c.scene.get('tileGrid') or {}
        if not tile_corner(grid):
            self.c.leave_out('diagonal-mark', 'The map\'s export has no tile grid, so the project\'s diagonal cover can\'t '
                             'be placed: it is left out', **where)
            return
        own = {tuple(t['tile']) for t in (self.c.scene.get('tactical') or {}).get('diagonalCover') or []}
        marks, removed = {}, {}
        for i, m in enumerate(rec.get('marks') or []):
            # a map's mark whose piece the project deletes (the page's carried record): its tile loses the mark
            if isinstance(m, dict) and m.get('gone'):
                came = _place(m.get('from'))
                if came is not None and self.tile(came) in own:
                    removed[self.tile(came)] = came
                continue
            at = _place(m.get('at')) if isinstance(m, dict) else None
            corners = _corners(m.get('toward')) if isinstance(m, dict) else None
            low = [] if not isinstance(m, dict) or m.get('low') in (None, []) else _corners(m.get('low'))
            if at is None or corners is None or low is None or not set(low) <= set(corners):
                self.c.leave_out('diagonal-mark', 'A diagonal cover mark must name a place [x, y, z], one to four corners, '
                                 'each [1 or -1, 1 or -1], and as `low` the ones of them that are half cover; mark %d has '
                                 '%s: it is left out' % (i + 1, json.dumps(m)[:160]), record='diagonalCover.marks[%d]' % i)
                continue
            t = self.tile(at)
            if t in marks:
                marks[t]['toward'] = sorted(set(marks[t]['toward']) | set(corners))
                marks[t]['low'] = sorted(set(marks[t]['low']) | set(low))
            else:
                marks[t] = dict(at=at, toward=corners, low=low)
            came = _place(m.get('from')) if m.get('from') is not None else None
            if came is not None and self.tile(came) in own and self.tile(came) != t:
                removed[self.tile(came)] = came
        for i, value in enumerate(rec.get('removed') or []):
            at = _place(value)
            if at is None:
                self.c.leave_out('diagonal-mark', 'A place the project takes diagonal cover from must be [x, y, z]; it has '
                                 '%s: it is left out' % json.dumps(value)[:160], record='diagonalCover.removed[%d]' % i)
                continue
            t = self.tile(at)
            if t in own:
                removed[t] = at
            else:
                self.c.note('diagonal-removed-unmarked', 'The project takes diagonal cover from tile (%d, %d, %d), which the map '
                            'gives none: nothing to take' % t, tile=list(t))
        for t in marks:
            removed.pop(t, None)
        self.no_floor(marks)
        self.reworked(marks)
        carries = self.page_carries()
        if not marks and not removed:
            if carries:
                self.lane = dict(pageCarries=True)
            return
        self.lane = dict(marks=[dict(at=marks[t]['at'], toward=[list(c) for c in marks[t]['toward']],
                                     **({'low': [list(c) for c in marks[t]['low']]} if marks[t]['low'] else {}))
                                for t in sorted(marks)],
                         removed=[removed[t] for t in sorted(removed)], **({'pageCarries': True} if carries else {}))
        self.counts = dict(marks=len(marks), removed=len(removed))
        self.c.note('diagonal-marks', 'The Build gives %d tile%s the diagonal cover the project marks, and takes it from %d of '
                    'the map\'s own: a mark gets what the game gives a marked corner along each of its corners, full or half '
                    'cover as the mark says, and cover as marked toward a corner with no wall there'
                    % (len(marks), '' if len(marks) == 1 else 's', len(removed)))

    def page_carries(self):
        """Whether the page worked out the marks the map's pieces carry (a project of schema 7 or later: its
        `diagonalCover` holds them, `by` the piece each follows), so the Build carries none of its own (pageCarries):
        it writes what the view shows. An older project's Build still carries the map's marks with copies of their
        pieces (native_copy.diagonal_candidates)."""
        return isinstance(self.c.doc.get('schemaVersion'), int) and self.c.doc['schemaVersion'] >= 7

    def rework_areas(self):
        """The areas the variant's streamed levels rework at the battle's start (export 41's streams[].rebuildSpheres,
        42's donors[].rebuildSpheres; KNOWN-BUGS.md KB-22), as tile boxes [(stream, kind, lo, hi, missions, mutator)]:
        each volume's centre ± its sphere's radius on every axis, floored from the game's tile corner as the game counts
        tiles (findings register F-150). The streams of the missions the variant keeps, and an added kind's donor stream
        (the added bomb's Slaughterhouse stream); a cleared map streams none of Long War's patch levels (KB-23). A
        mission object's volume (a bomb's, a power node's, a capture point's) stands where the project's move puts it, as
        the Build moves it in the stream's copy, its offset from the actor turned with it, and goes with its delete;
        `mutator` for a bomb's or node's, which Long War's bomb mutator places with them. The page works the same out
        (diagonal_marks.js reworkAreas)."""
        import missions
        corner = tile_corner(self.c.scene.get('tileGrid') or {})
        if not corner:
            return []
        scene, me = self.c.scene, self.c.mission_edits
        streams = {}
        for index, m in me.kept_missions():
            for name in m.get('streams') or []:
                streams.setdefault(name, [(scene.get('streams') or {}).get(name), []])[1].append(m.get('label') or 'mission %d' % (index + 1))
        for kind in sorted(self.c.added_kinds()):
            donor = (scene.get('donors') or {}).get(kind)
            if isinstance(donor, dict) and donor.get('stream') and donor['stream'] not in streams:
                streams[donor['stream']] = [dict(donor, kind='mission'), ['%s (added)' % missions.label(kind)]]
        size, out = (TILE, TILE, LEVEL), []
        for stream, (s, labels) in sorted(streams.items()):
            if not isinstance(s, dict) or (me.cleared and s.get('kind') == 'lwr'):
                continue
            objects = {o.get('actor'): o for o in s.get('missionObjects') or [] if isinstance(o, dict)}
            hidden = self.c.stream_hides.get(stream) or set()
            for v in s.get('rebuildSpheres') or []:
                o, name = objects.get(v['actor']), str(v['actor']).rsplit('.', 1)[-1]
                if o is not None and name in hidden:
                    continue        # (a mission object the project deletes: out of the stream's copy)
                c, r = list(v['centre']), v['radius']
                move = next((x for x in self.c.stream_moves.get(stream) or [] if x['actor'] == name), None) if o else None
                if move:
                    off = [c[k] - o['location'][k] for k in range(3)]
                    turn = (move['rotation'][1] - (o.get('rotation') or [0, 0, 0])[1]) * math.pi / 32768
                    cos, sin = math.cos(turn), math.sin(turn)
                    to = move['location']
                    c = [to[0] + off[0] * cos - off[1] * sin, to[1] + off[0] * sin + off[1] * cos, to[2] + off[2]]
                lo = tuple(int(math.floor((c[k] - r - corner[k]) / size[k])) for k in range(3))
                hi = tuple(int(math.floor((c[k] + r - corner[k]) / size[k])) for k in range(3))
                group = str((o or {}).get('group') or '')
                out.append((stream, s.get('kind'), lo, hi, list(dict.fromkeys(labels)), group == 'bomb' or group.startswith('node:')))
        return out

    def reworked(self, marks):
        """A warning for the marks on tiles a streamed level reworks at the battle's start: the game works the tile out
        again and never writes diagonal cover back, so the mark gives no cover there (KB-22). One warning a level."""
        by = {}
        for stream, kind, lo, hi, missions, mutator in self.rework_areas():
            for t in marks:
                if all(lo[k] <= t[k] <= hi[k] for k in range(3)):
                    entry = by.setdefault(stream, [kind, missions, set(), False])
                    entry[2].add(t)
                    entry[3] = entry[3] or mutator
        for stream, (kind, missions, tiles, mutator) in sorted(by.items()):
            tiles = sorted(tiles)
            who = ("Long War's %s" % stream if kind == 'lwr'
                   else '%s (streamed by %s)' % (stream, ' and '.join(missions) if missions else 'a mission'))
            self.c.warn('diagonal-mark-reworked', 'Diagonal cover is marked on %s that %s reworks at %s start (tile%s %s): the '
                        'game works %s out again and never writes diagonal cover back, so %s no cover there. Move %s off '
                        "the area the Diagonal cover view draws when %s picked" % (
                            'a tile' if len(tiles) == 1 else '%d tiles' % len(tiles), who,
                            "every battle's" if kind == 'lwr' else "the battle's", '' if len(tiles) == 1 else 's',
                            ', '.join('(%d, %d, %d)' % x for x in tiles), 'it' if len(tiles) == 1 else 'them',
                            'the mark gives' if len(tiles) == 1 else 'the marks give', 'it' if len(tiles) == 1 else 'them',
                            'it is' if len(tiles) == 1 else 'one is')
                        + ('. Under Long War its bomb mutator places the bomb and its power nodes itself, and their areas go '
                           'with them' if mutator else ''),
                        stream=stream, tiles=[list(x) for x in tiles])

    def no_floor(self, marks):
        """A warning for a mark on a tile the map as exported has no floor on and no piece the project adds stands near:
        the game gives a tile with no floor of its own no cover (the Build writes the diagonal flag alone)."""
        floors = {tuple(f['tile']) for f in (self.c.scene.get('tactical') or {}).get('floorTiles') or []}
        if not floors:
            return
        corner = tile_corner(self.c.scene.get('tileGrid') or {})
        boxes = [x['box'] for x in self.c.copies + self.c.covers if x.get('box')]

        def near(t):
            x, y = corner[0] + TILE * (t[0] + 0.5), corner[1] + TILE * (t[1] + 0.5)
            z0, z1 = corner[2] + LEVEL * t[2], corner[2] + LEVEL * (t[2] + 1)
            return any(b[0] - MARGIN <= x <= b[1] + MARGIN and b[2] - MARGIN <= y <= b[3] + MARGIN
                       and b[4] - LEVEL <= z1 and b[5] >= z0 - LEVEL for b in boxes)
        bare = [t for t in sorted(marks) if t not in floors and not near(t)]
        if bare:
            self.c.warn('diagonal-mark-no-floor', 'Diagonal cover is marked on %s with no floor (tile%s %s): the game gives a '
                        'tile with no floor of its own no cover' % (
                            'a tile' if len(bare) == 1 else '%d tiles' % len(bare), '' if len(bare) == 1 else 's',
                            ', '.join('(%d, %d, %d)' % t for t in bare)), tiles=[list(t) for t in bare])
