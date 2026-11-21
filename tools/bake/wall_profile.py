"""A made wall's outline across its thickness, as frac_wall.py's general path builds it (a measured look's recipe:
its `profile`, `strips`, `splits` and heights; frac_wall.py's block "any look" says what each holds): the height a
storey less takes out of it, and the free form's shape (custom geometry improvements plan, stage 2): a look's outline
resized to a wall's faces, bottom and top, and a window of it for a band of a tall wall.

The free form's shape, free_shape(R, y0, y1, z0, z1, band), in four steps:
- the Bar look (wall_looks.json's, built by frac_wall.py's first path from its symmetric `section`) is written as a
  measured look (as_measured), so every free wall is built by the general path;
- the faces go to y0 (side B) and y1 (side A): each side's corners move with its face, so a trim stands as far proud
  of its face as it did (thickened); the collision across moves with the faces too;
- the bottom goes to z0 and the top to z1 (heightened): the outline is raised to z0, then the height it lacks is put
  into, or the height it has too much taken out of, the longest stretch upright on both sides at once (storey_cut,
  lowered), the bands under and over it keeping their sizes; where no such stretch can take it (none upright on both
  sides, or a shortening that would eat the bands), every height is scaled between z0 and z1 instead (proportional).
  The faces' textures are read where they were before the raise (`uvShiftZ`), so a wall's pattern stays on it;
- a band [lo, hi] of a tall stretched wall is the outline between those heights (windowed): no bottom trims when lo is
  over the bottom, no top trims when hi is under the top, each strip's texture going on as it did on the whole.
"""
from free_form import NumbersError

STOREY_HEIGHT = 192.0           # the game's storey: what a storey less takes out of a measured look
RUN_LEFT = 8.0                  # what a storey's cut leaves of the straight run it is taken out of, at least
EPS = 1e-6
THINNEST = 0.5                  # units: the least thickness a free wall's outline keeps at any height


def storey_cut(R, drop):
    """Where a measured look loses `drop` of height (a storey less): the top `drop` of the longest stretch upright on
    both sides at once, each in one segment, when it leaves RUN_LEFT of that stretch: dict(lo, hi, segments {side: k}),
    or None. A `drop` under 0 is height put in (the free form's taller walls): any such stretch takes it, at its top
    (lowered then raises everything from there)."""
    runs = {X: [(za, zb, k) for k, ((ya, za), (yb, zb)) in enumerate(zip(R['profile'][X], R['profile'][X][1:]))
                if abs(ya - yb) < 1e-6 and zb > za] for X in 'AB'}
    need = drop + RUN_LEFT if drop > 0 else EPS
    best = None
    for a0, a1, ka in runs['A']:
        for b0, b1, kb in runs['B']:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo >= need and (best is None or (hi - lo, hi) > best[0]):
                best = ((hi - lo, hi), dict(lo=hi - drop, hi=hi, segments=dict(A=ka, B=kb)))
    return best[1] if best else None


def lowered(R, cut, drop):
    """The measured look `R` with `drop` taken out at `cut` (storey_cut's): every corner from the cut's top up `drop`
    lower, the segments that held the cut shorter (their texture up them kept to the unit, as before), the splits above
    lower; the caps' and the faces' textures as they were. A `drop` under 0 puts that much in: the corners from the
    cut's top up higher, the segments that held it longer."""
    profile, strips = {}, {}
    for X in 'AB':
        corners = [[y, z - drop if z >= cut['hi'] - 1e-9 else z] for y, z in R['profile'][X]]
        rows = [dict(s) for s in R['strips'][X]]
        k = cut['segments'][X]
        (_, za), (_, zb) = R['profile'][X][k], R['profile'][X][k + 1]
        if rows[k].get('uv'):
            f = (zb - za - drop) / (zb - za)
            rows[k]['uv'] = [[u[0], u[1] * f, u[2]] for u in rows[k]['uv']]
        profile[X], strips[X] = corners, rows
    splits = {X: [s - drop if s >= cut['hi'] - 1e-9 else s for s in R['splits'][X]] for X in 'AB'}
    return dict(R, top=R['top'] - drop, profile=profile, strips=strips, splits=splits)


# ---------------------------------------------------------------------------------------------------- the free form
def measured(R):
    """Whether `R` is a measured look's recipe (wall_measure.py's, or as_measured's): frac_wall.general's test."""
    return R.get('measure') is not None


def as_measured(R):
    """The Bar look's recipe (wall_looks.json: a symmetric `section` of [y, z, the trim set's v] corners, its faces'
    and trims' repeats) written as a measured look's: the same outline on both sides; a face on the main plane in the
    side's two face slots split at the storey, its texture u = x / faceRepeat + faceU (side B: -x), v = faceV - z /
    faceRepeat; every other segment a trim strip, u = -x / trimRepeat - trimU (side B: both signs turned), v the
    section's v up it; the top and bottom the trim slot's, u = -x / trimRepeat, v = topV (bottomV) across. `measure` 0:
    made here, by no measurer."""
    half, sec = float(R['half']), R['section']
    corners = [[float(y), float(z)] for y, z, _ in sec]
    trim, rep, trep = R['slots']['trim'], float(R['faceRepeat']), float(R['trimRepeat'])

    def strips(side):
        out = []
        for (ya, za, va), (yb, zb, vb) in zip(sec, sec[1:]):
            if abs(ya - half) < EPS and abs(yb - half) < EPS and zb > za:
                out.append(dict(slot=None, face=True, uv=None))
            else:
                out.append(dict(slot=trim, face=False, uv=[[-side / trep, 0.0, -side * float(R['trimU'])],
                                                           [0.0, float(vb) - float(va), float(va)]]))
        return out
    face_uv = {}
    for slot in R['slots']['sideA']:
        face_uv['%dA' % slot] = [[1.0 / rep, 0.0, float(R['faceU'])], [0.0, -1.0 / rep, float(R['faceV'][0])]]
    for slot in R['slots']['sideB']:
        face_uv['%dB' % slot] = [[-1.0 / rep, 0.0, float(R['faceU'])], [0.0, -1.0 / rep, float(R['faceV'][1])]]
    caps = {key: dict(slot=trim, uv=[[-1.0 / trep, 0.0, 0.0], [0.0, float(R[v][1]), float(R[v][0])]])
            for key, v in (('top', 'topV'), ('bottom', 'bottomV'))}
    ch = float(R['collisionHalf'])
    return dict(measure=0, donor=R['donor'], bottom=float(R['bottom']), top=float(R['top']), half=half,
                endInset=float(R['endInset']), profile=dict(A=corners, B=[list(c) for c in corners]),
                strips=dict(A=strips(1), B=strips(-1)),
                slots=dict(sideA=list(R['slots']['sideA']), sideB=list(R['slots']['sideB']),
                           interior=R['slots']['interior']),
                splits=dict(A=[float(R['storey'])], B=[float(R['storey'])]), faceUV=dict(sorted(face_uv.items())),
                caps=caps, colours=dict(R['colours']), cell=[float(v) for v in R['cell']], jitter=float(R['jitter']),
                collisionHalf=ch, collisionY=[-ch, ch], lightmap=dict(R['lightmap']), sections=6, storeys=2,
                storey=float(R['storey']))


def thickened(R, y0, y1):
    """The measured look `R` with its faces at y0 (side B, facing -y) and y1 (side A): each side's corners moved as
    far as its face, so its trims stand as proud of it as they did; its collision across moved with the faces; `half`
    the faces' half distance. ValueError when the outline would cross itself (thinner than THINNEST anywhere: a look
    whose trims stand in from its faces, made thinner than they reach): a free_form.NumbersError, code 'thickness'."""
    half = float(R['half'])
    da, db = float(y1) - half, -float(y0) - half
    if abs(da) < 1e-12 and abs(db) < 1e-12:
        return R
    profile = dict(A=[[y + da, z] for y, z in R['profile']['A']], B=[[y + db, z] for y, z in R['profile']['B']])
    cy = R.get('collisionY') or [-R['collisionHalf'], R['collisionHalf']]
    lo, hi = float(cy[0]) - db, float(cy[1]) + da
    out = dict(R, profile=profile, half=(float(y1) - float(y0)) / 2, collisionY=[lo, hi], collisionHalf=(hi - lo) / 2)
    least, at = thinnest(out)
    if least < THINNEST:
        raise NumbersError('thickness', "a wall's faces %g..%g leave its look's outline %g thick at %g over its floor "
                           "(its trims reach in from its faces; it keeps %g at least)" % (y0, y1, least, at, THINNEST))
    if hi - lo < THINNEST:
        raise NumbersError('thickness', "a wall's faces %g..%g leave its look's collision %g thick" % (y0, y1, hi - lo))
    return out


def width_at(corners, z, above):
    """A side's y at height z (its corners [y, z] bottom to top): at a ledge's height, the y above it (`above`) or
    under it; past the ends, the end's."""
    at = [k for k, (_, cz) in enumerate(corners) if abs(cz - z) < 1e-9]
    if at:
        return corners[at[-1]][0] if above else corners[at[0]][0]
    for (ya, za), (yb, zb) in zip(corners, corners[1:]):
        if za < z < zb:
            return ya + (z - za) * (yb - ya) / (zb - za)
    return corners[0][0] if z <= corners[0][1] else corners[-1][0]


def thinnest(R):
    """(the least thickness of the outline, the height it is at): both sides' y added, at every corner's height (the
    sides are straight between them, so the least is at one), above and under a ledge."""
    A, B = R['profile']['A'], R['profile']['B']
    best = None
    for z in sorted({z for _, z in A} | {z for _, z in B}):
        for above in (False, True):
            t = width_at(A, z, above) + width_at(B, z, above)
            if best is None or t < best[0]:
                best = (t, z)
    return best


def shifted(R, s):
    """The measured look `R` raised `s`: every corner, split, the bottom and the top; its faces' textures read where
    they were (`uvShiftZ` lower by s), so the pattern rises with it."""
    if not s:
        return R
    profile = {X: [[y, z + s] for y, z in R['profile'][X]] for X in 'AB'}
    splits = {X: [v + s for v in R['splits'][X]] for X in 'AB'}
    return dict(R, profile=profile, splits=splits, bottom=R['bottom'] + s, top=R['top'] + s,
                uvShiftZ=float(R.get('uvShiftZ', 0.0)) - s)


def proportional(R, z1):
    """The measured look `R` (its bottom where it stays) with every height scaled so its top is z1: the fallback where
    no upright stretch takes the change (heightened). Its strips' textures stretch with them."""
    z0, f = float(R['bottom']), (z1 - float(R['bottom'])) / (float(R['top']) - float(R['bottom']))
    profile = {X: [[y, z0 + (z - z0) * f] for y, z in R['profile'][X]] for X in 'AB'}
    splits = {X: [z0 + (v - z0) * f for v in R['splits'][X]] for X in 'AB'}
    return dict(R, profile=profile, splits=splits, top=float(z1))


def heightened(R, z0, z1):
    """The measured look `R` standing from z0 to z1 (the module's docstring): raised to z0, then the height it lacks
    put into, or what it has too much taken out of, its longest stretch upright on both sides (storey_cut, lowered),
    else every height scaled (proportional)."""
    R = shifted(R, float(z0) - float(R['bottom']))
    change = (float(z1) - float(z0)) - (float(R['top']) - float(R['bottom']))
    if abs(change) < 1e-9:
        return R
    cut = storey_cut(R, -change)
    R = lowered(R, cut, -change) if cut is not None else proportional(R, float(z1))
    # (the top exactly z1: the corners there moved or scaled to it within rounding)
    top = float(R['top'])
    profile = {X: [[y, float(z1) if abs(z - top) < 1e-7 else z] for y, z in R['profile'][X]] for X in 'AB'}
    return dict(R, profile=profile, top=float(z1))


def windowed(R, lo, hi):
    """The measured look `R` between heights lo and hi (a band of a tall stretched wall): each side's outline from lo
    to hi (a corner put in where each crosses them; at a ledge's height, the outline above it at lo and under it at
    hi), its strips' textures going on as they did on the whole (each cut strip's texture up it re-read over its new
    length), the splits between, the bottom lo and the top hi."""
    bottom, top = float(R['bottom']), float(R['top'])
    if lo <= bottom + 1e-9 and hi >= top - 1e-9:
        return R
    profile, strips = {}, {}
    for X in 'AB':
        c, rows = R['profile'][X], R['strips'][X]
        segs = [k for k in range(len(c) - 1) if c[k + 1][1] > c[k][1]]
        first = next((k for k in segs if c[k][1] <= lo + 1e-9 and lo < c[k + 1][1] - 1e-9), segs[0])
        last = next((k for k in reversed(segs) if c[k][1] + 1e-9 < hi and hi <= c[k + 1][1] + 1e-9), segs[-1])

        def at(k, z):
            (ya, za), (yb, zb) = c[k], c[k + 1]
            return [ya + (z - za) * (yb - ya) / (zb - za), z]
        corners = [at(first, max(lo, c[first][1]))] + [list(p) for p in c[first + 1:last + 1]] + [at(last, min(hi, c[last + 1][1]))]
        kept = []
        for k in range(first, last + 1):
            row = dict(rows[k])
            za, zb = c[k][1], c[k + 1][1]
            na, nb = (max(za, lo), min(zb, hi)) if zb > za else (za, zb)
            if row.get('uv') and zb > za and (na, nb) != (za, zb):
                # t on the whole strip = (na - za + t' (nb - na)) / (zb - za)
                f, g = (nb - na) / (zb - za), (na - za) / (zb - za)
                row['uv'] = [[u[0], u[1] * f, u[2] + u[1] * g] for u in row['uv']]
            kept.append(row)
        profile[X], strips[X] = corners, kept
    splits = {X: [v for v in R['splits'][X] if lo + 1e-9 < v < hi - 1e-9] for X in 'AB'}
    return dict(R, profile=profile, strips=strips, splits=splits, bottom=float(lo), top=float(hi))


def free_shape(R, y0, y1, z0, z1, band=None):
    """The free form's shape of a wall in the look of recipe `R` (the module's docstring): its faces at y0 and y1, its
    bottom and top at z0 and z1, and a band [lo, hi] of it when given."""
    if not measured(R):
        R = as_measured(R)
    R = thickened(R, y0, y1)
    R = heightened(R, z0, z1)
    if band is not None:
        R = windowed(R, float(band[0]), float(band[1]))
    return R
