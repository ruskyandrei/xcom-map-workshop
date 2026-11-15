"""The map's own landings moved in place (private/plans/done/clear-map-plan.md, section 4; findings register F-96 to
F-98): what a plain Enemy Within install plays, and what LWR's landing-zone mutator spawns its landing from.

A project's landing zones (the compiler's `landingZones`: {zones, own, ownLandings}) name, by `own`, the zones that are
also the map's own landings: the first own slot is the map's first landing (its group by the game's order, export 22),
the second the second. Each such zone that puts the landing somewhere else than the map has it moves the landing's
prefab's actors in place, by the offsets of LWR's mutator (XComLZMutator.CalcLocations; tools/viewer/spawns.py), so
that both installs land the squad at the same place:
- the drop zone's frame to the zone's place, turned by the zone's direction;
- the evac volume, the player start and the PointInSpace to their offsets, each turned as the mutator turns them
  (AdjRotation: the zone's turn plus its own yaw less the frame's). The evac volume saves Rotation (0, 0, 0), its turn
  being baked into its brush (F-98), so it is written the zone's turn less the frame's;
- the six soldier points to their offsets, facing a quarter turn on (FaceRot);
- the grounded Skyranger next to the landing (its prefab's mesh, emitter, sound and PointInSpace) by the same rigid
  move as the frame: from the frame's old place and turn to its new ones.
A landing with no frame (the tutorial's, TempleShip's, the alien bases') is the zone spawns.fit_zone fits to its soldier
points; while the zone stays there nothing moves, and moved, its actors go to the zone's offsets as any landing's do
(its own layout is not kept), the Skyranger from where the fitted zone's frame would stand.
Every actor keeps its name and archetype (LWR finds its templates by archetype; the mission script's show-or-hide
switch names the Skyranger and the frame). A player start based on another actor gets its RelativeLocation anew.
The Skyranger is in the baked tile data: a rebuild volume goes over its old place and its new one, which is seeded as
a copy's is.

A full Build's relight sees the move (F-98): native_copy.py hands each moved piece with a mesh to relight.py as
moved in place (--moved-in-place, with its old pose), so its shadow leaves the old place and falls at the new one. Its
own lightmap and shadow maps keep their bake.

  python -B tools/bake/native_spawns.py <map.upk> <native-edit.json> <out.upk>   (a check: the moves on their own)
"""
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import props as legacy_props  # noqa: E402
import scene_metadata  # noqa: E402
import spawns  # noqa: E402

TURN = 65536
SAME = 4.0     # a zone whose frame and soldiers are this near the landing's own is the landing unmoved


def norm(yaw):
    """A yaw in (-32768, 32768]."""
    yaw = int(round(yaw)) % TURN
    return yaw - TURN if yaw > TURN // 2 else yaw


def unmoved(landing, zone, bottom=None):
    """Whether the zone puts the landing where the map has it: its frame and six soldier points within SAME units,
    the frame's turn the zone's."""
    by = {a['role']: a for a in landing['actors']}
    at = spawns.place(zone)
    frame = by.get('frame')
    if frame is None:
        fitted = spawns.fit_zone(landing['actors'], bottom)
        return fitted is not None and spawns.at_own_place(zone, dict(zone=fitted))
    if norm(frame['rotation'][1] - at['frame'][1]) != 0:
        return False
    pairs = [(frame['location'], at['frame'][0])] + [(by['soldier%d' % (k + 1)]['location'], at['soldiers'][k][0])
                                                     for k in range(6) if 'soldier%d' % (k + 1) in by]
    return all(all(abs(a[j] - b[j]) <= SAME for j in range(3)) for a, b in pairs)


def plan(landings, zones, bottom=None):
    """The moves for a project's zones ({zones, own}): [dict(landing (its prefab), group, zone (its id), actors:
    [dict(path, role, old: (location, rotation), new: (location, rotation), relative?)])], one for each own slot
    whose zone moves its landing. `landings` is scene_metadata.landing_metadata's list, in the game's order;
    `bottom` the tile grid's (a landing with no frame is fitted on it: spawns.fit_zone)."""
    out = []
    for k, slot in enumerate(zones.get('own') or []):
        if k >= len(landings):
            break
        landing, zone = landings[k], zones['zones'][slot]
        by = {a['role']: a for a in landing['actors']}
        here = spawns.frame_of(landing, bottom)
        if here is None or unmoved(landing, zone, bottom):
            continue
        at = spawns.place(zone)
        frame = by.get('frame')
        f_loc, f_yaw = here
        z_yaw = spawns.yaw_of(zone['direction'])
        actors = []

        def move(a, location, yaw):
            actors.append(dict(path=a['path'], role=a['role'], actorClass=a['actorClass'], savesRotation=a['savesRotation'],
                               old=(list(a['location']), list(a['rotation'])),
                               new=([round(v, 4) for v in location], [a['rotation'][0], norm(yaw), a['rotation'][2]])))
        if frame:
            move(frame, at['frame'][0], z_yaw)
        for role in ('volume', 'playerStart', 'point'):
            if role in by:
                a = by[role]
                move(a, at[role][0], z_yaw + a['rotation'][1] - f_yaw)
        for n in range(6):
            a = by.get('soldier%d' % (n + 1))
            if a:
                move(a, at['soldiers'][n][0], at['soldiers'][n][1])
        sky = landing.get('skyranger')
        if sky:
            turn = z_yaw - f_yaw
            for a in sky['actors']:
                d = spawns.turn([a['location'][j] - f_loc[j] for j in range(3)], turn)
                move(a, [at['frame'][0][j] + d[j] for j in range(3)], a['rotation'][1] + turn)
        out.append(dict(landing=landing['prefab'], group=landing.get('group'), index=k, zone=zone['id'], slot=slot,
                        frame=dict(old=[list(f_loc), f_yaw], new=[list(at['frame'][0]), z_yaw]),
                        skyranger=sky['prefab'] if sky else None, actors=actors))
    return out


def _set(walker, g, p, index, location=None, rotation=None, relative=None):
    import native_lights
    e = p.exports[index - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    if location is not None:
        data = native_lights.set_property(walker, g, data, start, 'Location', 'StructProperty', 'Vector',
                                          struct.pack('<3f', *location))
    if rotation is not None:
        data = native_lights.set_property(walker, g, data, start, 'Rotation', 'StructProperty', 'Rotator',
                                          struct.pack('<3i', *rotation))
    if relative is not None:
        data = native_lights.set_property(walker, g, data, start, 'RelativeLocation', 'StructProperty', 'Vector',
                                          struct.pack('<3f', *relative))
    g.relocate(index, bytes(data))


def apply(g, p, zones, gone=()):
    """The project's own landings moved in the map (`g` the grower of package `p`): returns (the report: the moves,
    each actor's old and new pose, and the tiles; the rebuild volumes to add to the level). `gone`: actors the edit
    takes out (never moved)."""
    import native_copy
    walker = native_copy.Walker(p)
    moves = plan(scene_metadata.landing_metadata(p), zones, native_copy.level_grid(p)['oz'])
    volumes, report = [], []
    for m in moves:
        tiles = []
        for a in m['actors']:
            i = p.by_name[a['path']]
            if i in gone:
                a['skipped'] = 'taken out by the edit'
                continue
            (loc0, rot0), (loc1, rot1) = a['old'], a['new']
            rotation = rot1 if (a['savesRotation'] or rot1 != rot0) else None
            relative = None
            if p.cls(i) == 'PlayerStart' and p.own(i, 'RelativeLocation') is not None:
                base = p.own(i, 'Base', 0)
                if base > 0:
                    b_loc, b_yaw = p.own(base, 'Location', [0.0, 0.0, 0.0]), (p.own(base, 'Rotation') or [0, 0, 0])[1]
                    relative = spawns.turn([loc1[j] - b_loc[j] for j in range(3)], -b_yaw)
                    a['relative'] = [round(v, 4) for v in relative]
            _set(walker, g, p, i, loc1, rotation, relative)
            # a piece in the baked tiles (the Skyranger): its old tiles rebuilt, its new ones seeded and rebuilt
            if native_copy.has_mesh(p, i) and native_copy.collides(p, i):
                old = native_copy.hide_tiles(g, p, native_copy.piece_box(p, i, loc0, rot0))
                new = native_copy.add_tiles_box(g, p, native_copy.piece_box(p, i, loc1, rot1))
                for t in (old, new):
                    if t:
                        volumes.append(t['volume']['export'])
                tiles.append(dict(actor=a['path'].split('.')[-1], old=old['tiles'] if old else None,
                                  new=new['tiles'] if new else None, seeded=new['seeded'] if new else 0))
        report.append(dict(m, tiles=tiles))
    return report, volumes


def main(argv=None):
    import package_grow
    from package import Package
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print(__doc__)
        return 2
    src, edit, out = argv
    zones = json.loads(Path(edit).read_text(encoding='utf-8')).get('landingZones')
    p = Package(src)
    g = package_grow.Grower(str(src))
    report, volumes = apply(g, p, zones or {})
    import native_copy
    if volumes:
        native_copy.add_to_level(g, p, volumes)
    g.write(str(out))
    for m in report:
        print('%s (%s) to zone %s: %d actors moved' % (m['landing'], m['group'], m['zone'], len(m['actors'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
