"""Which piece each of a map's diagonal cover marks takes its cover from (diagonal cover by hand, stage M5: marks follow
their pieces; private/plans/todo/diagonal-cover-by-hand-and-views-plan.md, section 5).

A marked tile's cover is worked out as the game's build works out a seeded tile (tile_rule.cover along the four
diagonals, against the map's pieces and its baked tile data: diagonal_keep.Loaded), and each diagonal that gives cover
names the piece its sweep met: the wall. The editor carries a mark with that piece when the piece is moved, copied or
deleted. Nothing here writes.

  walls(p)    {tile: {(sx, sy): the wall's actor path}} for the map's marked tiles that have a floor of their own
  marks(p)    [{at, toward, low?, wall}]: each marked tile's corners with one wall (`low`: the ones the map gives
              half cover), the tile named by its middle in the world (a piece of this map placed in another brings its
              marks: tools/viewer/library.py)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE.parent / 'upk', HERE.parent / 'viewer', HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))


def walls(p):
    """The wall of each corner of each of the map's marked tiles (its bake's diagonal cover): {tile: {(sx, sy): actor
    path}}, the corners the rule finds a wall along; a tile with no floor of its own (the flag alone) has none."""
    return {t: {c: wall for c, (wall, _) in corners.items()} for t, corners in _walls(p).items()}


def _walls(p):
    """walls' {tile: {(sx, sy): (actor path, low: whether the map's cover that way is half)}}."""
    import diagonal_keep
    import native_copy
    import tile_rule
    marked = native_copy.diagonal_tiles(p)
    if not marked:
        return {}
    ld = diagonal_keep.Loaded(p)
    view = ld.view()
    names = {pc.name: pc.actor for pc in ld.world.pieces}
    baked = ld.cover
    out = {}
    for t in sorted(marked):
        if not tile_rule.candidate(view, t):
            continue
        c = tile_rule.cover(ld.world, view, t, True)
        corners = {}
        for i, e in enumerate(tile_rule.TABLE):
            part = c['parts'].get(e['name'])
            if part and part['hit'] in names:
                corners[tuple(diagonal_keep.toward(i))] = (p.name(names[part['hit']]), bool(baked.get(t, 0) & e['low']))
        if corners:
            out[t] = corners
    return out


def marks(p):
    """The map's marks with the piece each takes its cover from: [{at (the tile's middle in the world, the level's
    middle in height), toward [[sx, sy]...], wall (actor path)}], one record for each tile and wall."""
    import native_copy
    found = _walls(p)
    if not found:
        return []
    grid = native_copy.level_grid(p)
    corner = (grid['tx'], grid['ty'], grid['tz'])
    out = []
    for t, corners in sorted(found.items()):
        at = [round(corner[k] + size * (t[k] + 0.5), 4) for k, size in enumerate((96.0, 96.0, 64.0))]
        for wall in sorted({w for w, _ in corners.values()}):
            low = sorted([list(c) for c, (w, half) in corners.items() if w == wall and half])
            out.append(dict(at=at, toward=sorted([list(c) for c, (w, _) in corners.items() if w == wall]),
                            **({'low': low} if low else {}), wall=wall))
    return out
