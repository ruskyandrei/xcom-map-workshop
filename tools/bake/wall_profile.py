"""A made wall's outline across its thickness, as frac_wall.py's general path builds it (a measured look's recipe:
its `profile`, `strips`, `splits` and heights; frac_wall.py's block "any look" says what each holds): the height a
storey less takes out of it."""

STOREY_HEIGHT = 192.0           # the game's storey: what a storey less takes out of a measured look
RUN_LEFT = 8.0                  # what a storey's cut leaves of the straight run it is taken out of, at least


def storey_cut(R, drop):
    """Where a measured look loses `drop` of height (a storey less): the top `drop` of the longest stretch upright on
    both sides at once, each in one segment, when it leaves RUN_LEFT of that stretch: dict(lo, hi, segments {side: k}),
    or None."""
    runs = {X: [(za, zb, k) for k, ((ya, za), (yb, zb)) in enumerate(zip(R['profile'][X], R['profile'][X][1:]))
                if abs(ya - yb) < 1e-6 and zb > za] for X in 'AB'}
    best = None
    for a0, a1, ka in runs['A']:
        for b0, b1, kb in runs['B']:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo >= drop + RUN_LEFT and (best is None or (hi - lo, hi) > best[0]):
                best = ((hi - lo, hi), dict(lo=hi - drop, hi=hi, segments=dict(A=ka, B=kb)))
    return best[1] if best else None


def lowered(R, cut, drop):
    """The measured look `R` with `drop` taken out at `cut` (storey_cut's): every corner from the cut's top up `drop`
    lower, the segments that held the cut shorter (their texture up them kept to the unit, as before), the splits above
    lower; the caps' and the faces' textures as they were."""
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
