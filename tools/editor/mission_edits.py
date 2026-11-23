"""The project's map grid, its clear, its landing zones, its missions and its spawn rule, and where a mission's points
and the squad's spots stand after the edit, for the compiler.

The map's grid made larger, or smaller on a cleared map (stage, stage_max: `stage_grid`), and what lies outside it
(stage_outside, grid_box); the clear and what it keeps outside the grid (cleared_mark, outside_box: `cleared`,
`keep_outside`); the drop-in rule (spawn_rules_mark, spawn_rules_notes: `spawn_rules`); the landing zones and the map's
own landings (landing_zones, check_zones: `zones`, `own_landings_found`, `own_count`); the missions the variant keeps
or adds (missions_kept, kept_missions, kept_streams, missions_check, mission_list) and their objects (mission_objects);
and the places the game drops units at (projected_spawns, spawn_places). The compiler's run asks for each stage in its
order, and its spec and report read the state they leave: the larger grid, the clear, the landing zones and the spawn
rule go into the spec for the Build (its shell, its clear, its config lines), the rest into the report's warnings and
notes.

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A MissionEdits works for one
Compiler: it reads the map, the scene, the document, the copies, the cover blocks, the entities and the other families'
state from it, asks its floor family for the floor the project leaves (floor_now, added_floors, scenery_floor) and it
for a mission object's place in its stream (moved_object), and says what it finds through its error, leave_out, warn and
note, so the report and what is left out are the compiler's as before.

Its own tables and helpers (STAGE_GRID_MAX, STAGE_LEVELS_MAX, stage_max, POD_DISTANCE, tidy_zone, zone_words,
scripted_users and the others) are here, and the compiler names again those that others read through it
(compiler.STAGE_GRID_MAX, compiler.STAGE_LEVELS_MAX, compiler.stage_max). What the family shares with the compiler
(TILE, STOREY, HEADROOM, FLOOR_THICK, STAGE_MAPS, tidy, tile_corner) it takes from compiler_tables, so it
never imports the compiler.
"""
import json
import math
from pathlib import Path

# (compiler_tables puts tools/viewer and tools/bake on the path, for missions and spawns)
from compiler_tables import FLOOR_THICK, HEADROOM, STAGE_MAPS, STOREY, TILE, tidy, tile_corner
import missions
import spawns

# a project's larger tile grid (stage): most of the game's own maps are under 100 tiles a side, but not all
# (TempleShip is 45 by 203, AlienBase01 63 by 168); the editor makes up to 256 (the user, 16 November 2026; 128
# before), and a map past it keeps its own as its limit (stage_max)
STAGE_GRID_MAX = 256
# levels: the game's own maps go to 18 (1,152 units, the tallest of its 96: prefab plan 5.6b; prefab_bounds.PLAYED_LEVELS,
# the test stage's least height); the editor makes up to 30 (1,920 units; the user, 14 November 2026)
STAGE_LEVELS_MAX = 30


def stage_max(own):
    """The most a project's grid may be on each axis for a map whose own grid is `own` [nx, ny, nz]: STAGE_GRID_MAX
    tiles across and deep and STAGE_LEVELS_MAX levels, or the map's own where that is more, so a map is never past
    the limit at its own size and can still be made larger (project.js stageMax is the twin)."""
    return [max(limit, int(own[k]) if own and len(own) > k else 0)
            for k, limit in enumerate((STAGE_GRID_MAX, STAGE_GRID_MAX, STAGE_LEVELS_MAX))]


# LWR's pod mutator keeps only map sections this many tiles from the squad's middle (F-90): stage-small
POD_DISTANCE = 29


def tidy_zone(z):
    """A landing zone as the spec carries it: the keys it has, the place to four decimals (web/project.js
    tidyLandingZone)."""
    out = dict(id=z['id'], location=[tidy(float(v)) for v in z['location']], direction=z['direction'],
               kind=z.get('kind') or 'normal')
    for k in ('missionType', 'councilType'):
        if z.get(k):
            out[k] = z[k]
    if z.get('alternate'):
        out['alternate'] = dict(location=[tidy(float(v)) for v in z['alternate']['location']],
                                direction=z['alternate']['direction'])
    if z.get('lwr') is False:
        out['lwr'] = False
    if z.get('ew') is True:
        out['ew'] = True
    if z.get('other'):
        out['other'] = z['other']
    return out


def numbers(ns):
    """1, 2 and 5 / 3 to 7: a list of numbers in words."""
    ns = sorted(ns)
    if len(ns) > 2 and ns == list(range(ns[0], ns[-1] + 1)):
        return '%d to %d' % (ns[0], ns[-1])
    return ', '.join(str(n) for n in ns[:-1]) + (' and ' if len(ns) > 1 else '') + str(ns[-1])


def zone_words(ns):
    return 'landing zone%s %s' % ('' if len(ns) == 1 else 's', numbers(ns))


def scripted_users(record):
    """The scripted actions that drop units at a spawn point (export 33's `uses`: a SeqAct_SpawnAlien naming it, or
    an object list holding it that feeds such actions), as web/spawn_rules.js scriptedUsers reads them."""
    out = []
    for u in record.get('uses') or []:
        if not isinstance(u, dict):
            continue
        if u.get('how') == 'direct' and u.get('byClass') == 'SeqAct_SpawnAlien':
            out.append(u.get('by'))
        elif u.get('how') == 'indirect':
            out += list(u.get('then') or [u.get('by')])
    return list(dict.fromkeys(a for a in out if a))


class MissionEdits:
    def __init__(self, compiler):
        self.c = compiler
        # what run()'s stages work out, in its order (review finding 23): cleared_mark the clear; spawn_rules_mark the
        # drop-in rule; stage the larger grid; landing_zones the zones and the map's own landings. Each keeps these
        # values when the stage doesn't run (a document that stops earlier).
        self.cleared, self.keep_outside = False, False
        self.keep_triggers = False  # the clear kept the map's triggers (cleared_mark)
        self.drop_patches = False   # the records stream none of LWR's patch levels (cleared_mark: a cleared map)
        self.spawn_rules = None
        self.map_info = None        # what Long War Rebalance is told of the map (map_info_mark)
        self.stage_grid = None
        self.zones, self.own_landings_found, self.own_count = None, None, None
        # the missions the project keeps (missions_kept), made the first time they are asked for, then kept
        self._missions_kept = None

    def stage(self):
        """The project's `stage` (optional): `grid` [nx, ny] or [nx, ny, nz], the map's tile grid made that many tiles
        from its own corner (prefab plan 5.11; the Build's shell stage resizes it) and, with nz, that many levels from
        its own bottom (5.6b), `ground` (false: lay no ground over the new area), `lines` (true: the ground drawn as a
        grid, its planes hidden and a white line on every tile edge; 5.11) and `hideGround` (true: the planes hidden, no
        lines). A map as it is, the blank map among them, only grows (the user, 13 November 2026: any map, where
        before only the blank map); a cleared project's grid (Clear map plan, section 6) may also be smaller in any of
        the three, from 1 tile or level. Each is at most STAGE_GRID_MAX tiles or STAGE_LEVELS_MAX levels, or the map's
        own where that is more (stage_max). A size this compiler can't build is left out (record `stage`: the map
        keeps its size, and the Build reads nothing of `stage`); an export with no tile grid is an error.
        Sets self.stage_grid to [nx, ny, nz] when the grid differs from the map's, else None."""
        self.stage_grid = None
        stage = self.c.doc.get('stage')
        if stage is None:
            return
        grid = stage.get('grid') if isinstance(stage, dict) else None
        if not (isinstance(grid, list) and len(grid) in (2, 3) and all(isinstance(v, int) and not isinstance(v, bool) for v in grid)) \
                or any(stage.get(k) not in (None, True, False) for k in ('ground', 'lines', 'hideGround')):
            self.c.leave_out('stage-shape', 'the project\'s map size must be {"grid": [tiles across, tiles deep]} or '
                                          '{"grid": [tiles across, tiles deep, levels]}, with an optional "ground", '
                                          '"lines" and "hideGround", each true or false: it is left out, and the map '
                                          'keeps its own size', record='stage')
            return
        bare = self.c.map in STAGE_MAPS
        grows_only = not self.cleared
        own = (self.c.scene.get('tileGrid') or {}).get('dimensions')
        if not own:
            self.c.error('stage-grid', 'the export of %s has no tile grid to resize' % self.c.map)
            return
        if not bare and any(stage.get(k) is not None for k in ('lines', 'hideGround')):
            self.c.note('stage-ground', '"lines" and "hideGround" are the blank map\'s; on %s they do nothing' % self.c.map)
        if self.cleared and stage.get('ground') is not None:
            self.c.note('stage-ground', '"ground" does nothing on a cleared map: it lays no ground')
        grid = list(grid[:2]) + [grid[2] if len(grid) == 3 else own[2]]
        if grows_only and (grid[0] < own[0] or grid[1] < own[1]):
            self.c.leave_out('stage-grid', '%s can be made larger, not smaller, until it is cleared: %d by %d tiles against '
                           'its own %d by %d; the size is left out, and the map keeps its own'
                           % ('the blank map' if bare else self.c.map, grid[0], grid[1], own[0], own[1]),
                           grid=grid, own=own[:2], record='stage')
            return
        most = stage_max(own)
        if not (1 <= grid[0] <= most[0] and 1 <= grid[1] <= most[1]):
            self.c.leave_out('stage-grid', 'the map can be from 1 to %d tiles across and 1 to %d deep (asked: %d by %d); '
                           'the size is left out, and the map keeps its own'
                           % (most[0], most[1], grid[0], grid[1]), grid=grid, own=own[:3], record='stage')
            return
        lowest = own[2] if grows_only else 1
        if not lowest <= grid[2] <= most[2]:
            self.c.leave_out('stage-grid', 'the map can be from %d up to %d levels high (asked: %d); the size is left out, '
                           'and the map keeps its own' % (lowest, most[2], grid[2]), grid=grid, own=own[:3], record='stage')
            return
        if grid != list(own[:3]):
            self.stage_grid = grid
            if grows_only and not bare:
                words = []
                if grid[:2] != list(own[:2]):
                    words.append('the Build lays more of the map\'s ground over the new area only where it is laid as '
                                 'planes, and makes the map\'s own low scenery there (ground, pavements) walkable; '
                                 'elsewhere lay floors')
                if grid[2] > own[2]:
                    words.append('the cursor reaches the new levels by storeys the Build adds over the whole grid, above '
                                 'the map\'s own cursor volumes')
                self.c.note('stage-grown-map', '%s made larger as it is: %s' % (self.c.map, '; '.join(words)),
                          grid=grid, own=own[:3])

    def spawn_rules_mark(self):
        """The project's `spawnRules` (schema 4; spawns plan, SP8): left out or null, scripted drop-ins play as the
        install plays them; {"dropIns": "placed"}, Long War's scripted drop-ins land where placed: the Build adds the
        variant to its drop-in mutator's ExcludeMaps list (DefaultRandomSpawns.ini). Anything else (a newer editor's
        rule this one can't build) is left out (spawn-rules): the drop-ins play as the install plays them."""
        self.spawn_rules = None
        rules = self.c.doc.get('spawnRules')
        if rules is None:
            return
        if rules != {'dropIns': 'placed'}:
            self.c.leave_out('spawn-rules', 'the project\'s spawn rules must be {"dropIns": "placed"} or left out; it has '
                           '%s, which this editor can\'t build: the rule is left out, and scripted drop-ins play as the '
                           'install plays them' % json.dumps(rules)[:160], record='spawnRules')
            return
        self.spawn_rules = dict(dropIns='placed')

    def map_info_mark(self):
        """The project's `lwrMapInfo` (schema 6; Map settings' Long War Rebalance section): what LWR 3.00.00 beta 17
        and later is told of the map, {"alienDensity"?: Light, Moderate, Heavy or Swarming (the largest abduction the
        map suits), "holdTheLine"?: No or Yes} (missions.MAP_INFO). The Build writes a MapInfo line for each into the
        manifest's config.mapInfo, and a map pack's card carries them; the map itself is not changed. Left out, null
        or empty: no line, so LWR takes the map as any other. Anything else (a newer editor's key or value) is left
        out whole (lwr-map-info)."""
        self.map_info = None
        info = self.c.doc.get('lwrMapInfo')
        if info is None or info == {}:
            return
        if not missions.valid_map_info(info):
            self.c.leave_out('lwr-map-info', 'the project\'s Long War Rebalance map info must be {%s}, each left out or one '
                             'of its values; it has %s, which this editor can\'t build: it is left out, and LWR takes the '
                             'map as any other' % (', '.join('"%s": %s' % (k, ' | '.join(values)) for k, (_, values) in missions.MAP_INFO.items()),
                                                    json.dumps(info)[:160]), record='lwrMapInfo')
            return
        self.map_info = {k: info[k] for k in missions.MAP_INFO if k in info}
        self.c.note('lwr-map-info-set', '%s reads the map\'s info from its map pack (%s): a pack exported from Manage projects '
                    'carries it on its card' % (missions.MAP_INFO_SINCE, missions.map_info_words(self.map_info)))

    def spawn_rules_notes(self):
        """Notes on the spawn rule (spawns plan, SP8): dropins-placed says what it covers, the scripted actions that
        drop aliens in at points of the map and of the streams of the missions the variant keeps (export 33's `uses`),
        and that wave systems are never moved by Long War; dropins-base-excluded, with no rule, that the install's
        ExcludeMaps names the base map (the Chryssalid Hive) but not the variant, which has a name of its own."""
        variant = self.c.out['shipAs']
        if self.spawn_rules:
            actions = set()
            for r in self.c.scene.get('spawns') or []:
                if isinstance(r, dict) and r.get('kind') == 'dropIn':
                    actions.update(('the map', a) for a in scripted_users(r))
            for _, _, stream, objects in self.kept_streams():
                for o in objects:
                    if o.get('kind') == 'dropIn':
                        actions.update((stream, a) for a in scripted_users(o))
            labels = [m.get('label') or 'mission %d' % (i + 1) for i, m in self.kept_missions()]
            labels += ['%s (added)' % missions.label(k) for k in sorted(self.c.added_kinds())]
            places = sorted({where for where, _ in actions})
            covers = ('%d scripted %s in %s' % (len(actions), 'action' if len(actions) == 1 else 'actions', ', '.join(places))
                      if actions else 'every scripted drop-in (the export finds no scripted action dropping aliens in)')
            self.c.note('dropins-placed', 'Scripted drop-ins land where placed: the Build adds %s to Long War\'s ExcludeMaps list '
                      '(DefaultRandomSpawns.ini), for %s of %s (%s), and Long War\'s drop-in mutator gives them neither its '
                      'overwatch nor its reveal; wave systems\' drop-ins are never moved by Long War. Plain Enemy Within '
                      'plays them where placed already, and the Build writes nothing there'
                      % (variant, covers, 'the one mission' if len(labels) == 1 else 'every mission', ', '.join(labels)),
                      actions=len(actions), missions=labels)
            return
        game = getattr(self.c.library, 'game', None)
        if not isinstance(game, (str, Path)) or not game:
            return
        import spawnrules
        try:
            found = spawnrules.rules(game)
        except (OSError, ValueError):
            return
        if found.get('dropIns') == 'active' and spawnrules.excluded(found, self.c.map) and not spawnrules.excluded(found, variant):
            self.c.note('dropins-base-excluded', 'Long War\'s ExcludeMaps names %s, so its drop-in mutator leaves the map\'s '
                      'scripted drop-ins where placed; %s has a name of its own, and Long War moves them near the squad '
                      'there unless the project leaves them where placed (the Spawns view\'s flyout)' % (self.c.map, variant))

    def cleared_mark(self):
        """The project's `cleared` (Clear map plan, section 6): true says the Build takes out what the editor never
        showed and puts one rebuild volume over the whole grid. The pieces themselves go by their delete records."""
        cleared = self.c.doc.get('cleared', False)
        if not isinstance(cleared, bool):
            self.c.leave_out('cleared-shape', '"cleared" must be true or false: it is left out, and the map is built as '
                           'not cleared (its pieces go by their own delete records)', record='cleared')
            cleared = False
        self.cleared = cleared is True
        # `clearKeepsOutside` (the Clear map window's "Keep the scenery outside the play area"): the clear left the
        # pieces wholly outside the play area, and the Build's clear_level leaves the lights, emitters, decals and
        # lens flares placed outside it (outside_box). Without `cleared` it says nothing.
        keeps = self.c.doc.get('clearKeepsOutside', False)
        if not isinstance(keeps, bool):
            self.c.leave_out('cleared-shape', '"clearKeepsOutside" must be true or false: it is left out%s'
                           % (', and the clear takes out what lies outside the play area too' if cleared is True else ''),
                           record='clearKeepsOutside')
            keeps = False
        self.keep_outside = self.cleared and keeps is True
        # `clearKeepsTriggers` (the Clear map window's "Keep the map's triggers and scripts"): the Build's clear_level
        # leaves the map's trigger volumes and sight points, which it takes out otherwise (F-159). Without `cleared` it
        # says nothing.
        keeps = self.c.doc.get('clearKeepsTriggers', False)
        if not isinstance(keeps, bool):
            self.c.leave_out('cleared-shape', '"clearKeepsTriggers" must be true or false: it is left out%s'
                           % (', and the clear takes out the map\'s triggers' if cleared is True else ''),
                           record='clearKeepsTriggers')
            keeps = False
        self.keep_triggers = self.cleared and keeps is True
        if self.cleared and not (self.c.scene.get('tileGrid') or {}).get('dimensions'):
            self.c.error('cleared-grid', 'the export of %s has no tile grid, which a cleared map\'s Build covers with its '
                       'cursor and rebuild volumes' % self.c.map)
        # LWR's patch levels for the map (patch_*): a cleared map's records stream none of them (the Build's
        # config_lines, `dropPatches`), their pieces, lights, rebuild volumes and load scripts all made for the map that
        # is gone (KNOWN-BUGS.md KB-23, F-163); the no-spawn volumes and meld points some carry go with them. The
        # mission's own streamed levels are left. (Before, a cleared map streamed copies with the pieces out.)
        self.drop_patches = self.cleared

    def outside_box(self):
        """What a clear that keeps the scenery outside the play area counts as the play area, across: [x0, y0, x1, y1],
        the map's level volume (playableBounds, in the viewer's basis [x, up, y]) and the grid as the project has it
        together. A piece or an actor wholly outside it stays."""
        b, g = self.c.scene.get('playableBounds') or {}, self.grid_box()
        boxes = ([[b['min'][0], b['min'][2], b['max'][0], b['max'][2]]] if b.get('min') and b.get('max') else []) \
            + ([[g[0], g[1], g[3], g[4]]] if g else [])
        if not boxes:
            return None
        return [float(min(v[0] for v in boxes)), float(min(v[1] for v in boxes)),
                float(max(v[2] for v in boxes)), float(max(v[3] for v in boxes))]

    def grid_box(self):
        """The tile grid as the project has it: [x0, y0, z0, x1, y1, z1], or None without one."""
        grid = self.c.scene.get('tileGrid') or {}
        if not grid.get('origin') or not grid.get('dimensions'):
            return None
        o, size = grid['origin'], grid.get('size') or [TILE, TILE, STOREY]
        dims = self.stage_grid or grid['dimensions']
        return [float(o[0]), float(o[1]), float(o[2]), float(o[0]) + dims[0] * size[0], float(o[1]) + dims[1] * size[1],
                float(o[2]) + dims[2] * size[2]]

    def stage_outside(self):
        """The warning for the project's pieces and cover blocks wholly outside a grid the project sized
        (stage-outside): counted, the first few named. A piece is outside when the middle of its box's floor is
        outside the grid's sides, or its box reaches no level of the grid (a piece sunk into the ground, or reaching
        over its top, still stands in it). Lights and building floors are left out: a light lights anything, and a
        floor box beyond the grid only covers a place with no tiles (the user, 14 November 2026: warnings only for
        what can cause a problem in the game)."""
        if not self.stage_grid:
            return
        g = self.grid_box()

        def outside(b):
            x, y = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
            return not (g[0] <= x <= g[3] and g[1] <= y <= g[4]) or b[5] < g[2] or b[4] > g[5]
        out = []
        for c in self.c.copies:
            if outside(c['box']):
                out.append(c['label'].split(':', 1)[-1])
        for c in self.c.covers:
            if c.get('box') and outside(c['box']):
                out.append(c['name'])
        if out:
            self.c.warn('stage-outside', '%d of the project\'s pieces stand outside the %d by %d by %d '
                      'grid: there are no tiles there to stand on or take cover by (%s%s)'
                      % (len(out), self.stage_grid[0], self.stage_grid[1], self.stage_grid[2], ', '.join(out[:5]),
                         ', ...' if len(out) > 5 else ''), count=len(out), names=out[:12])

    # ---------------------------------------------------------------- landing zones (Clear map plan, section 4)
    def landing_zones(self):
        """The project's landing zones (`landingZones`, optional): checked for shape, then warned of: a soldier point
        over no floor (landing-floor), a piece the project puts on one (landing-blocked), a zone outside the grid
        (landing-outside), more zones than the map has landings of its own (landing-lwr-only), a zone that plays
        nowhere (landing-unused), none (landing-none). A zone this compiler can't read, or whose id an earlier one has,
        is left out (landing-shape) and the rest are the variant's; a list that is no list, or whose zones are all left
        out, is as no list: the base map's lines are copied. Without the list, the map's own landings are checked the
        same way on a cleared or resized project. Sets self.zones (the list, tidied, or None) and self.own_count."""
        self.zones = None
        own = spawns.own_landings(self.c.scene)
        self.own_landings_found = own
        self.own_count = len(own)
        raw = self.c.doc.get('landingZones')
        if raw is not None and not isinstance(raw, list):
            self.c.leave_out('landing-shape', '"landingZones" must be a list of landing zones: it is left out, and the '
                           'variant lands as %s does' % self.c.map, record='landingZones')
            raw = None
        kept, ids = [], set()
        for k, z in enumerate(raw or []):
            where = dict(record='landingZones[%d]' % k)
            if not spawns.valid_zone(z):
                self.c.leave_out('landing-shape', 'landing zone %d is not {id, location: [x, y, z], direction, kind, ...}: '
                               'it is left out' % (k + 1), **where)
            elif z['id'] in ids:
                self.c.leave_out('landing-shape', 'landing zone %d has the id of an earlier one (%s): it is left out'
                               % (k + 1, z['id']), **where)
            else:
                ids.add(z['id'])
                kept.append(z)
        if raw and not kept:
            # every zone left out: the variant lands as the map does, not at none
            self.c.note('landing-own', 'every landing zone of the project is left out: the variant lands as %s does' % self.c.map)
            raw = None
        if raw is None:
            if self.cleared or self.stage_grid:
                self.check_zones([dict(o['zone'], id='own%d' % (k + 1)) for k, o in enumerate(own)], own=True)
            return
        self.zones = [tidy_zone(z) for z in kept]
        if not self.zones:
            self.c.warn('landing-none', 'the project has no landing zone: LWR gets no line for the map, and a plain '
                      'install plays the map\'s own landing where it stands')
            return
        slots = spawns.own_slots(self.zones, self.own_count)
        lwr_only = [k + 1 for k in range(len(self.zones)) if k not in slots and self.zones[k].get('lwr', True) is not False]
        nowhere = [k + 1 for k in range(len(self.zones)) if k not in slots and self.zones[k].get('lwr', True) is False]
        if lwr_only:
            self.c.warn('landing-lwr-only', '%s %s under Long War only: a plain install plays the map\'s %d landing%s of '
                      'its own, at the zones marked Plain EW' % (zone_words(lwr_only), 'plays' if len(lwr_only) == 1 else 'play',
                                                                self.own_count, '' if self.own_count == 1 else 's'),
                      zones=lwr_only)
        marked = [k + 1 for k, z in enumerate(self.zones) if z.get('ew') is True]
        if spawns.explicit(self.zones) and len(marked) > self.own_count:
            self.c.warn('landing-ew-extra', '%d zones are marked Plain EW, and the map has %d landing%s of its own: %s '
                      'play%s under Long War only' % (len(marked), self.own_count, '' if self.own_count == 1 else 's',
                                                      zone_words(marked[self.own_count:]),
                                                      's' if len(marked) - self.own_count == 1 else ''),
                      zones=marked[self.own_count:])
        if len(slots) < self.own_count:
            self.c.warn('landing-ew-fewer', 'a plain install also lands at %d of the map\'s own landing%s where the map has '
                      '%s: only %d zone%s %s marked Plain EW' % (
                          self.own_count - len(slots), '' if self.own_count - len(slots) == 1 else 's',
                          'it' if self.own_count - len(slots) == 1 else 'them', len(slots), '' if len(slots) == 1 else 's',
                          'is' if len(slots) == 1 else 'are'),
                      missing=self.own_count - len(slots))
        if nowhere:
            self.c.warn('landing-unused', '%s %s no line for Long War and %s none of the map\'s own landings, so %s '
                      'never played' % (zone_words(nowhere), 'has' if len(nowhere) == 1 else 'have',
                                        'is' if len(nowhere) == 1 else 'are', 'it is' if len(nowhere) == 1 else 'they are'),
                      zones=nowhere)
        self.check_zones(self.zones)

    def missions_kept(self):
        """The project's `missions` as the Build writes them (mission types plan, D1): (its entries the Build can
        write, in order, or None for every record of the base map; [(where, why) of each part left out]). An entry the
        Build can't write is left out, and so is the whole value when it is no list or empty, or when none of its
        entries can be written: the variant then serves every record of the base map, as with no list. build.py
        writes the records of this list (the report's `missions`)."""
        if self._missions_kept is None:
            listed, dropped = self.c.doc.get('missions'), []
            records = len([m for m in self.c.scene.get('missions') or [] if isinstance(m, dict)])
            if listed is not None and (not isinstance(listed, list) or not listed):
                dropped.append((dict(record='missions'), 'the project\'s missions must be a list of at least one'))
                listed = None
            kept = [e for e in listed if missions.valid_entry(e, records)] if listed is not None else None
            for k, e in enumerate(listed or []):
                if not missions.valid_entry(e, records):
                    dropped.append((dict(record='missions[%d]' % k), 'mission %d of the project\'s list is neither one of the '
                                    'base map\'s %d records nor a kind a record alone gives a map (%s)'
                                    % (k + 1, records, ', '.join(missions.ADDED_KINDS))))
            self._missions_kept = (kept or None, dropped)
        return self._missions_kept

    def kept_missions(self):
        """The base map's missions the variant keeps (mission types plan, D1): [(index, the export's mission)]: the
        entries of the project's `missions` (missions_kept) that name a record ({record: i}), else every mission of
        the export."""
        found = [m for m in self.c.scene.get('missions') or [] if isinstance(m, dict)]
        listed = self.missions_kept()[0]
        if not isinstance(listed, list):
            return list(enumerate(found))
        return [(e['record'], found[e['record']]) for e in listed
                if isinstance(e, dict) and isinstance(e.get('record'), int) and 0 <= e['record'] < len(found)]

    def kept_streams(self):
        """Each stream of the missions the variant keeps with its objects (export 24): [(label, index or kind, stream,
        objects)], the kept records' streams, then an added kind's donor stream (export 33: the added bomb's
        Slaughterhouse stream) where no kept record streams it already."""
        streams = self.c.scene.get('streams') or {}
        out, named = [], set()
        for index, mission in self.kept_missions():
            label = mission.get('label') or 'mission %d' % (index + 1)
            for name in mission.get('streams') or []:
                named.add(name)
                objects = (streams.get(name) or {}).get('missionObjects') or []
                if objects:
                    out.append((label, index, name, objects))
        for kind in sorted(self.c.added_kinds()):
            donor = (self.c.scene.get('donors') or {}).get(kind)
            if isinstance(donor, dict) and donor.get('stream') and donor['stream'] not in named and donor.get('missionObjects'):
                out.append(('%s (added)' % missions.label(kind), kind, donor['stream'], donor['missionObjects']))
        return out

    def missions_check(self):
        """What an edit means for the map's missions (private/plans/done/mission-types-plan.md): a note for a map the
        game knows by its whole name (missions.NAMED_MAPS: the Build's records can't keep it, plan Part B), and, for
        each mission the variant keeps, its stream's objects (export 24) against the edit (C3): mission_objects."""
        why = missions.named_map(self.c.map) or (missions.named_map(self.c.package) if self.c.package != self.c.map else None)
        if why:
            self.c.note('named-map', '%s is known by its name in the game\'s script, which a variant can\'t keep: %s.'
                      % (self.c.map, why))
        self.mission_list()
        self.mission_objects()
        self.spawn_places()
        self.spawn_rules_notes()

    def mission_list(self):
        """The project's `missions` (D1, optional): what of it is left out (missions_kept: an entry the Build can't
        write; the whole list, when it is no list, is empty or keeps nothing, so the variant serves every record of the
        base map); a warning for a UFO mission on a map with no UFO building (mission-ufo: Long War puts the
        commander's pod in the UFO's building volume, O-5), a note for a bomb mission added (mission-bomb: Long War's
        mutator places it; plain Enemy Within plays Slaughterhouse's places)."""
        listed, dropped = self.missions_kept()
        for where, why in dropped:
            self.c.leave_out('missions', '%s: %s left out' % (why, 'it is' if where['record'] == 'missions' else 'that entry is'),
                           **where)
        if dropped and listed is None:
            self.c.note('missions-all', 'the project\'s missions list keeps no mission the Build can write: the variant '
                      'serves every mission of %s' % self.c.map)
        if listed is None:
            return
        kinds = {e['kind'] for e in listed if 'kind' in e}
        if kinds & {'Crash', 'LandedUFO'}:
            gone = {e['actor'] for e in self.c.building_edits.edits if e.get('deleted')}
            ufo = any(b.get('kind') == 'ufo' for b in self.c.building_edits.new_buildings) or any(
                e.get('isUfo') and e.get('name', e.get('actor')) not in gone and e.get('actor') not in gone
                for e in self.c.scene.get('buildings') or [])
            if not ufo:
                self.c.warn('mission-ufo', 'the project is for a UFO mission and the map has no UFO building: Long War puts '
                          'the commander\'s pod in the UFO, so place a UFO prefab')
        if 'Special/Bomb' in kinds:
            self.c.note('mission-bomb', 'the bomb mission streams %s: Long War\'s bomb mutator places its bomb and power '
                      'nodes on the map; plain Enemy Within would play them where Slaughterhouse has them'
                      % missions.BOMB_STREAM)

    # a mission's objects that a soldier, the operative or a VIP must reach, or that stand for an objective: a warning
    # when the edit leaves one over no floor or inside a piece (C3); drop-in points and pods only get a note (Long War
    # places most of its drop-ins and pods itself)
    MISSION_REACHED = {'capturePoint', 'radar', 'bomb', 'powerNode', 'use', 'soldier', 'landing', 'operative', 'vip'}
    MISSION_SPAWNS = {'dropIn', 'pod'}

    def mission_objects(self):
        """C3, for each mission the variant keeps (kept_missions) and each stream of it that has objects: a warning
        (mission-object) for an objective, a landing's or soldier's point, the operative's or a VIP's point that had
        floor under it before the edit and has none now (the map's saved floor tiles that stay, and the floor the
        project's flat copies give), or that a copy of the project stands on; a warning (mission-capture) for a capture
        volume with none of its floor tiles left; a note (mission-spawns) for the drop-in points and pods that lose
        their floor; on a cleared map, a note (mission-cleared) that the stream's objects stand where the original map
        had them. Warnings only: the Build goes on. Each names its mission (mission, missionIndex) and the object's
        stream and actor, for the build window's list by mission."""
        grid = self.c.scene.get('tileGrid') or {}
        origin = grid.get('origin')
        kept = self.kept_streams()
        if not origin or not kept:
            return
        size = grid.get('size') or [TILE, TILE, STOREY]
        before = {tuple(f['tile']) for f in ((self.c.scene.get('tactical') or {}).get('floorTiles') or [])}
        added, _ = self.c.floor_edits.added_floors()
        now = self.c.floor_edits.floor_now() | set(added)
        corner = tile_corner(grid)      # an object's tile as the game counts it
        tile = lambda p, dz=0: (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),  # noqa: E731
                                int(math.floor((p[2] - corner[2]) / size[2])) + dz)
        under = lambda p, floors: tile(p) in floors or tile(p, -1) in floors  # noqa: E731
        solid = [c for c in self.c.copies if c.get('box') and c.get('actorClass') != 'XComLadder' and c['box'][5] - c['box'][4] > FLOOR_THICK]
        seen = set()
        g = self.grid_box()
        for label, index, name, objects in kept:
            where = dict(mission=label, missionIndex=index) if isinstance(index, int) else dict(mission=label, missionKind=index)
            donor = not isinstance(index, int)
            unmoved = [o for o in objects if self.c.moved_object(name, o)[1] is None]
            if self.cleared and unmoved and not donor:
                self.c.note('mission-cleared', '%s: %s of %s stand where the original map had them, on a cleared map: '
                          'place them, or drop the mission' % (label, '%d objects' % len(unmoved) if len(unmoved) != len(objects)
                                                              else 'the %d objects' % len(objects), name), stream=name, **where)
            lost = []
            for o in objects:
                p, offset = self.c.moved_object(name, o)
                key = (index, name, o.get('actor'))
                if key in seen:
                    continue
                seen.add(key)
                short = str(o.get('actor') or '').rsplit('.', 1)[-1]
                what = missions.object_words(o)
                if o.get('actorClass') == 'XComCapturePointVolume' and o.get('box'):
                    d = offset or [0, 0, 0]
                    b = dict(min=[o['box']['min'][k] + d[k] for k in range(3)], max=[o['box']['max'][k] + d[k] for k in range(3)])
                    inside = lambda t: (b['min'][0] <= origin[0] + (t[0] + 0.5) * size[0] <= b['max'][0]  # noqa: E731
                                        and b['min'][1] <= origin[1] + (t[1] + 0.5) * size[1] <= b['max'][1]
                                        and b['min'][2] - size[2] <= origin[2] + t[2] * size[2] <= b['max'][2])
                    had = [t for t in before if inside(t)] if offset is None else [None]
                    if had and not any(inside(t) for t in now):
                        self.c.warn('mission-capture', '%s: %s (%s) has none of its %d floor tiles left: no soldier can '
                                  'stand in it to capture it' % (label, what, short, len(had)),
                                  stream=name, actor=o.get('actor'), **where)
                    continue
                kind = o.get('kind')
                if kind not in self.MISSION_REACHED and kind not in self.MISSION_SPAWNS:
                    continue
                if o.get('role') in ('effect', 'rebuild', 'visible', 'waypoint', 'volume', 'point'):
                    continue
                if donor:
                    # an added kind's object stands where its own map has it until placed: its fallback place
                    # (Long War plays it there when it finds no place of its own), checked on this map as it is
                    if kind in ('bomb', 'powerNode') and offset is None:
                        out_grid = g is not None and not (g[0] <= p[0] <= g[3] and g[1] <= p[1] <= g[4])
                        inside = next((c for c in solid if c['box'][0] <= p[0] <= c['box'][1] and c['box'][2] <= p[1] <= c['box'][3]
                                       and c['box'][4] < p[2] + STOREY and c['box'][5] > p[2] - 24), None)
                        why = ('off the map\'s grid' if out_grid else 'over no floor' if not under(p, now)
                               else 'inside %s' % inside['label'].split(':', 1)[-1] if inside else None)
                        if why:
                            self.c.warn('mission-donor-place', '%s: %s (%s) still stands where %s has it, which here is %s: Long '
                                      'War plays it there when it finds no place of its own; place it on the map'
                                      % (label, what, short, name, why), stream=name, actor=o.get('actor'), **where)
                        continue
                # (moved, it needs floor where it stands now, whatever the map had there)
                bare = (under(p, before) or offset is not None) and not under(p, now)
                on = next((c for c in solid if c['box'][0] <= p[0] <= c['box'][1] and c['box'][2] <= p[1] <= c['box'][3]
                           and c['box'][4] < p[2] + STOREY and c['box'][5] > p[2] - 24), None)
                if kind in self.MISSION_SPAWNS:
                    if bare or on: lost.append(o)
                    continue
                if bare:
                    self.c.warn('mission-object', '%s: %s (%s) has no floor under it now: %s' % (
                        label, what, short, missions.object_risk(o)), stream=name, actor=o.get('actor'), **where)
                if on:
                    self.c.warn('mission-object', '%s: %s (%s) is inside %s now: %s' % (
                        label, what, short, on['label'].split(':', 1)[-1], missions.object_risk(o)),
                        stream=name, actor=o.get('actor'), **where)
            if lost:
                count = {}
                for o in lost: count[o['kind']] = count.get(o['kind'], 0) + 1
                words = ', '.join('%d %s' % (n, missions.object_words(dict(kind=k), plural=n != 1)) for k, n in sorted(count.items()))
                self.c.note('mission-spawns', '%s: %s of %s stand over no floor or inside a piece now (Long War places '
                          'most drop-ins and pods itself; plain Enemy Within uses them where they stand)'
                          % (label, words, name), stream=name, **where)

    def projected_spawns(self):
        """The base map's spawn points as the variant will have them (export 33: scene.json's `spawns`): [(record,
        location)], a point a delete record takes out left out. Spawns plan, SP5; the base point edits (SP6, SP7) move,
        copy and delete them here."""
        gone = {e['target'] for e in self.c.entities if e['kind'] == 'delete' or (e['kind'] == 'spawn' and e['op'] == 'delete')}
        moved = {e['target']: e['location'] for e in self.c.entities if e['kind'] == 'spawn' and e['op'] == 'move'}
        valued = {e['target']: e['spawn'] for e in self.c.entities if e['kind'] == 'spawn' and e['op'] == 'values'}
        with_values = lambda r, values: dict(r, values=dict(r.get('values') or {}, **{  # noqa: E731
            k: {'value': v, 'from': 'project'} for k, v in (values or {}).items()})) if values else r
        out = [(with_values(r, valued.get(r['actor'])), moved.get(r['actor'], r['location'])) for r in self.c.scene.get('spawns') or []
               if isinstance(r, dict) and isinstance(r.get('location'), list) and r.get('actor') not in gone]
        # (a copy: its template's record under its own name, with its values; never one the map had)
        for e in self.c.entities:
            if e['kind'] == 'spawn' and e['op'] == 'add':
                t = self.c.spawn_edits.actors.get(e['template'])
                if t:
                    out.append((with_values(dict(t, actor=e['entity'], copied=True), e.get('spawn')), e['location']))
        return out

    def spawn_places(self):
        """The base map's pods and Meld points against the edit (spawns plan, SP5): a pod or Meld point's place is usable
        when it is in the grid, over floor (the map's that stays, or the project's own) and in no solid piece of the
        project. Warnings: spawn-pod-places when fewer pod places are usable than the map had (plain Enemy Within, and
        the missions Long War's pod mutator leaves alone, put a pod at each: fewer places than pods can lose one);
        spawn-meld-group when a Meld spawn group loses every usable hard point, or every point, it had. A note,
        spawn-outside, counts the points a resized grid leaves outside. Each names the variant's mission (its one, or
        every one) and the first point it is about, for the build window's "show"."""
        grid = self.c.scene.get('tileGrid') or {}
        records = self.projected_spawns()
        if not grid.get('origin') or not grid.get('dimensions') or not records:
            return
        size = grid.get('size') or [TILE, TILE, STOREY]
        corner = tile_corner(grid)
        tile = lambda p, dz=0: (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),  # noqa: E731
                                int(math.floor((p[2] - corner[2]) / size[2])) + dz)
        before = {tuple(f['tile']) for f in ((self.c.scene.get('tactical') or {}).get('floorTiles') or [])}
        added, _ = self.c.floor_edits.added_floors()
        now = self.c.floor_edits.floor_now() | set(added)
        o, dims = grid['origin'], grid['dimensions']
        box_before = [o[0], o[1], o[0] + dims[0] * size[0], o[1] + dims[1] * size[1]]
        g = self.grid_box()
        box_now = [g[0], g[1], g[3], g[4]]
        solid = [c for c in self.c.copies if c.get('box') and c.get('actorClass') != 'XComLadder' and c['box'][5] - c['box'][4] > FLOOR_THICK]
        inside_box = lambda p, b: b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]  # noqa: E731
        in_piece = lambda p: any(c['box'][0] <= p[0] <= c['box'][1] and c['box'][2] <= p[1] <= c['box'][3]  # noqa: E731
                                 and c['box'][4] < p[2] + STOREY and c['box'][5] > p[2] - 24 for c in solid)
        under = lambda p, floors: tile(p) in floors or tile(p, -1) in floors  # noqa: E731
        was = lambda r: not r.get('copied') and inside_box(r['location'], box_before) and under(r['location'], before)  # noqa: E731
        usable = lambda p: inside_box(p, box_now) and under(p, now) and not in_piece(p)  # noqa: E731
        labels = [m.get('label') or 'mission %d' % (i + 1) for i, m in self.kept_missions()]
        labels += ['%s (added)' % missions.label(k) for k in sorted(self.c.added_kinds())]
        where = dict(mission=labels[0] if len(labels) == 1 else 'Every mission of the variant')
        name = lambda r: str(r.get('actor') or '').rsplit('.', 1)[-1]  # noqa: E731

        pods = [(r, p) for r, p in records if r.get('kind') == 'pod']
        had = [r for r, _ in pods if was(r)]
        has = [r for r, p in pods if usable(p)]
        if len(has) < len(had):
            lost = next((r for r, p in pods if was(r) and not usable(p)), None) or had[0]
            self.c.warn('spawn-pod-places', '%s: %d of the map\'s pod places are usable now, where %d were (in the grid, over '
                      'floor, in no piece of the project), %s among those lost: plain Enemy Within, and the missions Long '
                      'War\'s pod mutator leaves alone, put a pod at each place, and with fewer places than pods it can '
                      'lose one' % (where['mission'], len(has), len(had), name(lost)), actor=lost.get('actor'),
                      before=len(had), now=len(has), **where)

        groups = {}
        for r, p in records:
            if r.get('kind') == 'meld':
                group = ((r.get('values') or {}).get('spawnGroup') or {}).get('value', 0)
                groups.setdefault(group if isinstance(group, int) else 0, []).append((r, p))
        for group, points in sorted(groups.items()):
            hard = lambda r: str(((r.get('values') or {}).get('difficulty') or {}).get('value', '')).endswith('Hard')  # noqa: E731
            had_any = [r for r, _ in points if was(r)]
            has_any = [r for r, p in points if usable(p)]
            had_hard = [r for r in had_any if hard(r)]
            has_hard = [r for r in has_any if hard(r)]
            if had_any and not has_any:
                self.c.warn('spawn-meld-group', '%s: Meld spawn group %d has none of its %d usable points left (in the grid, '
                          'over floor, in no piece of the project): when the mission picks this group it places no '
                          'canister' % (where['mission'], group, len(had_any)), actor=had_any[0].get('actor'),
                          group=group, **where)
            elif had_hard and not has_hard:
                self.c.warn('spawn-meld-group', '%s: Meld spawn group %d has none of its %d usable hard points left (in the '
                          'grid, over floor, in no piece of the project): the mission places a hard canister of the group '
                          'first, and without one it places fewer' % (where['mission'], group, len(had_hard)),
                          actor=had_hard[0].get('actor'), group=group, **where)

        if self.stage_grid:
            out = [r for r, p in records if r.get('kind') in ('pod', 'meld') and not r.get('copied') and inside_box(r['location'], box_before)
                   and not inside_box(p, box_now)]
            if out:
                count = {}
                for r in out: count[r['kind']] = count.get(r['kind'], 0) + 1
                words = ' and '.join('%d %s' % (n, ('pod' if k == 'pod' else 'Meld point') + ('s' if n != 1 else ''))
                                     for k, n in sorted(count.items(), key=lambda kv: kv[0] != 'pod'))
                self.c.note('spawn-outside', '%s of the map stand outside the grid as the project sizes it, %s among them'
                          % (words, name(out[0])), actor=out[0].get('actor'), count=len(out), **where)

    def check_zones(self, zones, own=False):
        """Warnings for zones' places: outside the grid, over no floor, a piece of the project on a soldier point, and
        a grid too small for LWR's pods (stage-small, F-90)."""
        g = self.grid_box()
        if g is None:
            return
        grid = self.c.scene['tileGrid']
        # a soldier's spot's tile as the game counts it (tile_corner)
        corner, size = tile_corner(grid), grid.get('size') or [TILE, TILE, STOREY]
        label = (lambda k: "the map's landing %d" % (k + 1)) if own else (lambda k: 'landing zone %d' % (k + 1))
        floors = self.c.floor_edits.floor_now()
        added, _ = self.c.floor_edits.added_floors()
        scenery = self.c.floor_edits.scenery_floor()
        # each zone's own landing, where it is one (a landing with no frame keeps its own points until its zone moves)
        found = self.own_landings_found or []
        mine = {k: found[k] for k in range(min(len(zones), len(found)))} if own else \
            {k: found[j] for j, k in enumerate(spawns.own_slots(zones, len(found)))}
        far = []
        for k, z in enumerate(zones):
            at = spawns.place(z)
            points = [p for p, _ in spawns.soldier_spots(z, mine.get(k))]
            ground = spawns.ground(z)
            if any(not (g[0] <= p[0] <= g[3] and g[1] <= p[1] <= g[4] and g[2] <= p[2] <= g[5]) for p in points + [at['frame'][0]]):
                self.c.warn('landing-outside', '%s is outside the tile grid: its soldiers would stand where there are no '
                          'tiles' % label(k), zone=z['id'])
                continue
            bare, blocked = [], []
            for n, p in enumerate(points):
                # (its ground's level: a ground up to a unit under a level's start is in it, as the maps' floors are
                # a unit over the game's corner; 2 over the level volume's, as before)
                tile = (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),
                        int(math.floor((ground + 1.0 - corner[2]) / size[2])))
                if (tile not in floors and tile not in added
                        and not any(b[0] <= p[0] <= b[1] and b[2] <= p[1] <= b[3] and abs(b[5] - ground) <= 20.0
                                    for b in scenery)):
                    bare.append(n + 1)
                for c in self.c.copies:
                    b = c['box']
                    if c.get('actorClass') == 'XComLadder' or b[5] - b[4] <= FLOOR_THICK:
                        continue
                    if b[0] <= p[0] <= b[1] and b[2] <= p[1] <= b[3] and b[4] < ground + HEADROOM and b[5] > ground + 8:
                        blocked.append((n + 1, c['label'].split(':', 1)[-1]))
                        break
            if bare:
                self.c.warn('landing-floor', '%s: soldier point%s %s %s over no floor of the map or the project: lay floor '
                          'there, or the squad lands on nothing (F-46)'
                          % (label(k), '' if len(bare) == 1 else 's', numbers(bare), 'is' if len(bare) == 1 else 'are'),
                          zone=z['id'], points=bare)
            if blocked:
                who = sorted({b for _, b in blocked})
                self.c.warn('landing-blocked', '%s: %s stand%s on soldier point%s %s, where a soldier lands (F-06)'
                          % (label(k), ', '.join(who), 's' if len(who) == 1 else '', '' if len(blocked) == 1 else 's',
                             numbers([n for n, _ in blocked])), zone=z['id'])
            # LWR's pod mutator keeps only map sections at least POD_DISTANCE tiles from the squad's middle (F-90)
            mx, my = sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
            reach = max(math.hypot(x - mx, y - my) for x in (g[0], g[3]) for y in (g[1], g[4]))
            if reach < POD_DISTANCE * size[0]:
                far.append(k)
        if far and (self.cleared or self.stage_grid):
            self.c.warn('stage-small', 'no part of the grid is %d tiles from %s: LWR places no pods or Meld there for a '
                      'squad landing at %s (F-90)' % (POD_DISTANCE, ', '.join(label(k) for k in far),
                                                      'it' if len(far) == 1 else 'them'), zones=[zones[k]['id'] for k in far])
