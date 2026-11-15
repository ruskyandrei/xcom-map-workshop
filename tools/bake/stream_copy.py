"""A streamed package copied for a variant, with some of its actors taken out (private/plans/done/cars-doors-ladders-plan.md,
section 3.6, step G6).

LWR's patches, which every record of their map keeps streaming, hold hidden pieces that stand in for the map's own:
patch_bar holds a hidden ladder beside each of the bar's two. The game makes a climb for any ladder of any loaded
level, so a bar ladder moved or deleted would still climb where it stood. The variant streams this copy instead
(the Build's manifest, replaceStreams): the named actors' slots in its persistent level's actor list are emptied, as
the map's own hidden pieces are (native_copy.empty_slots), so the game never spawns them. Nothing else changes.

A mission's stream is copied the same way when the project moves its objects (private/plans/done/mission-types-plan.md,
Part E): each named actor's Location and Rotation are set in place (`--moves`: a JSON list of {actor, location,
rotation}), so every reference to it holds (the Kismet's variables, the wave system's groups, the handlers' lists),
and an actor based on another (a RelativeLocation and a Base) gets its RelativeLocation from its base's pose. The
copy is streamed by the variant's records for that mission alone, so the Switch String entries naming the base map
(the DLC streams' branches by map, F-45's kind) name the variant (`--base`, `--variant`), as an intro copy's do.
`tile_boxes` gives the Build the world boxes of the moved pieces that touch the game's tiles, before and after: the
base map's baked tiles are rebuilt at the old place and seeded and rebuilt at the new one (native_copy.py
--copies' streamTiles).

  python -B tools/bake/stream_copy.py <stream.upk> <copy.upk> [--hide XComLadder_11 ...] [--moves moves.json]
                                      [--base <map> --variant <variant>] [--report report.json]
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import audit_lighting as lighting  # noqa: E402
import native_copy  # noqa: E402
import package_grow  # noqa: E402

PL = native_copy.PL


def level_actor(p, name, src):
    """The export of actor `name` (as XComLadder_11) of the package's persistent level, or a ValueError."""
    level = p.by_name.get('TheWorld.PersistentLevel')
    if level is None:
        raise ValueError(f'{Path(src).name} has no persistent level')
    i = p.by_name.get(PL + name)
    if i is None or p.exports[i - 1]['outer'] != level:
        raise ValueError(f'{Path(src).name} has no actor {name} in its level')
    return i


def move_actors(g, p, moves, src):
    """Each move ({actor, location, rotation}) set in place: Location and Rotation (added where the actor saves
    none), and an actor's RelativeLocation from its Base's pose (the base's new one when it moves too). Returns the
    report's rows."""
    import native_spawns
    import spawns
    walker = native_copy.Walker(p)
    poses = {level_actor(p, m['actor'], src): m for m in moves}
    rows = []
    for i, m in poses.items():
        old = pose(p, i)
        location, rotation = [float(v) for v in m['location']], [int(v) for v in m['rotation']]
        relative = None
        base = p.own(i, 'Base', 0)
        if base and base > 0 and p.own(i, 'RelativeLocation') is not None:
            b = poses.get(base)
            b_loc, b_turn = (b['location'], b['rotation']) if b else pose(p, base)
            b_yaw = b_turn[1]
            relative = spawns.turn([location[k] - b_loc[k] for k in range(3)], -b_yaw)
        native_spawns._set(walker, g, p, i, location, rotation if list(rotation) != list(old[1]) or p.own(i, 'Rotation') is not None
                           else None, relative)
        rows.append(dict(actor=m['actor'], export=i, old=dict(location=list(old[0]), rotation=list(old[1])),
                         new=dict(location=location, rotation=rotation),
                         **({'relative': [round(v, 4) for v in relative]} if relative is not None else {})))
    return rows


def pose(p, i):
    """An actor's place and turn as the game reads them: its own Location and Rotation, else its archetype's (Police
    Station's captured encoder saves no Rotation; its archetype turns it a quarter), else none."""
    return ([float(v) for v in p.effective(i, 'Location', [0.0, 0.0, 0.0])],
            [int(v) for v in p.effective(i, 'Rotation', [0, 0, 0])])


def tile_boxes(src, moves):
    """The moved actors of stream `src` that touch the game's tiles (a mesh that collides: a power node, the bomb,
    an objective's mesh): [{actor, old, new}], each a world box [x0, x1, y0, y1, z0, z1] at the actor's old and new
    pose. The base map's tiles are rebuilt under the old box and seeded and rebuilt under the new one."""
    p = lighting.Package(src)
    out = []
    for m in moves:
        i = level_actor(p, m['actor'], src)
        if not (native_copy.has_mesh(p, i) and native_copy.collides(p, i)):
            continue
        old = pose(p, i)
        out.append(dict(actor=m['actor'], old=native_copy.piece_box(p, i, list(old[0]), list(old[1])),
                        new=native_copy.piece_box(p, i, [float(v) for v in m['location']], [int(v) for v in m['rotation']])))
    return out


def make(src, dst, hides, moves=(), base=None, variant=None):
    """<dst>: <src> with the actors `hides` (names in its persistent level, as XComLadder_11) out of its level's actor
    list, the actors `moves` names moved in place, and, with `base` and `variant` and moves, the Switch String entries
    naming `base` naming `variant`. Returns the report: source, copy, hidden [{name, export}], moved, renamed, the
    list's length."""
    src, dst = Path(src), Path(dst)
    p = lighting.Package(src)
    gone = {name: level_actor(p, name, src) for name in hides}
    if set(gone) & {m['actor'] for m in moves}:
        raise ValueError('an actor is both moved and taken out: %s' % sorted(set(gone) & {m['actor'] for m in moves}))
    g = package_grow.Grower(str(src))
    if gone:
        native_copy.empty_slots(g, p, set(gone.values()))
    moved = move_actors(g, p, moves, src) if moves else []
    renamed = []
    if moves and base and variant:
        import intro_copy
        renamed = intro_copy.rename_switches(g, p, base, variant)
    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = g.write(str(dst))
    q = lighting.Package(dst)
    left = [a for a in native_copy.level_actors(q) if a in gone.values()]
    if left:
        raise ValueError(f'the copy still lists {[q.name(a) for a in left]}')
    for row in moved:
        i = q.by_name[PL + row['actor']]
        at = q.own(i, 'Location', [0.0, 0.0, 0.0])
        if any(abs(at[k] - row['new']['location'][k]) > 1e-3 for k in range(3)):
            raise ValueError(f"the copy has {row['actor']} at {at}, not {row['new']['location']}")
    return dict(source=str(src), sourceSha256=lighting.digest(src), copy=str(dst), copySha256=lighting.digest(dst),
                hidden=[dict(name=n, export=i) for n, i in sorted(gone.items())], moved=moved, renamed=renamed,
                actors=len(native_copy.level_actors(q)),
                writer=writer, tool=dict(path='tools/bake/stream_copy.py', sha256=lighting.digest(__file__)))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('src', type=Path, help='the streamed package, as patch_bar.upk')
    a.add_argument('dst', type=Path, help='the copy, as patch_bar_<variant>.upk')
    a.add_argument('--hide', action='append', default=[], help='an actor of its level to take out (repeat)')
    a.add_argument('--moves', type=Path, help='a JSON list of {actor, location, rotation}: actors moved in place')
    a.add_argument('--base', help='the base map whose name the copy\'s map switches name (with --moves)')
    a.add_argument('--variant', help='the variant\'s name, which they name instead')
    a.add_argument('--report', type=Path, help='write the report here too')
    args = a.parse_args(argv)
    moves = json.loads(args.moves.read_text(encoding='utf-8')) if args.moves else []
    if not args.hide and not moves:
        a.error('nothing to do: give --hide or --moves')
    report = make(args.src, args.dst, args.hide, moves, args.base, args.variant)
    if args.report:
        args.report.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f"{args.dst.name}: {', '.join(h['name'] for h in report['hidden']) or 'nothing'} out of its level, "
          f"{len(report['moved'])} moved, {len(report['renamed'])} switches renamed ({report['actors']} slots)")


if __name__ == '__main__':
    main()
