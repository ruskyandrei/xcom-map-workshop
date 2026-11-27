"""The map's placed lights edited in a project, and the generated area lights its glowing pieces take along (the
editor lights plan, L6: plan 4.2, 4.8 and 9.5), for the compiler.

An original placed light moved, turned, changed, switched off or deleted (light_override), a copy of one or a light
made from a built-in recipe (light_add); and the generated area lights a moved, copied or deleted glowing piece takes
along (derive_area_lights, from the piece edits the compiler records in `owner_edits`; copy_area_light for a piece of
another map, whose donor's area lights the compiler reads), each owner found from the export's association or the
project's areaLightBindings (area_bindings). light_rule says which lights may be edited. Each edit checked goes into
`ops`, the spec's `lights` object, which compiler.native_split hands to the Build's writer
(tools/bake/native_lights.py), and into the report's entities, with what its radius reaches (reaching, reach_box).
`members` holds the group member keys of the lights the project adds.

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A LightEdits works for one
Compiler: it reads the map, the scene, the export's lights and pieces by key (lights, actors) and the document from
it, asks it whether a family builds (builds) and for a pose (pose) and a piece's boxes (boxes), and says what it finds
through its error, leave_out, warn and note, so the report and the pieces left out are the compiler's as before.

Its own tables and helpers (LIGHT_KEYS, LIGHT_RANGES, LIGHT_RECIPES, light_rule, rotator_of and the others) are here,
and the compiler names again those that others read through it (compiler.LIGHT_RECIPES, compiler.light_rule, ...).
What the family shares with the compiler (FAMILIES, EPS_LOCATION, short, tidy, world_box and the others it imports)
it takes from compiler_tables, so it never imports the compiler. The export check that every project with edits needs
(light_metadata_problem, LIGHT_METADATA) is the compiler's.

The project's `sun` (schema 10; the game-likeness plan's T-S1: the time of day, the map's sun or moon and sky light) is
this family's too (sun_mark). It is read for its shape alone for now (tools/viewer/sun_curve.py `problem`): the Build's
lane for it is stage T-S2's, so a project with one builds and the map keeps its own sun, sky light and time of day,
said in a note.
"""
import math

# (compiler_tables puts tools/viewer on the path, for export_math and, in submitted_light, lights)
from compiler_tables import EPS_LOCATION, FAMILIES, game_round, keyable, short, target_key, tidy, world_box
from export_math import multiply, transform

# The light values an edit may set (plan 9.1), with their ranges (plan 4.2); the cone angles are spot lights' only.
LIGHT_KEYS = ('color', 'brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled')
CONE_KEYS = ('innerConeAngle', 'outerConeAngle')
LIGHT_RANGES = dict(brightness=(0.0, 100.0), radius=(1.0, 16384.0), falloffExponent=(0.1, 64.0),
                    innerConeAngle=(0.0, 89.0), outerConeAngle=(0.0, 89.99))
# The built-in recipes for lights a map has no template for (plan 3.3, 4.9): kind -> version -> starting values.
# (a point light's, light_factory.POINT_RECIPES, are for prefabs: a prefab's lights are recipe lights, so they need
# no map; prefab plan 5.5. A point light has no cones.)
LIGHT_RECIPES = {'spot': {1: dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0,
                                  innerConeAngle=0.0, outerConeAngle=44.0, enabled=True)},
                 'point': {1: dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0, enabled=True)}}
RECIPE_ACTOR = {'spot': 'SpotLight', 'point': 'PointLight'}
RECIPE_ROTATION = {'spot': [-16384, 0, 0],      # pointing down, as a placed SpotLight's class default
                   'point': [0, 0, 0]}
# An unresolved area light this near an edited piece's old box (units) is named in a warning (plan 4.8)
AREA_NEAR = 64.0


def light_rule(light):
    """None for a light an edit may change, else why it is view only (plan 3.2). The page shows the same verdicts
    (families.json `lightRules`)."""
    role, kind = light.get('role'), light.get('kind')
    if light.get('layer') != 'base':
        return "it is a light of a streamed level (a patch's own)"
    if role == 'area':
        return 'it was made by the bake for a glowing surface: it follows its glowing piece'
    if role == 'toggleable':
        who = ', '.join(light.get('referencedBy') or []) or 'a destructible'
        return 'it is lit live and switched by %s; moving it means relighting its shadow maps (a later step)' % who
    if role in ('dominant', 'sky') or kind in ('directional', 'sky'):
        return 'it is the sun, moon or sky: these come with the time of day, a later step'
    if role != 'static' or kind not in ('point', 'spot'):
        return 'it is not a placed point or spot light'
    if 'lightmapGuid' not in light or 'bakedInto' not in light:
        return 'the export lacks its light data (export 18)'
    if light.get('referencedBy'):
        return "it is named by the map's Kismet (%s)" % '; '.join(light['referencedBy'])
    if light.get('channels'):
        return 'it lights only the lighting channels it picks'
    if not light.get('bakedInto'):
        return 'it is in no lightmap: the bake never used it'
    return None


def light_values(light):
    """A light record's editable values in the package's terms (plan 9.1): colour bytes, not the export's 0-1."""
    out = dict(color=[int(round(v * 255)) for v in (light.get('color') or [1, 1, 1])[:3]],
               brightness=light.get('brightness'), enabled=bool(light.get('enabled')))
    if light.get('kind') in ('point', 'spot'):
        out.update(radius=light.get('radius'), falloffExponent=light.get('falloffExponent'))
    if light.get('kind') == 'spot':
        out.update(innerConeAngle=light.get('innerConeAngle'), outerConeAngle=light.get('outerConeAngle'))
    return out


def light_value_problem(key, value):
    """Why a submitted light value is out of its range (plan 4.2), or None."""
    if key == 'color':
        if not (isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) and not isinstance(v, bool)
                                                                      and 0 <= v <= 255 for v in value)):
            return 'color must be three whole numbers 0 to 255'
        return None
    if key == 'enabled':
        return None if isinstance(value, bool) else 'enabled must be true or false'
    lo, hi = LIGHT_RANGES[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return '%s must be a number' % key
    if not lo <= value <= hi:
        return '%s must be %g to %g' % (key, lo, hi)
    return None


def reach_box(location, radius):
    return [tidy(v, 3) for c in location for v in (c - radius, c + radius)]


def rotator_of(m):
    """The rotator [pitch, yaw, roll] (whole units, -32768..32767) of a 4 x 4 transform's rotation (export_math's
    convention: its columns are the rotator's X, Y and Z axes)."""
    x = [m[i][0] for i in range(3)]
    pitch = math.atan2(x[2], math.hypot(x[0], x[1]))
    yaw = math.atan2(x[1], x[0])
    roll = math.atan2(-m[2][1], m[2][2])
    unit = lambda a: int(game_round(a * 32768 / math.pi)) % 65536  # noqa: E731
    return [(v + 32768) % 65536 - 32768 for v in (unit(pitch), unit(yaw), unit(roll))]


def moved_light_pose(location, rotation, move):
    """A light's pose carried by a rigid move (rigid_move: the owner's before to after): lightAfter = M · lightBefore.
    A move that only turns about Z adds its turn to the light's yaw, keeping its stored rotator exactly otherwise."""
    loc = [tidy(sum(move[i][k] * location[k] for k in range(3)) + move[i][3]) for i in range(3)]
    if all(abs(move[i][2] - (1.0 if i == 2 else 0.0)) < 1e-9 for i in range(3)):
        dyaw = game_round(math.atan2(move[1][0], move[0][0]) * 32768 / math.pi)
        return loc, [int(rotation[0]), int(rotation[1]) + int(dyaw), int(rotation[2])]
    return loc, rotator_of(multiply(move, transform([0, 0, 0], rotation, [1, 1, 1])))


class LightEdits:
    def __init__(self, compiler):
        self.c = compiler
        # light edits (plan 9.5): the spec's `lights` object, and what each piece edit does to the area lights (the
        # compiler's override and add record each piece edit here; derive_area_lights reads them)
        self.ops = dict(deletes=[], changes=[], adds=[], area=[])
        self.owner_edits = []    # (kind, owner actor path, owner entity, rigid move or None, where)
        self.members = set()     # the group member keys of the lights the project adds
        self.object_boxes = None     # the base map's pieces' world boxes, made when reaching first needs them

    def sun_mark(self):
        """The project's `sun` (the time of day) read for its shape: one this compiler can't read is left out
        (sun-shape); one it reads is noted (sun-not-built), since no Build writes it yet (stage T-S2 makes its lane)."""
        rec = self.c.doc.get('sun')
        if rec is None:
            return
        import sun_curve
        why = sun_curve.problem(rec)
        if why:
            self.c.leave_out('sun-shape', "The project's time of day can't be read (%s): it is left out, and the map "
                             'keeps its own sun, sky light and time of day.' % why, record='sun')
            return
        self.c.note('sun-not-built', 'The project sets the time of day (%s): the editor shows it, and the Build does not '
                    'write it into the map yet, so the map keeps its own sun, sky light and time of day.'
                    % ('%02d:%02d' % divmod(round(rec['time'] * 60) % 1440, 60)), record='sun')

    def light_of(self, target):
        """The export's light a target {package, level, actor} names, or None."""
        key = target_key(target)
        return self.c.lights.get(key) if key else None

    def light_gate(self, name, where):
        """The family's refusal while it doesn't build (plan 3.4): True when the edit may go on."""
        if self.c.builds('light'):
            return True
        self.c.error('family', '%s is a light edit. %s' % (name, FAMILIES['light']['note']), family='light', **where)
        return False

    def submitted_light(self, values, kind, where, name):
        """The submitted light values `values` checked (plan 4.2): dict, or None with an error."""
        if not isinstance(values, dict):
            self.c.error('malformed', '%s: "light" must be an object of light values' % name, **where)
            return None
        bad = sorted(set(values) - set(LIGHT_KEYS))
        if bad:
            self.c.error('malformed', '%s: %s %s not a light value (they are %s)' % (
                name, ', '.join(bad), 'is' if len(bad) == 1 else 'are', ', '.join(LIGHT_KEYS)), **where)
            return None
        if kind != 'spot' and set(values) & set(CONE_KEYS):
            self.c.error('light-value', '%s is a %s light, which has no cone' % (name, kind), **where)
            return None
        values = dict(values)
        for key in sorted(values):
            why = light_value_problem(key, values[key])
            value = values[key]
            if why and key in LIGHT_RANGES and isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and math.isfinite(value) and key not in CONE_KEYS:
                # a number outside its range: built at the nearest value in range, and said (plan R3)
                lo, hi = LIGHT_RANGES[key]
                values[key] = min(max(value, lo), hi)
                self.c.note('light-clamped', '%s: its %s is %g, outside %g to %g; built as %g'
                          % (name, key, value, lo, hi, values[key]), key=key, stored=value, built=values[key], **where)
            elif why and key in CONE_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and math.isfinite(value):
                continue        # (the two cone angles are taken together, below)
            elif why:
                self.c.error('light-value', '%s: %s' % (name, why), key=key, **where)
                return None
        cone = [values.get(k) for k in CONE_KEYS]
        if any(k in values and light_value_problem(k, values[k]) for k in CONE_KEYS):
            # a cone out of range lights as its effective cone (a map's stored 100 lights as 89.99): built as that
            from lights import storable_cone
            inner, outer = cone
            if inner is None or outer is None:
                key = CONE_KEYS[0 if inner is not None else 1]
                lo, hi = LIGHT_RANGES[key]
                built = {key: min(max(values[key], lo), hi)}
            else:
                built = dict(zip(CONE_KEYS, storable_cone(inner, outer)))
            for key, value in built.items():
                if value != values[key]:
                    self.c.note('light-clamped', '%s: its %s is %g, outside %g to %g; built as %g'
                              % (name, key, values[key], *LIGHT_RANGES[key], value), key=key, stored=values[key],
                              built=value, **where)
                values[key] = value
        return values

    def light_after(self, name, kind, before, submitted, where):
        """Every raw value after the edit, the inherited ones as stored (a stored 580-degree cone stays 580): dict, or
        None with an error when an inherited value is malformed or an edited cone's inner is wider than its outer."""
        after = dict(before, **submitted)
        for key in LIGHT_KEYS:
            if key not in after or key in submitted:
                continue
            value = after[key]
            if key == 'color':
                ok = isinstance(value, list) and len(value) == 3
            elif key == 'enabled':
                ok = isinstance(value, bool)
            else:
                ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            if not ok:
                self.c.error('light-value', '%s: its stored %s (%r) is not a value the Build can keep' % (name, key, value),
                           key=key, **where)
                return None
        if kind == 'spot' and set(submitted) & set(CONE_KEYS) and after['innerConeAngle'] > after['outerConeAngle']:
            self.c.note('light-clamped', '%s: its inner cone (%g) is wider than its outer cone (%g); built with the inner '
                      'cone at %g' % (name, after['innerConeAngle'], after['outerConeAngle'], after['outerConeAngle']),
                      key='innerConeAngle', stored=after['innerConeAngle'], built=after['outerConeAngle'], **where)
            after['innerConeAngle'] = after['outerConeAngle']
            submitted['innerConeAngle'] = after['innerConeAngle']
        return after

    def light_override(self, target, rec, where, light):
        """An original light moved, turned, changed, switched off or deleted (plan 4.2)."""
        name = short(target['actor'])
        for f in sorted(set(rec) - {'target', 'location', 'rotation', 'deleted', 'light'}):
            self.c.note('unknown-field', 'field %r is not part of an override and is ignored' % f, **where)
        if target['package'].casefold() != self.c.map.casefold():
            self.c.error('level', '%s is a light of %s, not of %s' % (name, target['package'], self.c.map), **where)
            return
        why = light_rule(light)
        if why:
            self.c.error('light-view-only', '%s is view only: %s' % (name, why), **where)
            return
        before = light_values(light)
        kind = light['kind']
        if rec.get('deleted') is True:
            if not self.light_gate(name, where):
                return
            self.ops['deletes'].append(dict(name=name, label='delete:' + name, kind=kind, role=light['role'],
                                                  reach=reach_box(light['location'], light['radius'])))
            self.c.entities.append(dict(kind='light', op='delete', target=target['actor'], lightClass=light['actorClass'],
                                      bakedInto=len(light.get('bakedInto') or [])))
            return
        if not {'location', 'rotation', 'light'} & set(rec):
            self.c.error('malformed', 'a light override is deleted, or gives a pose or light values', **where)
            return
        p = self.c.pose(dict(location=rec.get('location', light['location']),
                           rotation=rec.get('rotation', light['rotation'])), where)
        if not p:
            return
        loc, rot, rounding = p
        submitted = self.submitted_light(rec.get('light', {}), kind, where, name)
        if submitted is None:
            return
        after = self.light_after(name, kind, before, submitted, where)
        if after is None:
            return
        changed = {k: v for k, v in submitted.items() if v != before.get(k)}
        moved = not (all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, light['location']))
                     and rot == [int(v) for v in light['rotation']])
        if not changed and not moved:
            self.c.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)
            return
        if not self.light_gate(name, where):
            return
        entry = dict(name=name, label='change:' + name, kind=kind, role=light['role'], location=loc, rotation=rot,
                     set=changed, light=after,
                     before=dict(before, location=list(light['location']), rotation=[int(v) for v in light['rotation']]),
                     reach=dict(before=reach_box(light['location'], before['radius']),
                                after=reach_box(loc, after['radius'])))
        self.ops['changes'].append(entry)
        self.c.entities.append(dict(kind='light', op='change', target=target['actor'], lightClass=light['actorClass'],
                                  location=loc, rotation=rot, rotationRounding=tidy(rounding, 6), set=sorted(changed),
                                  bakedInto=len(light.get('bakedInto') or []),
                                  reaches=self.reaching(loc, after)))

    def light_add(self, rec, where):
        """A copy of an original light, or a spot light made from the built-in recipe (plan 3.3, 4.9)."""
        out = rec['actor']
        name = short(out)
        template = rec.get('template')
        if template is not None:
            if 'from' in rec or 'components' in rec:
                self.c.error('malformed', '%s is both a copy (from) and a recipe light (template)' % name, **where)
                return
            kind, version = (template.get('kind'), template.get('version')) if isinstance(template, dict) else (None, None)
            if not (keyable(kind) and keyable(version)) or kind not in LIGHT_RECIPES or version not in LIGHT_RECIPES[kind]:
                self.c.error('light-recipe', '%s is made from a recipe this compiler doesn\'t know (%r); its versions are %s'
                           % (name, template, {k: sorted(v) for k, v in LIGHT_RECIPES.items()}), **where)
                return
            values = rec.get('light')
            wanted = [k for k in LIGHT_KEYS if k in LIGHT_RECIPES[kind][version]]
            if not isinstance(values, dict) or set(values) != set(wanted):
                self.c.error('malformed', '%s: a recipe light carries every light value (%s)' % (name, ', '.join(wanted)),
                           **where)
                return
            submitted = self.submitted_light(values, kind, where, name)
            if submitted is None:
                return
            if kind == 'spot' and submitted['innerConeAngle'] > submitted['outerConeAngle']:
                self.c.note('light-clamped', '%s: its inner cone (%g) is wider than its outer cone (%g); built with the '
                          'inner cone at %g' % (name, submitted['innerConeAngle'], submitted['outerConeAngle'],
                                                submitted['outerConeAngle']), key='innerConeAngle',
                          stored=submitted['innerConeAngle'], built=submitted['outerConeAngle'], **where)
                submitted['innerConeAngle'] = submitted['outerConeAngle']
            p = self.c.pose(dict(location=rec.get('location'), rotation=rec.get('rotation', RECIPE_ROTATION[kind])), where)
            if not p or not self.light_gate(name, where):
                return
            loc, rot, rounding = p
            source = dict(template=dict(kind=kind, version=version))
            after, actor_class = submitted, RECIPE_ACTOR[kind]
        else:
            light = self.light_of(rec.get('from'))
            src = rec['from']
            if src['package'].casefold() != self.c.map.casefold() or src['level'] != 'base':
                self.c.error('level', '%s copies a light of %s level %s; only the base map\'s own lights copy'
                           % (name, src['package'], src['level']), **where)
                return
            why = light_rule(light)
            if why:
                self.c.error('light-view-only', '%s copies %s, which is view only: %s' % (name, short(src['actor']), why),
                           **where)
                return
            if sorted(rec.get('components') or []) != [light['component']]:
                self.c.error('template-changed', '%s names components %s, but its template now has %s'
                           % (name, rec.get('components'), [light['component']]), **where)
                return
            kind = light['kind']
            submitted = self.submitted_light(rec.get('light', {}), kind, where, name)
            if submitted is None:
                return
            after = self.light_after(name, kind, light_values(light), submitted, where)
            p = self.c.pose(rec, where)
            if after is None or not p or not self.light_gate(name, where):
                return
            loc, rot, rounding = p
            source = {'from': short(src['actor'])}
            actor_class = light['actorClass']
        self.members.add('added|' + out)
        self.ops['adds'].append(dict(source, name=name, label=name, kind=kind, role='static', location=loc,
                                           rotation=rot, light=after, guidSeed='%s|%s' % (self.c.doc.get('id'), name),
                                           reach=reach_box(loc, after['radius'])))
        self.c.entities.append(dict(kind='light', op='add', entity=out, id=rec.get('id'), lightClass=actor_class,
                                  template=rec.get('template') or (rec.get('from') or {}).get('actor'),
                                  location=loc, rotation=rot, rotationRounding=tidy(rounding, 6),
                                  reaches=self.reaching(loc, after)))

    def reaching(self, location, values):
        """How many of the base map's pieces a light's radius reaches at `location` (the report's estimate of what a
        full build relights; plan 4.2): object boxes within its radius."""
        if self.object_boxes is None:
            self.object_boxes = []
            meshes = self.c.scene.get('meshes') or {}
            for o in self.c.scene.get('objects') or []:
                if o.get('layer') == 'base' and o.get('mesh') in meshes and o.get('location') is not None:
                    try:
                        self.object_boxes.append(world_box(o, meshes, o['location'], o['rotation']))
                    except (KeyError, TypeError, ValueError, IndexError):
                        continue
        r2 = float(values.get('radius') or 0) ** 2
        n = 0
        for b in self.object_boxes:
            d2 = sum(max(b[2 * k] - location[k], 0, location[k] - b[2 * k + 1]) ** 2 for k in range(3))
            n += d2 <= r2
        return n

    def copy_area_light(self, light, owner, entity, move, donor=None):
        lname = short(light['actor'])
        name = '%s_%s' % (lname, short(entity))
        location, rotation = moved_light_pose(light['location'], light['rotation'], move)
        seed = '%s|%s|%s' % (self.c.doc.get('id'), lname, short(entity))
        if donor:
            seed += '|' + donor['package']
        op = dict(op='copy', name=name, light=lname, owner=short(owner), ownerEntity=short(entity),
                  label='area-copy:' + name, location=location, rotation=rotation, guidSeed=seed,
                  reach=dict(before=None, after=reach_box(location, light['radius'])))
        if donor:
            op['donor'] = donor
        self.ops['area'].append(op)
        self.c.entities.append(dict(kind='light', op='area-copy', target=light['actor'], owner=owner,
                                  ownerEntity=entity, lightClass=light['actorClass']))

    def area_bindings(self):
        """The effective glowing piece of each area light: {light actor path: (owner actor path or None, where it came
        from)}: the project's areaLightBindings, else the export's verified association. A binding this compiler can't
        use is left out (its light follows the export's association), and so is a list that is no list."""
        out = {}
        for light in self.c.scene.get('lights') or []:
            if light.get('role') != 'area' or light.get('layer') != 'base':
                continue
            att = light.get('emitterAttachment') or {}
            owner = (att.get('owner') or {}).get('target') if att.get('status') == 'verified' else None
            out[light['actor']] = (owner.get('actor') if owner else None, 'export' if owner else att.get('status'))
        records = self.c.doc.get('areaLightBindings')
        if records is None:
            return out
        if not isinstance(records, list):
            self.c.leave_out('malformed', '"areaLightBindings" must be a list: the bindings are left out, and each '
                           'generated light follows the glowing piece the export found for it', record='areaLightBindings')
            return out
        seen = set()
        for k, rec in enumerate(records):
            where = dict(record='areaLightBindings[%d]' % k)
            target = rec.get('target') if isinstance(rec, dict) else None
            light = self.light_of(target)
            if not isinstance(rec, dict) or not isinstance(target, dict) or 'owner' not in rec:
                self.c.leave_out('area-binding', 'a binding names an area light (target) and its owner (or null): this one '
                               'is left out', **where)
                continue
            where['target'] = str(target.get('actor'))
            if light is None or light.get('role') != 'area' or light.get('layer') != 'base':
                self.c.leave_out('area-binding', '%s is not an area light of %s\'s base level in the export: its binding '
                               'is left out' % (short(str(target.get('actor'))), self.c.map), **where)
                continue
            if light['actor'] in seen:
                self.c.leave_out('area-binding', '%s is bound twice: the first binding holds' % short(light['actor']), **where)
                continue
            seen.add(light['actor'])
            owner = rec['owner']
            if owner is None:
                out[light['actor']] = (None, 'kept')
                continue
            ot = owner.get('target') if isinstance(owner, dict) else None
            parts = self.c.actors.get(target_key(ot)) if target_key(ot) else None
            if (not parts or ot.get('level') != 'base' or str(ot.get('package')).casefold() != self.c.map.casefold()
                    or not any(p.get('component') == owner.get('component') for p in parts)):
                self.c.leave_out('area-binding', '%s is bound to a piece that is not a base-level piece of %s in the export'
                               ' (or not its component): the binding is left out, and the light follows the glowing '
                               'piece the export found for it' % (short(light['actor']), self.c.map), **where)
                continue
            out[light['actor']] = (ot['actor'], 'project')
        return out

    def derive_area_lights(self):
        """The area lights the piece edits take along (plan 4.8), once from the final piece state: a moved original's
        lights move with it (rigid_move of the owner), a deleted one's go, each copy of an owner gets a copy of each
        of its lights at the copy's place. An edited piece that may own an area light whose glowing piece isn't
        settled (ambiguous or unmatched, and not bound in the project) is an error: assign or keep it fixed."""
        if not self.owner_edits:
            return
        bound = self.area_bindings()
        owned = {}
        for light, (owner, _) in bound.items():
            if owner:
                owned.setdefault(owner, []).append(light)
        lights = {l['actor']: l for l in self.c.scene.get('lights') or [] if l.get('role') == 'area'}
        by_id = {l.get('id'): l for l in lights.values()}
        for kind, owner, entity, move, where in self.owner_edits:
            parts = self.c.actors.get((self.c.package, 'base', owner)) or []
            # the lights this piece may have emitted whose glowing piece isn't settled (neither bound nor kept fixed)
            maybe = sorted({lid for o in parts for lid in o.get('areaLights') or []})
            unsettled = []
            for lid in maybe:
                rec = by_id.get(lid)
                if rec is None:
                    continue
                owner_now, why = bound.get(rec['actor'], (None, None))
                if owner_now is None and why != 'kept':
                    unsettled.append(short(rec['actor']))
            if unsettled and self.c.mission_edits.pieces_cleared and kind == 'delete':
                # with its pieces cleared, the Build takes out every area light whose glowing piece isn't settled
                # (clear_level's Pieces part)
                unsettled = []
            if unsettled:
                # (a warning since plan R4: the piece's edit is built, and the light stays as the map has it)
                self.c.note('area-light-unresolved', '%s may be the glowing piece of %s, whose glowing piece isn\'t settled '
                          '(the matcher found it %s): the light stays where the map has it. Assign it or keep it fixed '
                          '(the light\'s inspector) to settle it' % (short(owner), ', '.join(unsettled),
                                                                    'ambiguous or unmatched'), **where)
                continue
            mine = sorted(owned.get(owner, []))
            if not mine:
                self.near_unknown(parts, where)
                continue
            if not self.c.builds('light'):
                # (a warning since plan R4: the piece's edit is built, and its light stays as the map has it)
                self.c.note('family', '%s glows: %s it would take its generated light%s (%s) along, which stay%s where '
                          'the map has %s. %s' % (
                              short(owner), {'move': 'moved,', 'delete': 'deleted,', 'copy': 'copied,'}[kind],
                              '' if len(mine) == 1 else 's', ', '.join(short(m) for m in mine),
                              's' if len(mine) == 1 else '', 'it' if len(mine) == 1 else 'them',
                              FAMILIES['light']['note']), family='light', **where)
                continue
            for light_path in mine:
                light = lights[light_path]
                if kind == 'copy':
                    self.copy_area_light(light, owner, entity, move)
                    continue
                lname = short(light_path)
                before_reach = reach_box(light['location'], light['radius'])
                if kind == 'delete':
                    op = dict(op='delete', name=lname, light=lname, owner=short(owner), ownerEntity=short(owner),
                              label='area-delete:' + lname, location=list(light['location']),
                              rotation=[int(v) for v in light['rotation']], guidSeed=None,
                              reach=dict(before=before_reach, after=None))
                else:
                    loc, rot = moved_light_pose(light['location'], light['rotation'], move)
                    op = dict(op=kind, name=lname, light=lname, owner=short(owner), ownerEntity=short(entity),
                              label='area-move:' + lname, location=loc, rotation=rot, guidSeed=None,
                              reach=dict(before=before_reach, after=reach_box(loc, light['radius'])))
                self.ops['area'].append(op)
                self.c.entities.append(dict(kind='light', op='area-' + kind, target=light_path, owner=owner,
                                          ownerEntity=entity, lightClass=light['actorClass']))

    def near_unknown(self, parts, where):
        """Warns of unmatched area lights (no candidate glowing piece) near an edited piece (plan 4.8): their glow may
        be this piece's, which the matcher couldn't tell from its materials."""
        try:
            box = self.c.boxes(parts, parts[0]['location'], parts[0]['rotation'])
        except (KeyError, TypeError, ValueError, IndexError):
            return
        near = []
        for light in self.c.scene.get('lights') or []:
            att = light.get('emitterAttachment') or {}
            if light.get('role') != 'area' or att.get('status') != 'unmatched' or att.get('candidates'):
                continue
            if all(box[2 * k] - AREA_NEAR <= light['location'][k] <= box[2 * k + 1] + AREA_NEAR for k in range(3)):
                near.append(short(light['actor']))
        if near:
            self.c.note('area-light-near', '%s stands by %s, generated light%s whose glowing piece the export couldn\'t '
                      'find: if it glows from this piece, it stays where it is' % (
                          short(parts[0]['actor']), ', '.join(near), '' if len(near) == 1 else 's'), **where)
