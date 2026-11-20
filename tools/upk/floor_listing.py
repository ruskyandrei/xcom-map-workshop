"""Which floors of a building list a piece: the game editor's own rule (research/native/building-cutaway.md,
RebuildCachedActors; findings register F-87), as every Build lists the pieces of the buildings it makes and edits
(tools/bake/buildings.py) and the buildings survey checked it against the maps (audit_buildings.py).

A piece counts for each floor whose volume it touches with its bottom more than MARGIN under the volume's top; one
with bCutoutMask is listed on the lowest of them only, its CutdownFloor the index of the highest.
"""

MARGIN = 20.0  # the exe's constant: a piece is a floor's when its bottom is more than this under the volume's top


def touched(box, floors, margin=MARGIN, slack=0.0):
    """The indices of the floors a world box [x0, x1, y0, y1, z0, z1] counts for: it meets one of the floor's volume
    boxes ([x0, y0, z0, x1, y1, z1]), or comes within `slack` of it, and its bottom is more than `margin` under that
    volume's top."""
    out = []
    for k, volumes in enumerate(floors):
        for v in volumes:
            if v and box[4] < v[5] - margin and all(
                    box[2 * j] <= v[j + 3] + slack and box[2 * j + 1] >= v[j] - slack for j in range(3)):
                out.append(k)
                break
    return out


def listing(floors, mask):
    """Where the game's editor lists a piece that counts for the floors `floors` (indices, as touched() gives):
    [(floor index, CutdownFloor)]. A piece with bCutoutMask is listed on the lowest only, its CutdownFloor the index
    of the highest when that is another floor (0: none); any other piece on each, with no CutdownFloor."""
    if not floors:
        return []
    if mask and len(floors) > 1:
        return [(min(floors), max(floors))]
    return [(k, 0) for k in sorted(floors)]
