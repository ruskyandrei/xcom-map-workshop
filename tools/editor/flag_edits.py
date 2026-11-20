"""Pieces' flags edited in a project (the piece flags plan, P4: walking, cover, sight, floor and mouse), for the
compiler.

A record's `flags` checked (flags_valid) and planned against the piece's settings as the export has them (flag_plan,
with tools/viewer/piece_flags.py): a map's own piece whose flags change where it stands goes into `edits`, the spec's
`pieceFlags` object, which compiler.native_split hands to the Build's writer (tools/bake/native_copy.py set_roles)
(stationary_flags); a copy's flags go with the copy (copy_flags). `floor_off` and `floor_on` hold the map's own pieces
whose floor such an edit takes away or gives (the compiler's floor, ladder and landing checks count with them), and
`counts` the report's counts.

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A FlagEdits works for one
Compiler: it reads the scene and the meshes from it, asks it for a piece's boxes (boxes), and says what it finds
through its error, warn and note, so the report and the pieces left out are the compiler's as before.

Its own tables (FLAGS_EXPORT, FLAGS_WALL) are here; nothing reads them through the compiler. What the family shares
with the compiler (short, tidy, tile_corner) it takes from compiler_tables, so it never imports the compiler.
"""
import math

# (compiler_tables puts tools/viewer on the path, for piece_flags)
from compiler_tables import short, tidy, tile_corner
import piece_flags

# Pieces' flags (piece flags plan, P4): read from the export's pieceFlags (export 27; a piece of another map from its
# library record), checked with piece_flags.plan, and built by the Build's writer from the package itself (native_copy
# set_roles). A piece this wide or tall (units) with walking, cover or sight turned off is noted (flags-wall).
FLAGS_EXPORT = 27
FLAGS_WALL = 192.0


class FlagEdits:
    def __init__(self, compiler):
        self.c = compiler
        # pieces' flags (piece flags plan): the map's own pieces whose flags change where they stand (the spec's
        # `pieceFlags` object), the actors whose floor such an edit takes away or gives, and the report's counts
        self.edits = []
        self.floor_off, self.floor_on = set(), {}
        self.counts = dict(requested=0, applied=0, leftOut=0, roles={r: 0 for r in piece_flags.ROLES}, companions=0)

    def flags_valid(self, rec, where):
        """Whether a record's `flags` (if any) is well formed: an object of known roles, each strictly true or false,
        never empty. A malformed one leaves the record out, as any malformed field does."""
        if 'flags' not in rec:
            return True
        f = rec['flags']
        if isinstance(f, dict) and f and all(k in piece_flags.ROLES for k in f) and all(isinstance(v, bool) for v in f.values()):
            return True
        self.c.error('malformed', 'flags must name walking, cover, sight, floor or mouse, each true or false (it has %r)'
                   % (f,), **where)
        return False

    def flag_plan(self, src, flags, name, where, box=None, made=None):
        """(the request applied, piece_flags.plan) of a piece's flags against its settings as the export has them, or
        (None, None) with a warning when they can't be checked (the piece is built without them). Roles the class
        doesn't have are noted and dropped; a request a prop's gate makes ambiguous (a hand-edited file: the page
        asks) is a warning and nothing of it is built. box: the piece's world box where it ends up (a copy's), else
        the one where it stands. made: the generated kind of a wall, floor or ground made from numbers, whose flags
        are planned on what the Build makes of its donor (piece_flags.made: simple collision of its own; a ground
        shape's class and settings as native_copy.ground_collision leaves them)."""
        self.counts['requested'] += 1
        record = src.get('pieceFlags')
        cls = src.get('actorClass')
        if not record:
            why = ('the flags are not a setting of %s %s' % ('an' if str(cls)[:1] in 'AEIOUX' else 'a', cls)
                   if piece_flags.family_of(cls) is None else
                   'its export predates pieces\' flags (export %d): open the map in the editor to prepare it again, then '
                   'build' % FLAGS_EXPORT)
            self.c.warn('flags-unavailable', '%s\'s flags are not built: %s' % (name, why), **where)
            self.counts['leftOut'] += 1
            return None, None
        if made:
            cls, record = piece_flags.made(cls, record, made)
        raw, assumed = piece_flags.raw_of(record)
        plan = piece_flags.plan(cls, raw, flags, assumed)
        for role, why in sorted(plan['unsupported'].items()):
            self.c.note('flags-unsupported', '%s: %s is not built (%s)' % (name, piece_flags.LABELS.get(role, role), why),
                      role=role, **where)
        if plan['conflicts']:
            self.c.warn('flags-conflict', '%s\'s flags are not built: %s' % (name, '; '.join(plan['conflicts'].values())),
                      **where)
            self.counts['leftOut'] += 1
            return None, None
        for role, why in sorted(plan['unmet'].items()):
            self.c.note('flags-limited', '%s: %s' % (name, why), role=role, **where)
        applied = {k: v for k, v in flags.items() if k not in plan['unsupported']}
        if not applied:
            self.counts['leftOut'] += 1
            return None, None
        changed = [r for r in piece_flags.ROLES if plan['after'][r] != plan['before'][r]]
        if record.get('collides') is False and changed:
            self.c.note('flags-no-collision', '%s collides with nothing, so no trace of the game meets it: its %s take effect '
                      'only if it gets collision (the Build\'s floor for low scenery on a grown map gives some)'
                      % (name, ' and '.join(piece_flags.LABELS[r] for r in changed)), **where)
        elif record.get('bodySetup') is False and any(r in changed for r in ('walking', 'cover', 'sight')):
            self.c.note('flags-limited', '%s\'s mesh has no simple collision (BodySetup): the pathing, cover and sight sweeps '
                      'pass through it whatever its flags say' % name, **where)
        opened = [r for r in ('walking', 'sight') if plan['after'][r] == 'off' and plan['before'][r] != 'off']
        if cls == 'XComInteractiveLevelActor' and opened:
            self.c.note('flags-door', '%s is a door with %s off: units %s through it when it is shut too'
                      % (name, ' and '.join(piece_flags.LABELS[r] for r in opened),
                         ' and '.join(dict(walking='walk', sight='see')[r] for r in opened)), **where)
        if box is None:
            box = self.c.boxes([src], src['location'], src['rotation']) if src.get('mesh') in self.c.meshes else None
        if flags.get('walking') is True and plan['after']['walking'] in ('on', 'partial') and record.get('collides') is not False \
                and piece_flags.low_piece(box, (tile_corner(self.c.scene.get('tileGrid')) or [None] * 3)[2]):
            corner = tile_corner(self.c.scene.get('tileGrid'))[2]
            reach = box[5] - (corner + piece_flags.LEVEL * math.floor((box[4] + 8 - corner) / piece_flags.LEVEL))
            self.c.warn('flags-low', '%s is too low for Blocks walking to stop anyone: it reaches %d over the bottom of its '
                      'level, under the %d the game\'s tiles need, so its tiles are only partly occupied and units still '
                      'walk into them' % (name, round(reach), piece_flags.STOPS_FROM), **where)
        if box and any(plan['after'][r] == 'off' and plan['before'][r] != 'off' for r in ('walking', 'cover', 'sight')) \
                and (cls in ('XComFracLevelActor', 'XComDecoFracLevelActor') or max(box[1] - box[0], box[3] - box[2], box[5] - box[4]) > FLAGS_WALL):
            self.c.note('flags-wall', '%s is a large piece (or a fracturing wall) that no longer blocks %s: units may walk or see '
                      'through what looks solid' % (name, ' or '.join(piece_flags.LABELS[r].split()[-1] for r in ('walking', 'cover', 'sight')
                                                                     if plan['after'][r] == 'off' and plan['before'][r] != 'off')), **where)
        self.counts['applied'] += 1
        self.counts['companions'] += len(plan['companions'])
        for r in changed:
            self.counts['roles'][r] += 1
        return applied, plan

    def stationary_flags(self, target, parts, flags, where):
        """An original's flags changed where it stands (no move): the spec's `pieceFlags` entry, written in the map by
        the Build (native_copy set_roles), with its box for the tiles it rebuilds."""
        src, name = parts[0], short(target['actor'])
        applied, plan = self.flag_plan(src, flags, name, where)
        if applied is None:
            return
        box = self.c.boxes(parts, src['location'], src['rotation'])
        if plan['after']['floor'] == 'off' and plan['before']['floor'] == 'on':
            self.floor_off.add(target['actor'])
            owned = sum(1 for f in ((self.c.scene.get('tactical') or {}).get('floorTiles') or []) if f.get('actor') == target['actor'])
            if owned:
                self.c.warn('flags-floor', '%s is no floor now: the %d tiles it is the floor of lose it unless another piece '
                          'gives floor there; the landing, mission and ladder checks count without it' % (name, owned),
                          tiles=owned, **where)
        elif plan['after']['floor'] == 'on' and plan['before']['floor'] != 'on':
            self.floor_on[target['actor']] = (name, box)
        self.edits.append(dict(name=name, target=target['actor'], flags=applied, box=[tidy(v, 3) for v in box],
                                    tiles=plan['tiles'], actorClass=src['actorClass']))
        self.c.entities.append(dict(kind='flags', target=target['actor'], actorClass=src['actorClass'], flags=applied,
                                  before=plan['before'], after=plan['after'], writes=[list(w) for w in plan['writes']],
                                  companions=plan['companions'], tiles=plan['tiles']))

    def copy_flags(self, copy, src, flags, name, where):
        """A copy's flags (a moved original's, an added piece's): its request goes with the copy, which the Build
        writes once it is made."""
        kind = (copy.get('generated') or {}).get('kind')
        applied, plan = self.flag_plan(src, flags, name, where, copy.get('box'), made=kind)
        if applied is None:
            return
        copy['flags'] = applied
        collides = kind == 'ground' or src.get('pieceFlags', {}).get('collides') is not False
        copy['floorAfter'] = plan['after']['floor'] if collides else None
        copy['flagPlan'] = dict(before=plan['before'], after=plan['after'], companions=plan['companions'],
                                writes=[list(w) for w in plan['writes']])
