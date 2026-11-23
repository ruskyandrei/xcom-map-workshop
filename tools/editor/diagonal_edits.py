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
