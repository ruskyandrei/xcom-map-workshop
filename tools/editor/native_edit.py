"""The native edit: the contract between the compiler and the Build.

native_split(spec) takes the compiler's spec (compiler.compile_project) apart into what a patch would still do and
the native edit, the lanes the Build's copy tool (tools/bake/native_copy.py) makes in the variant map itself; what is
left for a patch is nothing for every project the compiler accepts today. It is a function of the spec alone.
NATIVE_CLASSES are the classes whose copies it puts in the map; the compiler reads them too (a component offset from
its actor is no matter for a copy made in the map).

It was moved out of compiler.py (review finding 23). The compiler names both again (compiler.native_split,
compiler.NATIVE_CLASSES), and what reads them reads them there: the Build (build.py), the tests, the examples'
generators, and the compile recorder (tests/compile_record.py), which records every native_split through
compiler.native_split. A new lane of the native edit is added in one change to the compiler's spec, native_split, the
copy tool and the Build (ARCHITECTURE.md).
"""
# Copies the editor's Build makes as new actors of the variant map (tools/bake/native_copy.py, baker step L4): every
# M1 class, linked in the map when they break together. A collectible's copy is a collectible, so it counts as
# mission loot as its original does (the copier's copy, XComMapEdDestructible, would not). The Build also takes the
# hidden pieces out of the map itself, so an M1 edit needs no patch. Fracturing pieces and physics props are made there
# too (9 November 2026): the copier has no recipe for either on its own.
NATIVE_CLASSES = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComCollectible',
                  'XComFracLevelActor', 'XComDecoFracLevelActor', 'KAsset')


def native_split(spec):
    """(patch spec, native edit): the spec without what the Build does in the variant map itself, and that as
    tools/bake/native_copy.py takes it: `copies` (actor, location, rotation, label, box, and breakGroup when the copy
    breaks with a group) of NATIVE_CLASSES, `breakOriginals` (the base map's pieces left in place that break with
    those groups, {name, group}) and `hides` (the exact hider's targets, {name, label, box}). A copy of an assembly
    (a car, a door, a ladder: always made in the map) also carries its `family` and `assembly`, and `assemblies` lists
    each assembly's grid move ({id, family, members, turns, translation}), `covers` the cover blocks (the spec's
    `covers` blocks: name, kind, location, rotation, size, heights, box, and breakGroup for a block that breaks with
    a group; the spec's `breakOriginals` object carries such a group's map pieces when the project has no copy), `buildings` the buildings made from nothing
    (id, name, kind, floors of boxes), `buildingEdits` the map's own buildings changed or deleted (id, actor, name, kind,
    deleted, moved, floors of boxes and volumes, old: each floor's volumes and their boxes as exported); a ladder copy
    carries its `ladder` ends
    ({foot, top} tiles), and `streamHides` ({stream: [actor]}) the streamed patches' pieces to take out of the
    variant's copies of them (a moved or deleted ladder's helpers), `lights` the light edits (plan 9.5: deletes,
    changes, adds and the area lights the piece edits take along), and `effects`, `sounds` and `flares` the effects',
    sounds' and lens flares' lanes (each `moves`, `deletes`, `copies` and `values`; the effects and sounds plan, Part D),
    and `backgroundSound` the map's background sound ({op, cue, volume?, donor?}: tools/bake/native_sounds.py), and
    `diagonalCover` the diagonal cover the project marks ({marks [{at, toward}], removed [at]}: tools/bake/native_copy.py
    diagonal_edit). A group with a copy of another class stays
    the copier's whole, with its base-map pieces. What is left for the patch, if anything, is built by patchtool; with
    nothing left the Build makes no patch."""
    out, natives, originals, hides, moves = dict(spec, objects=[]), [], [], [], []
    lights, covers, buildings, edits, piece_flags_, flag_ladders, piece_blasts = None, [], [], [], [], [], []
    effect_lanes = {}
    stream_hides = out.pop('streamHides', None)
    stream_moves = out.pop('streamMoves', None)
    cleared, zones = out.pop('cleared', None), out.pop('landingZones', None)
    spawn_rules = out.pop('spawnRules', None)
    carried = out.pop('carriedEffects', None)
    sound = out.pop('backgroundSound', None)
    diagonal = out.pop('diagonalCover', None)
    for obj in spec['objects']:
        if obj.get('type') == 'buildings':
            buildings += obj['buildings']
            continue
        if obj.get('type') == 'buildingEdits':
            edits += obj['edits']
            continue
        if obj.get('type') == 'covers':
            covers += obj['blocks']
            continue
        if obj.get('type') == 'pieceFlags':
            piece_flags_ += obj['pieces']
            flag_ladders += obj.get('ladders') or []
            continue
        if obj.get('type') == 'pieceBlasts':
            piece_blasts += [dict(name=e['name'], blasts=e['blasts'], **({'breaksFurther': True} if e.get('breaksFurther') else {}))
                             for e in obj['pieces']]
            continue
        if obj.get('type') == 'breakOriginals':
            originals += obj['originals']
            continue
        if obj.get('type') == 'lights':
            lights = {k: obj[k] for k in ('deletes', 'changes', 'adds', 'area')}
            continue
        if obj.get('type') in ('effects', 'sounds', 'flares', 'spawns'):
            effect_lanes[obj['type']] = {k: obj.get(k) or [] for k in ('moves', 'deletes', 'copies', 'values')}
            continue
        if obj.get('type') == 'hide' and obj.get('exact'):
            boxes = obj.get('boxes') or [None] * len(obj['alsoHide'])
            labels = obj.get('labels') or obj['alsoHide']
            hides += [dict(name=n, label=l, box=b) for n, l, b in zip(obj['alsoHide'], labels, boxes)]
            continue
        if obj.get('type') != 'copy':
            out['objects'].append(obj)
            continue
        n = len(obj['from'])
        classes = obj.get('classes') or [None] * n
        groups = obj.get('breakGroups') or [0] * n
        walls = obj.get('wallGroups') or [0] * n
        walled = {w for w in walls if w}
        members = obj.get('assemblies') or [''] * n
        families = obj.get('families') or [''] * n
        donors = obj.get('donors') or [None] * n
        untried = obj.get('untried') or [False] * n
        flags = obj.get('flags') or [None] * n
        generated = obj.get('generated') or [None] * n
        blasts = obj.get('blasts') or [None] * n
        further = obj.get('breaksFurther') or [False] * n
        # a piece of another map is always made in the map: nothing else can bring what it needs; so is a copy of a
        # class the Build has not been tried on (the patch's copier has no recipe for it either)
        # (and a copy with flags: only the writer sets them)
        # (and the pieces of a group that breaks with a made wall: the wall's columns list them in the map)
        # (and a broken copy of one of the map's fracturing pieces: only the writer paints its fragments out, E6)
        in_map = [classes[k] in NATIVE_CLASSES or bool(members[k]) or bool(donors[k]) or untried[k] or bool(flags[k])
                  or bool(generated[k]) or bool(blasts[k]) or groups[k] in walled for k in range(n)]
        copier_groups = {groups[k] for k in range(n) if groups[k] and not in_map[k]}
        native = [k for k in range(n) if in_map[k] and groups[k] not in copier_groups]
        for k in native:
            natives.append(dict(actor=obj['from'][k], location=obj['poses'][k]['location'],
                                rotation=obj['poses'][k]['rotation'], label=obj['labels'][k], box=obj['boxes'][k],
                                **({'breakGroup': groups[k]} if groups[k] else {}),
                                **({'wallGroup': walls[k]} if walls[k] else {}),
                                **({'donor': donors[k]} if donors[k] else {}),
                                **({'untried': True} if untried[k] else {}),
                                **({'flags': flags[k]} if flags[k] else {}),
                                **({'generated': generated[k]} if generated[k] else {}),
                                **({'blasts': blasts[k]} if blasts[k] else {}),
                                **({'breaksFurther': True} if further[k] else {}),
                                **({'family': families[k], 'assembly': members[k]} if members[k] else {}),
                                **({'ladder': obj['ladders'][k]} if (obj.get('ladders') or [None] * n)[k] else {})))
        made = {members[k] for k in native if members[k]}
        moves += [m for m in obj.get('assemblyMoves') or [] if m['id'] in made]
        stay = [o for o in obj.get('breakOriginals') or [] if o['group'] in copier_groups]
        originals += [o for o in obj.get('breakOriginals') or [] if o['group'] not in copier_groups]
        keep = [k for k in range(n) if k not in native]
        if keep:
            rest = dict(obj)
            for f in ('from', 'poses', 'labels', 'boxes', 'classes', 'breakGroups', 'wallGroups', 'families', 'assemblies',
                      'ladders', 'donors', 'untried', 'flags', 'generated', 'blasts', 'breaksFurther'):
                if f in obj:
                    rest[f] = [obj[f][k] for k in keep]
            rest.pop('assemblyMoves', None)
            if 'breakOriginals' in obj:
                rest['breakOriginals'] = stay
                if not stay:
                    del rest['breakOriginals']
            rest['location'] = rest['poses'][0]['location']
            out['objects'].append(rest)
    native = dict(copies=natives, breakOriginals=originals, hides=hides)
    if lights:
        native['lights'] = lights
    if covers:
        native['covers'] = covers
    if piece_flags_:
        native['pieceFlags'] = piece_flags_
        if flag_ladders:
            native['pieceFlagLadders'] = flag_ladders
    if piece_blasts:
        native['pieceBlasts'] = piece_blasts
    if buildings:
        native['buildings'] = buildings
    if edits:
        native['buildingEdits'] = edits
    if moves:
        native['assemblies'] = moves
    if stream_hides:
        native['streamHides'] = stream_hides
    if stream_moves:
        native['streamMoves'] = stream_moves
    if cleared:
        native['cleared'] = cleared
    if zones is not None:
        native['landingZones'] = zones
    if spawn_rules:
        native['spawnRules'] = spawn_rules
    if carried:
        native['carriedEffects'] = carried
    if sound:
        native['backgroundSound'] = sound
    if diagonal:
        native['diagonalCover'] = diagonal
    native.update(effect_lanes)
    return out, native
