"""The floor a project leaves and the floors its pieces are checked against, for the compiler: the cursor's floors,
the floor the project's flat pieces give, ladders' climbs, the building floor a copy stands in, the map's low scenery
the Build makes walkable, and the map's floor tiles still there.

The cursor's floors of the map as the project has them (cursor_storeys, with grown_storeys for a grid made larger and
with_made_slabs for the made floors and roofs; web/floors.js cursorStoreys is the twin), which the buildings family
checks a building's floors against. The floor the project's flat pieces are expected to give (added_floors), and the
warning for one with too little standing room over it (floor_headroom). Each moved or copied ladder's climb
(ladder_ends), worked out once every copy, cover block and the stage are known (ladder_climbs, from `ladder_jobs`,
which the compiler's override and add fill), and the map's own ladders near a piece whose flags change where it stands
(flag_ladders, for the spec's `pieceFlags` object). The building floor a copy stands in (floor_at, among the floors as
the project has them: floor_boxes_now) and what is said of it (floor_note). The map's own low scenery the Build makes
walkable on a grid the project grows (scenery_floor, less what the project's flags keep off: floor_kept_off), and the
map's saved floor tiles whose piece is still where it was (floor_now, floor_records_now). The missions', made pieces'
and effects' families read these too.

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A FloorEdits works for one
Compiler: it reads the map, the scene, the meshes, the copies, the cover blocks, the entities, the map's floor tiles
and its building floors' boxes (floors, floor_boxes: index_export) and the other families' state (the larger grid and
the clear, the made floors and roofs, the pieces' flags, the buildings' records) from it, and says what it finds
through its warn and note, so the report is the compiler's as before.

Its own tables (SCENERY_LOW, CURSOR_STOREY, CURSOR_STOREYS, FLOOR_NOTE) are here; nothing reads them through the
compiler. What the family shares with the compiler (TILE, STOREY, FLOOR_THICK, HEADROOM, short, tile_corner,
world_box) it takes from compiler_tables, so it never imports the compiler.
"""
import math

# (compiler_tables puts tools/viewer and tools/bake on the path, for ladders and made_cursors)
from compiler_tables import FLOOR_THICK, HEADROOM, STOREY, TILE, short, tile_corner, world_box
import ladders
import made_cursors

# the map's own low scenery past its far sides, on a grid the project grows, is made walkable by the Build (F-100;
# native_copy.SCENERY_LOW, shell.py scenery_to_walk): a level actor no taller than this, within the grid's levels
SCENERY_LOW = 32.0
# The cursor's floors (the export's cursorVolumes, export 20): a map with none gets CURSOR_STOREYS even storeys of
# CURSOR_STOREY from the Build (shell.py); a building's floor should start within the buildings family's
# CURSOR_NEAR of where one starts.
CURSOR_STOREY, CURSOR_STOREYS = 192.0, 4
# A piece in a building floor's cutaway (its m_aCachedActors): the Build puts its copy in the cutaway of the floor it
# stands in (tools/bake/native_copy.py edit_floor_caches, plan step G7). From export 15 the export holds the floor
# volumes' boxes and the compiler tells whether the copy stands in a floor (floor_note); before, it can't.
FLOOR_NOTE = ("%s is in a building floor's cutaway: its copy joins the cutaway of the floor it stands in, and has none "
              "outside every building")


class FloorEdits:
    def __init__(self, compiler):
        self.c = compiler
        self.ladder_jobs = []    # moved and copied ladders whose climb is still to be checked (ladder_climbs)
        # the building floors' boxes as the project has them (floor_boxes_now), made the first time they are asked for,
        # then kept
        self._floor_boxes_now = None

    def cursor_storeys(self):
        """The cursor's floors of the map: [(floor, [x0, y0, z0, x1, y1, z1])], or None when the export predates them
        (export 20). A map with no cursor volumes, or a cleared one, gets the ones the Build's shell stage gives it:
        even storeys from the tile grid's bottom over the whole map, the last one up to the grid's top. A map as it
        is that keeps its own and is given a larger grid has them as shell.py grow_cursors leaves them: those
        reaching the old far X or Y side stretched to the new one, and with more levels even storeys over the whole
        grid from the top of its own up to the new top, with the floors after its highest. The made floors and roofs
        bring floors of their own over their footprints (with_made_slabs; M5b). Stair volumes are left out.
        web/floors.js cursorStoreys is the twin."""
        if (self.c.scene.get('exporterVersion') or 0) < 20:
            return None
        volumes = self.c.scene.get('cursorVolumes') or []
        own = [(v.get('floor'), list(v['box']['min']) + list(v['box']['max'])) for v in volumes if v.get('box') and not v.get('stair')]
        grid = self.c.scene.get('tileGrid') or {}
        if not grid.get('origin'):
            return self.with_made_slabs(own, None)
        count = list(self.c.mission_edits.stage_grid or grid['dimensions'][:3])
        box = [float(grid['origin'][k]) for k in range(3)] + [grid['origin'][k] + count[k] * grid['size'][k] for k in range(3)]
        if (own or volumes) and not self.c.mission_edits.cleared:
            return self.with_made_slabs(self.grown_storeys(own, grid), box)
        bottom = float(grid['origin'][2])
        levels = (self.c.mission_edits.stage_grid or grid['dimensions'])[2]
        top = bottom + levels * grid['size'][2]
        # (a grid made taller gets a storey more for each 192 units: shell.py clones the last)
        storeys = max(CURSOR_STOREYS, round((top - bottom) / CURSOR_STOREY))
        return self.with_made_slabs(
            [(n + 1, [-1e9, -1e9, bottom + CURSOR_STOREY * n, 1e9, 1e9,
                      max(top, bottom + CURSOR_STOREY * (n + 1)) if n == storeys - 1 else bottom + CURSOR_STOREY * (n + 1)])
             for n in range(storeys)], box)

    def with_made_slabs(self, storeys, grid_box):
        """The cursor's floors `storeys` [(floor, box)] with the made floors' and roofs' own over their footprints, as
        the Build gives them (made_cursors.storeys; M5b)."""
        slabs = self.c.made_edits.made_slab_boxes() if self.c.made_edits.slabs else []
        if not slabs:
            return storeys
        return made_cursors.storeys([dict(key=k, floor=f, box=list(b)) for k, (f, b) in enumerate(storeys)], slabs, grid_box)

    def grown_storeys(self, own, grid):
        """The map's own cursor floors `own` [(floor, box)] on the project's grid (cursor_storeys; shell.py
        grow_cursors is what the Build does)."""
        stage = self.c.mission_edits.stage_grid
        if not stage:
            return own
        o, n, size = grid['origin'], grid['dimensions'], grid['size']
        old = [o[k] + n[k] * size[k] for k in range(3)]
        new = [o[k] + stage[k] * size[k] for k in range(3)]
        out = []
        for floor, b in own:
            b = list(b)
            for k in (0, 1):
                if b[k + 3] >= old[k] - 1.0 and new[k] > b[k + 3]:
                    b[k + 3] = new[k]
            out.append((floor, b))
        if own and new[2] > old[2] + 1e-3:
            top = max(b[5] for _, b in own)
            highest = max(f or 0 for f, _ in own)
            if new[2] > top + 32.0:
                count = max(1, round((new[2] - top) / CURSOR_STOREY))
                for k in range(count):
                    bottom = top + CURSOR_STOREY * k
                    out.append((highest + 1 + k, [o[0], o[1], bottom, new[0], new[1],
                                                  new[2] if k == count - 1 else bottom + CURSOR_STOREY]))
        return out

    def added_floors(self):
        """The floor the copies made so far are expected to give (prefab plan, stage B2): ({tile: the copy's label},
        {tile: (the copy's label, what hangs over it)}). A copy counts when it is flat (no more than FLOOR_THICK
        high): each tile whose centre it covers, at the level of its top, is floor if nothing else the project adds
        hangs less than HEADROOM over it there (F-71: the game gives no floor to a tile without standing room);
        the second answer holds the tiles that fail that. It is a guess from the drawn boxes: the game goes by the
        piece's collision, and whether a piece can be stood on is the piece's own."""
        grid = self.c.scene.get('tileGrid') or {}
        origin, dims = grid.get('origin'), grid.get('dimensions')
        if not origin:
            return {}, {}
        # the levels as the project has them: a grid grown up has floor on its new levels too (once stage() has run)
        levels = max(dims[2], (self.c.mission_edits.stage_grid or [0, 0, 0])[2]) if dims else None
        waiting = {id(job[0]) for job in self.ladder_jobs}
        # (a copy whose flags make it no floor, and that collides, gives none: piece flags plan, 6.1)
        flat = [c for c in self.c.copies if c.get('box') and not c.get('ladder') and c.get('actorClass') != 'XComLadder'
                and id(c) not in waiting and c.get('floorAfter') != 'off']
        # the map's own pieces the project's flags make floor where they stand
        flat += [dict(box=[b[0], b[1], b[2], b[3], b[4], b[5]], label=name) for name, b in self.c.flag_edits.floor_on.values()]
        # an invisible floor is made to carry floor (EXP-32): a plate with its top at its place
        flat += [c for c in self.c.covers if c.get('kind') == 'floor']
        tiles, blocked = {}, {}
        for c in flat:
            b = c['box']
            if b[5] - b[4] > FLOOR_THICK:
                continue
            z = int(math.floor((b[5] + 2.0 - origin[2]) / 64.0))
            if z < 0 or (levels and z >= levels):
                continue
            for x in range(int(math.ceil((b[0] - origin[0]) / 96.0 - 0.5)), int(math.floor((b[1] - origin[0]) / 96.0 - 0.5)) + 1):
                for y in range(int(math.ceil((b[2] - origin[1]) / 96.0 - 0.5)), int(math.floor((b[3] - origin[1]) / 96.0 - 0.5)) + 1):
                    cx, cy = origin[0] + 96.0 * (x + 0.5), origin[1] + 96.0 * (y + 0.5)
                    over = next((o for o in flat if o is not c and o['box'][0] <= cx <= o['box'][1] and o['box'][2] <= cy <= o['box'][3]
                                 and b[5] + 8.0 < o['box'][4] < b[5] + HEADROOM), None)
                    if over:
                        blocked[(x, y, z)] = (c['label'], over['label'])
                    else:
                        tiles[(x, y, z)] = c['label']
        return tiles, blocked

    def floor_headroom(self):
        """The warning for a flat piece the project adds with less than standing room over some of its tiles (F-71)."""
        _, blocked = self.added_floors()
        by_piece = {}
        for tile, (label, over) in sorted(blocked.items()):
            by_piece.setdefault((label, over), []).append(list(tile))
        for (label, over), tiles in sorted(by_piece.items()):
            self.c.warn('floor-headroom', '%s has %s less than %d units over %d of its tiles: the game gives no floor to a tile a '
                      'soldier can\'t stand on, so they won\'t be walked on' % (label, over, HEADROOM, len(tiles)), tiles=tiles[:12])

    def ladder_ends(self, name, src, loc, rot, where):
        """A ladder copy's climb at its pose (ladders.ends against the export's floor tiles whose pieces are still there,
        floor_now, and the floor the project's own flat pieces are expected to give, added_floors): dict(foot, top) tiles, top being the linked top
        tile T′ that the Build rebuilds first, or None with the warning ladder-climb (the ladder is built all the same,
        as a piece with no climb: the check goes by drawn boxes, and warns rather than refuses). An end that counts on
        a floor the project adds is warned of (ladder-new-floor): that floor is made by the game's rebuild, where the
        piece can be stood on. Run by ladder_climbs, once every copy, cover block and the stage are known."""
        grid = self.c.scene.get('tileGrid') or {}
        extent = ladders.extent_z(dict(meshes=self.c.meshes), src)
        if not self.c.floors or not grid.get('origin') or extent is None:
            self.c.warn('ladder-climb', 'the export of %s has no floor data to check %s\'s ends against: it is built with no '
                      'climb of its own' % (self.c.map, name), family='ladder', **where)
            return None
        new, _ = self.added_floors()
        # (the floor of a piece deleted or moved, or that the project's flags make no floor, is gone: floor_now, as the
        # other floor checks count it; a moved piece's copy gives floor where it lands, in `new`)
        floors = self.c.floors & self.floor_now()
        e = ladders.ends(loc, rot, extent, tile_corner(grid), floors | set(new))
        if e['climbs']:
            counted = sorted({new[t] for t in (tuple(e['footTile']), tuple(e['linkedTop'])) if t not in floors})
            if counted:
                self.c.warn('ladder-new-floor', '%s climbs to or from a floor this project adds (%s): it will climb if the game '
                          'makes floor of that piece' % (name, ', '.join(counted)), family='ladder', **where)
        if not e['climbs']:
            missing = ' and '.join({'foot': 'its foot tile %s' % e['footTile'],
                                    'top': 'its top tile %s or the one below it' % e['topTile']}[w] for w in e['why'])
            self.c.warn('ladder-climb', '%s may not climb there: %s %s no floor in the map or under a flat piece of this '
                      'project, and the game makes a ladder\'s climb only between floors' % (name, missing, 'have' if len(e['why']) > 1 else 'has'),
                      family='ladder', ends=dict(foot=e['footTile'], top=e['topTile']), **where)
            return None
        return dict(foot=e['footTile'], top=e['linkedTop'])

    def ladder_climbs(self):
        """Each moved or copied ladder's climb (ladder_ends), worked out once the project's copies, cover blocks and
        stage are all known: a ladder may stand on a floor a later record adds, or on a level the grid grew by. The
        map's own ladders that stay are checked too where a flags edit takes a floor away (flags-floor)."""
        jobs, self.ladder_jobs = self.ladder_jobs, []
        for copy, name, src, loc, rot, where in jobs:
            copy['ladder'] = self.ladder_ends(name, src, loc, rot, where)
        if not self.c.flag_edits.floor_off:
            return
        grid = self.c.scene.get('tileGrid') or {}
        if not grid.get('origin'):
            return
        lost = {tuple(f['tile']) for f in ((self.c.scene.get('tactical') or {}).get('floorTiles') or [])
                if f.get('actor') in self.c.flag_edits.floor_off}
        gone = {e['target'] for e in self.c.entities if e['kind'] in ('delete', 'move')}
        for o in self.c.scene.get('objects') or []:
            if o.get('actorClass') != 'XComLadder' or o.get('actor') in gone or o.get('layer') != 'base':
                continue
            extent = ladders.extent_z(dict(meshes=self.c.meshes), o)
            if extent is None:
                continue
            e = ladders.ends(o['location'], o['rotation'], extent, tile_corner(grid), self.c.floors)
            ends = [t for t in (e.get('footTile'), e.get('linkedTop')) if t is not None]
            if any(tuple(t) in lost for t in ends):
                self.c.warn('flags-floor', '%s climbs to or from a floor that a flags edit takes away: it may no longer climb'
                          % short(o['actor']), actor=o['actor'], ends=dict(foot=e.get('footTile'), top=e.get('linkedTop')))

    def flag_ladders(self):
        """The map's own ladders that stay and climb whose foot or top tile is near a piece whose tile flags change
        where it stands (its box with a quarter tile and a tile round it, from the ground to the level over its top):
        the Build rebuilds their top tile first and their foot after, as a moved ladder's, so the climb keeps both its
        links (native_copy.flags_in_place). [{actor, foot, top}], sorted."""
        edits = [e for e in self.c.flag_edits.edits if e['tiles']]
        grid = self.c.scene.get('tileGrid') or {}
        if not edits or not self.c.floors or not grid.get('origin'):
            return []
        corner = tile_corner(grid)
        near = [(math.floor((b[0] - 24.0 - corner[0]) / 96.0) - 1, math.floor((b[1] + 24.0 - corner[0]) / 96.0) + 1,
                 math.floor((b[2] - 24.0 - corner[1]) / 96.0) - 1, math.floor((b[3] + 24.0 - corner[1]) / 96.0) + 1,
                 math.floor((b[5] - corner[2]) / 64.0) + 1) for b in (e['box'] for e in edits)]
        gone = {e['target'] for e in self.c.entities if e['kind'] in ('delete', 'move')}
        out = []
        for o in self.c.scene.get('objects') or []:
            if o.get('actorClass') != 'XComLadder' or o.get('layer') != 'base' or o.get('actor') in gone:
                continue
            extent = ladders.extent_z(dict(meshes=self.c.meshes), o)
            if extent is None:
                continue
            e = ladders.ends(o['location'], o['rotation'], extent, corner, self.c.floors)
            if not e['climbs']:
                continue
            ends = [tuple(e['footTile']), tuple(e['linkedTop'])]
            if any(x0 <= t[0] <= x1 and y0 <= t[1] <= y1 and t[2] <= z1 for t in ends for x0, x1, y0, y1, z1 in near):
                out.append(dict(actor=short(o['actor']), foot=list(e['footTile']), top=list(e['linkedTop'])))
        return sorted(out, key=lambda l: l['actor'])

    def floor_at(self, box, now=True):
        """(building, floor index) whose floor volumes overlap `box` [x0, x1, y0, y1, z0, z1] most, or None (as the
        Build's native_copy.floor_at finds it): among the floors as the project has them (now), or as exported."""
        best, most = None, 0.0
        for building, index, boxes in (self.floor_boxes_now() if now else self.c.floor_boxes) or []:
            got = 0.0
            for v in boxes:
                inter = 1.0
                for j in range(3):
                    inter *= max(0.0, min(box[2 * j + 1], v['max'][j]) - max(box[2 * j], v['min'][j]))
                got += inter
            if got > most:
                best, most = (building, index), got
        return best

    def floor_boxes_now(self):
        """self.c.floor_boxes with the map's buildings as the project has them (map buildings plan): a changed one's
        boxes from its record, a deleted one's gone; a record the compiler passes over (map_buildings) changes nothing."""
        if self.c.floor_boxes is None or self._floor_boxes_now is not None:
            return self.c.floor_boxes if self.c.floor_boxes is None else self._floor_boxes_now
        records = {}
        for b in self.c.building_edits.building_records()[0]:
            rep = b.get('replaces')
            if isinstance(rep, dict) and str(rep.get('package')).casefold() == self.c.map.casefold() and rep.get('level') == 'base' and isinstance(rep.get('actor'), str):
                records.setdefault(rep['actor'], b)
        usable = self.c.building_edits.map_buildings()
        out, done = [], set()
        for name, index, xs in self.c.floor_boxes:
            rec = records.get(name)
            if rec is None or name not in usable or usable[name][1]:
                out.append((name, index, xs))
                continue
            if name in done:
                continue
            done.add(name)
            if rec.get('deleted'):
                continue
            for k, f in enumerate(rec.get('floors') or []):
                good = [x for x in (f.get('boxes') if isinstance(f, dict) else None) or []
                        if isinstance(x, list) and len(x) == 6 and all(isinstance(v, (int, float)) for v in x)]
                out.append((name, k, [dict(min=list(x[:3]), max=list(x[3:])) for x in good]))
        self._floor_boxes_now = out
        return out

    def floor_note(self, name, src, box, where, old):
        """The building-floor warning for the copy of `src` (a moved piece's, or an added one) standing in `box`, its
        original in `old`: the Build puts the copy of a piece in a floor's cutaway in the cutaway of the floor it stands
        in (plan step G7), or keeps the original's when neither stands in a floor volume (a ladder on an outer wall).
        A van's parts say nothing: their own building goes with them (plan section 7.6)."""
        if (self.c.assemblies.get(src.get('actor')) or {}).get('family') == 'van':
            return
        if self.c.floor_boxes is None:
            if src.get('floors'):
                self.c.note('building-floor', FLOOR_NOTE % name, **where)
            return
        there = self.floor_at(box)
        if src.get('floors') and there is None and self.floor_at(old, now=False) is not None:
            self.c.note('building-floor', "%s is in a building floor's cutaway; its copy stands in no building floor, so no "
                      "cutaway hides it" % name, **where)
        elif not src.get('floors') and there is not None:
            self.c.warn('building-floor', "%s is in no building floor's cutaway (it has no floor component); its copy stands "
                      "in floor %d of %s but won't hide or cut down with it" % (name, there[1] + 1, short(there[0])),
                      **where)

    def scenery_floor(self):
        """The boxes of the map's own low scenery the Build makes walkable on a grid the project grows (F-100;
        shell.py scenery_to_walk): its level actors no taller than SCENERY_LOW, within the grid's levels (from a
        quarter level under its bottom: not the sky's ground plane), reaching past the map's own far X or Y side, and
        not deleted or moved. A raised backdrop counts as the ground does (CsmallScout_Farm's plateau). The map's saved
        floor tiles stop at its own grid, so a soldier point over one of these counts as floor. The Build turns on the
        collision of those that have it off and puts their tiles in the rebuild's queue. (The export doesn't say which
        collide: a piece of debris that collides but is no floor counts here too.)"""
        if not self.c.mission_edits.stage_grid or self.c.mission_edits.cleared:
            return []
        grid = self.c.scene.get('tileGrid') or {}
        origin, dims = grid.get('origin'), grid.get('dimensions')
        if not origin or not dims:
            return []
        x1, y1 = origin[0] + TILE * dims[0], origin[1] + TILE * dims[1]
        levels = self.c.mission_edits.stage_grid[2] if len(self.c.mission_edits.stage_grid) > 2 else dims[2]
        bottom, top = origin[2] - STOREY / 4, origin[2] + STOREY * levels
        gone = {e['target'] for e in self.c.entities if e['kind'] in ('delete', 'move')} | self.floor_kept_off()
        boxes = []
        for o in self.c.scene.get('objects') or []:
            if o.get('actorClass') != 'XComLevelActor' or o.get('actor') in gone or o.get('mesh') not in self.c.meshes:
                continue
            b = world_box(o, self.c.meshes, o['location'], o['rotation'])
            if b[5] - b[4] <= SCENERY_LOW and b[4] >= bottom and b[5] <= top and (b[1] > x1 or b[3] > y1):
                boxes.append(b)
        return boxes

    def floor_kept_off(self):
        """The map's own pieces whose Floor the project's flags turn off or keep off (explicit Floor off): the Build's
        floor for low scenery on a grown map leaves them as they are (F-100 gives way to the user's flags)."""
        return {e['target'] for e in self.c.flag_edits.edits if e['flags'].get('floor') is False}

    def diagonal_cover(self):
        """A warning for the map's diagonal cover tiles (the export's tactical.diagonalCover, the corners of slanted
        walls its makers marked) a change stands on: the copies' boxes, the hidden and moved pieces' old ones, the
        cover blocks' and the pieces whose flags change, counted as the Build does (scene_metadata.changed_tiles). The
        battle's rebuild works such a tile out again and its diagonal cover goes (findings register F-149); a tile
        only next to a change the Build writes itself and keeps."""
        import scene_metadata
        c = self.c
        tiles = (c.scene.get('tactical') or {}).get('diagonalCover') or []
        grid = c.scene.get('tileGrid') or {}
        if not tiles or not grid.get('origin') or not grid.get('dimensions'):
            return
        boxes = [x['box'] for x in c.copies + c.hides + c.covers if x.get('box')]
        boxes += [x['box'] for x in c.flag_edits.edits if x.get('box')]
        size = grid.get('size') or (TILE, TILE, 64.0)
        on = scene_metadata.changed_tiles(boxes, grid['origin'], grid['dimensions'], size)
        taken = [t['tile'] for t in tiles if tuple(t['tile']) in on]
        if taken:
            c.warn('diagonal-cover-taken', 'The project changes what stands on %s of the map\'s slanted corners that '
                   'give diagonal cover (tile%s %s): the game works %s out again and the diagonal cover goes, so a unit '
                   'there gets no cover from the slanted wall. A change a tile away keeps it'
                   % (len(taken) if len(taken) > 1 else 'one', 's' if len(taken) > 1 else '',
                      ', '.join('(%d, %d, %d)' % tuple(t) for t in taken), 'them' if len(taken) > 1 else 'it'),
                   tiles=taken)

    def floor_now(self):
        """The map's saved floor tiles whose piece is still where it was: a deleted or moved piece takes its floor
        with it (a moved one's copy gives floor where it lands: added_floors)."""
        return {tuple(f['tile']) for f in self.floor_records_now()}

    def floor_records_now(self):
        """The export's floor tile records (tactical.floorTiles: tile, location, actor) of floor_now."""
        gone = {e['target'] for e in self.c.entities if e['kind'] in ('delete', 'move')} | self.c.flag_edits.floor_off
        return [f for f in ((self.c.scene.get('tactical') or {}).get('floorTiles') or []) if f.get('actor') not in gone]
