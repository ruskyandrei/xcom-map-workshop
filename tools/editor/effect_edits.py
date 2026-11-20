"""The map's effects, ambient sounds and lens flares edited in a project (the effects and sounds plan, Part C, and
stages FX4, FX5 and FX6b), for the compiler.

An original Emitter, ambient sound or LensFlareSource moved, turned or deleted in place, or given values
(effect_override); a copy of one, this map's or another map's through the library (effect_add, foreign_effect). Each
is checked against the export's `can` and `why` (export 28), and goes into `ops`, the spec's `effects`, `sounds` and
`flares` objects (moves, deletes, copies, values), which compiler.native_split hands to the Build's writers
(tools/bake/native_effects.py, native_sounds.py, native_flares.py), and into the report's entities. `members` holds the
group member keys of the copies, and `own` the effects a record of the project's own takes from the piece that carries
them (they leave the spec's carriedEffects).

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). An EffectEdits works for one
Compiler: it reads the map, the scene, the export's effects (effect_actors), the building floors and the library from
it, asks it whether a family builds (builds) and for a pose (pose), and says what it finds through its error, warn and
note, so the report and the pieces left out are the compiler's as before.

Its own tables (EFFECT_WORDS, EFFECT_VALUE_KEYS, PARAMETER_TYPES, SOUND_* and the others) are here, and the compiler
names again those that others read through it (compiler.EFFECT_WORDS, compiler.SOUND_PITCH, ...). What the family
shares with the compiler (EFFECT_KINDS, FAMILIES, EPS_LOCATION, LibraryError, short, target_key, tidy) it takes from
compiler_tables, so it never imports the compiler.
"""
import math

from compiler_tables import EFFECT_KINDS, EPS_LOCATION, FAMILIES, LibraryError, short, target_key, tidy

# Effects and sounds (the effects and sounds plan, Part C): their records name actors of the export's `effects` and
# `sounds` (export 28, effects_metadata.py), each with what an edit may do with it (`can`, `why`). EFFECT_CLASSES:
# what each kind is (a lens flare, `flares`, since stage FX6b). An effect that is moved or new is listed by
# each upper floor (index 1 up) one of whose boxes holds its place within EFFECT_SLACK (buildings.SLACK; plan Part D):
# the report's note says which floors it joins and leaves.
EFFECTS_EXPORT = 28
EFFECT_CLASSES = {'effect': ('Emitter',),
                  'sound': ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundMovable'),
                  'flare': ('LensFlareSource',)}
# what the messages call each kind (its lane of the spec is compiler.EFFECT_LANES)
EFFECT_WORDS ={'effect': 'an effect', 'sound': 'a sound', 'flare': 'a lens flare'}
EFFECT_SLACK = 2.0
# the values objects (plan Part C): `follow` (an effect's carrying by the piece it stands on: 'none' once it is moved
# by itself, 'auto' to follow again) is FX3's; the others are stage FX5's, behind the effect-values and sound-values
# families: an effect's `scale` (a multiplier on the size the map gives it), `startsOn` and `parameters` ([{name,
# value}]: a scalar, a vector [x, y, z] or a colour [r, g, b, a], each 0 to 1, by the kind its effect saves it in, else
# by its system's parameter); a sound's `radiusMin`, `radiusMax`, `volume` and `pitch` ([least, most]) and `startsOn`
EFFECT_VALUE_KEYS = {'effect': ('scale', 'startsOn', 'parameters', 'follow'),
                     'sound': ('radiusMin', 'radiusMax', 'volume', 'pitch', 'startsOn')}
EFFECT_FOLLOW = ('none', 'auto')
# what a value may be (refused outside: nothing the game's maps come near; the page's handles and sliders stay well
# inside): an effect's size multiplier, a parameter's magnitude, a sound's radius, volume and pitch
EFFECT_SCALE = (1 / 64, 64.0)
PARAMETER_MAX = 1e6
SOUND_RADIUS_MAX = 65536.0
SOUND_VOLUME_MAX = 16.0
SOUND_PITCH = (1 / 16, 16.0)
# the particle parameter types the editor writes, by the kind of value: what a saved entry's type takes, and the type
# a parameter the effect doesn't save gets from its system's distribution
PARAMETER_TYPES = {'PSPT_Scalar': 'scalar', 'PSPT_Vector': 'vector', 'PSPT_Color': 'colour'}
DISTRIBUTION_TYPES = {'scalar': 'PSPT_Scalar', 'vector': 'PSPT_Vector'}


class EffectEdits:
    def __init__(self, compiler):
        self.c = compiler
        # the spec's `effects`, `sounds` and `flares` objects (moves, deletes, copies, values), the group member keys
        # of the copies the project adds, and the effects a record of the project's own takes from the piece that
        # carries them (they leave carriedEffects)
        self.ops = {k: dict(moves=[], deletes=[], copies=[], values=[]) for k in EFFECT_KINDS}
        self.members = set()
        self.own = set()

    def effect_of(self, target):
        """The export's effect, sound or flare a target {package, level, actor} names (its record with `kind`), or
        None."""
        key = target_key(target)
        return self.c.effect_actors.get(key) if key else None

    def effect_values(self, rec, kind, name, where, source=None, systems=None):
        """A record's values object checked (the effects and sounds plan, Part C): (follow or None, values or None,
        ok). `follow` is stage FX3's ('none': it doesn't follow the piece it stands on; 'auto': it does); `values` the
        others (stage FX5), checked against `source` (the export record of the effect or sound they are set on, or
        that a copy copies) and `systems` (its particle systems' records), as the Build's writer takes them: an
        effect's {scale, startsOn, parameters: [{name, type, value}]}, a sound's {radiusMin, radiusMax, volume,
        pitch, startsOn}. Refused: a malformed value, one outside what a value may be, a parameter its effect neither
        saves in a kind the editor writes nor its system offers in one kind, and values while their family doesn't
        build (effect-values, sound-values). A lens flare has no values object at all (its template and colour stay
        as the map has them)."""
        what = EFFECT_WORDS[kind]
        other = next((k for k in ('effect', 'sound') if k != kind and k in rec), None)
        if other:
            self.c.error('malformed', '%s is %s, so it has no %s values' % (name, what, other), **where)
            return None, None, False
        if kind == 'flare':
            if 'flare' in rec:
                self.c.error('malformed', '%s is a lens flare, whose template and colour stay as the map has them: it '
                           'has no values' % name, **where)
                return None, None, False
            return None, None, True
        values = rec.get(kind)
        if values is None:
            return None, None, True
        if not isinstance(values, dict):
            self.c.error('malformed', '%s: "%s" must be an object of %s values' % (name, kind, kind), **where)
            return None, None, False
        bad = sorted(set(values) - set(EFFECT_VALUE_KEYS[kind]))
        if bad:
            self.c.error('malformed', '%s: %s %s not %s value (they are %s)' % (
                name, ', '.join(bad), 'is' if len(bad) == 1 else 'are', what, ', '.join(EFFECT_VALUE_KEYS[kind])), **where)
            return None, None, False
        follow = values.get('follow')
        if follow is not None and follow not in EFFECT_FOLLOW:
            self.c.error('malformed', '%s: follow must be one of %s' % (name, ', '.join(EFFECT_FOLLOW)), **where)
            return None, None, False
        given = {k: v for k, v in values.items() if k != 'follow'}
        if not given:
            return follow, None, True
        gate = kind + '-values'
        if not self.c.builds(gate):
            self.c.error('family', '%s sets its %s. %s' % (name, ', '.join(sorted(given)), FAMILIES[gate]['note']),
                       family=gate, **where)
            return None, None, False
        source = source or {}
        if not (source.get('can') or {}).get('values'):
            why = (source.get('why') or {}).get('values') or 'the export doesn\'t say its values can change'
            self.c.error('effect-view-only', '%s\'s values can\'t be set: %s' % (name, why), **where)
            return None, None, False
        out = {}
        number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        if 'startsOn' in given:
            if not isinstance(given['startsOn'], bool):
                self.c.error('malformed', '%s: startsOn is true or false' % name, **where)
                return None, None, False
            out['startsOn'] = given['startsOn']
        if kind == 'effect':
            if 'scale' in given:
                v = given['scale']
                if not number(v) or not EFFECT_SCALE[0] <= v <= EFFECT_SCALE[1]:
                    self.c.error('malformed', '%s: its size is a multiplier of %g to %g of the size the map gives it'
                               % (name, EFFECT_SCALE[0], EFFECT_SCALE[1]), **where)
                    return None, None, False
                out['scale'] = float(v)
            if 'parameters' in given:
                params = self.effect_parameters(given['parameters'], name, where, source, systems)
                if params is None:
                    return None, None, False
                if params:
                    out['parameters'] = params
            return follow, out, True
        have = source.get('values') or {}
        for key in ('radiusMin', 'radiusMax'):
            if key in given:
                v = given[key]
                if not number(v) or not 0 <= v <= SOUND_RADIUS_MAX:
                    self.c.error('malformed', '%s: %s is 0 to %g units' % (name, key, SOUND_RADIUS_MAX), **where)
                    return None, None, False
                out[key] = float(v)
        lo, hi = out.get('radiusMin', have.get('radiusMin')), out.get('radiusMax', have.get('radiusMax'))
        if ('radiusMin' in out or 'radiusMax' in out) and number(lo) and number(hi) and lo > hi:
            self.c.error('malformed', '%s: its inner radius (%g) is beyond its outer one (%g)' % (name, lo, hi), **where)
            return None, None, False
        for key, (least, most) in (('volume', (0.0, SOUND_VOLUME_MAX)), ('pitch', SOUND_PITCH)):
            if key not in given:
                continue
            v = given[key]
            if (not isinstance(v, list) or len(v) != 2 or not all(number(x) for x in v) or v[0] > v[1]
                    or v[0] < least or v[1] > most):
                self.c.error('malformed', '%s: %s is [least, most], each %g to %g' % (name, key, least, most), **where)
                return None, None, False
            out[key] = [float(x) for x in v]
        return follow, out, True

    def effect_parameters(self, given, name, where, source, systems):
        """An effect's parameters ([{name, value}]) as the writer takes them ([{name, type, value}]), or None with an
        error: a parameter the effect saves keeps the type it is saved in (a scalar, vector or colour entry; the
        first of the name, as the game reads it), one it doesn't is added in the kind its system's distribution of
        that name has (all of them one kind)."""
        if not isinstance(given, list):
            self.c.error('malformed', '%s: parameters is a list of {name, value}' % name, **where)
            return None
        saved = {}
        for prm in source.get('parameters') or []:
            if prm.get('name') and prm['name'] not in saved:
                saved[prm['name']] = prm
        offers = {}
        system = (systems or {}).get(source.get('system')) if source.get('system') else None
        for o in (system or {}).get('offers') or []:
            offers.setdefault(o['name'], set()).add(o['kind'])
        number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        out, seen = [], set()
        for prm in given:
            if not isinstance(prm, dict) or set(prm) != {'name', 'value'} or not isinstance(prm['name'], str) or not prm['name']:
                self.c.error('malformed', '%s: each parameter is {name, value}' % name, **where)
                return None
            pname = prm['name']
            if pname in seen:
                self.c.error('malformed', '%s sets parameter %s twice' % (name, pname), **where)
                return None
            seen.add(pname)
            if pname in saved:
                type_ = saved[pname].get('type')
                if type_ not in PARAMETER_TYPES:
                    self.c.error('effect-view-only', '%s\'s parameter %s is of type %s, which the editor keeps as the map '
                               'has it' % (name, pname, type_), **where)
                    return None
            elif len(offers.get(pname, ())) == 1:
                type_ = DISTRIBUTION_TYPES[next(iter(offers[pname]))]
            elif pname in offers:
                self.c.error('effect-view-only', '%s\'s system reads parameter %s both as a number and as a vector, so it '
                           'is kept as the map has it' % (name, pname), **where)
                return None
            else:
                self.c.error('malformed', '%s\'s system has no parameter %s%s' % (
                    name, pname, '' if system else ' (its system didn\'t resolve)'), **where)
                return None
            v, shape = prm['value'], PARAMETER_TYPES[type_]
            ok = (number(v) and abs(v) <= PARAMETER_MAX if shape == 'scalar'
                  else isinstance(v, list) and len(v) == 3 and all(number(x) and abs(x) <= PARAMETER_MAX for x in v)
                  if shape == 'vector'
                  else isinstance(v, list) and len(v) == 4 and all(number(x) and 0 <= x <= 1 for x in v))
            if not ok:
                self.c.error('malformed', '%s: parameter %s is %s' % (name, pname, dict(
                    scalar='a number', vector='three numbers [x, y, z]',
                    colour='a colour [r, g, b, a], each 0 to 1')[shape]), **where)
                return None
            out.append(dict(name=pname, type=type_, value=float(v) if shape == 'scalar' else [float(x) for x in v]))
        return out

    def effect_value_warnings(self, name, kind, values, source, where, copy=False):
        """The warnings for an effect's or sound's values (decision 9: what may behave oddly in the game): one that
        starts off with nothing to switch it on, and values the map's script changes too."""
        if not values:
            return
        users = ' '.join(source.get('referencedBy') or []) if not copy else ''
        starts = values.get('startsOn', source.get('startsOn'))
        if 'startsOn' in values and starts is False and 'Toggle' not in users:
            self.c.warn('effect-starts-off', '%s starts off, and nothing in the map\'s script switches it on' % name,
                      **where)
        elif 'startsOn' in values and 'Toggle' in users:
            self.c.warn('mission-linked', '%s is switched on and off by the map\'s Kismet (%s): what it starts as lasts '
                      'until the script switches it' % (name, '; '.join(source['referencedBy'][:4])), **where)
        if values.get('parameters') and 'SetParticleSysParam' in users:
            self.c.warn('mission-linked', '%s\'s parameters are set by the map\'s Kismet too (%s): what the script sets '
                      'replaces these when it runs' % (name, '; '.join(source['referencedBy'][:4])), **where)

    def effect_gate(self, kind, name, where):
        """The family's refusal while it doesn't build: True when the edit may go on."""
        if self.c.builds(kind):
            return True
        self.c.error('family', '%s is %s edit. %s' % (name, EFFECT_WORDS[kind], FAMILIES[kind]['note']), family=kind,
                   **where)
        return False

    def effect_usable(self, rec, can, name, where):
        """Whether the export says an edit may `can` (move, copy, delete) the effect or sound `rec`: True, or False
        with the export's reason as an error."""
        if (rec.get('can') or {}).get(can):
            return True
        if 'can' not in rec:
            self.c.error('export-version', '%s: this map\'s export predates the effects and sounds data (export %d): '
                       'prepare it again' % (name, EFFECTS_EXPORT), minimum=EFFECTS_EXPORT, **where)
            return False
        why = (rec.get('why') or {}).get(can) or 'the export doesn\'t say it can'
        self.c.error('effect-view-only', '%s can\'t be %s: %s' % (
            name, dict(move='moved', copy='copied', delete='deleted')[can], why), **where)
        return False

    def effect_listing(self, location):
        """[(building path, floor index)]: the upper floors (index 1 up) one of whose boxes, as the project has them,
        holds `location` within EFFECT_SLACK: where the Build lists a moved or new effect (plan Part D)."""
        out = []
        for name, index, boxes in self.c.floor_edits.floor_boxes_now() or []:
            if index >= 1 and any(all(b['min'][a] - EFFECT_SLACK <= location[a] <= b['max'][a] + EFFECT_SLACK
                                      for a in range(3)) for b in boxes):
                out.append((name, index))
        return out

    def effect_floor_note(self, name, rec, location, where):
        """The note (not a warning) saying which floors' cutaways a moved or new effect joins and leaves: listed, it
        hides when its floor is cut away. A sound is in no floor's list."""
        if self.c.floor_boxes is None:
            return
        old = {(self.c.building_names.get(f.get('building')), f.get('floor')) for f in (rec or {}).get('floors') or []}
        new = set(self.effect_listing(location))
        words = lambda fs: ', '.join('floor %d of %s' % (k + 1, short(str(b))) for b, k in sorted(fs, key=str))
        joins, leaves = new - old, old - new
        if joins or leaves:
            self.c.note('effect-floors', '%s%s%s' % (name, ' joins the cutaway of %s' % words(joins) if joins else '',
                                                   ('%s leaves the cutaway of %s' % (',' if joins else '', words(leaves)))
                                                   if leaves else ''),
                      joins=[[short(str(b)), k] for b, k in sorted(joins, key=str)],
                      leaves=[[short(str(b)), k] for b, k in sorted(leaves, key=str)], **where)

    def effect_script(self, name, rec, what, where):
        """The warning for an edit of an effect or sound the mission's script names (export 15's referencedBy): the
        script acts on the original, wherever it is, and not on a copy."""
        if rec.get('referencedBy'):
            self.c.warn('mission-linked', '%s is named by the map\'s Kismet (%s): %s' % (
                name, '; '.join(rec['referencedBy'][:4]), what), **where)

    def effect_override(self, target, rec, where, effect):
        """An original effect or sound moved, turned or deleted (the effects and sounds plan, Part C), in place: the
        Build keeps its actor, so what names it still does."""
        kind, name = effect['kind'], short(target['actor'])
        for f in sorted(set(rec) - {'target', 'location', 'rotation', 'deleted', 'effect', 'sound', 'flare'}):
            self.c.note('unknown-field', 'field %r is not part of the override of %s and is ignored' % (f, EFFECT_WORDS[kind]),
                      **where)
        if target['level'] != 'base' or str(target['package']).casefold() != self.c.map.casefold():
            self.c.error('effect-view-only', '%s is %s of %s level %s, which the editor shows but doesn\'t change'
                       % (name, EFFECT_WORDS[kind], target['package'], target['level']), **where)
            return
        if not self.effect_gate(kind, name, where):
            return
        follow, values, ok = self.effect_values(rec, kind, name, where, effect, self.c.scene.get('effectSystems'))
        if not ok:
            return
        ops = self.ops[kind]
        if rec.get('deleted') is True:
            if not self.effect_usable(effect, 'delete', name, where):
                return
            self.own.add(target['actor'])
            self.effect_script(name, effect, 'it is taken out of the level, so what the script does with it does '
                               'nothing', where)
            ops['deletes'].append(dict(name=name, actorClass=effect['actorClass'], location=list(effect['location'])))
            self.c.entities.append(dict(kind=kind, op='delete', target=target['actor'], actorClass=effect['actorClass']))
            return
        def set_values():
            # its values, set on the actor in place (stage FX5): only once the record is known to build, since a
            # record left out for its pose or its follow rule builds nothing of it
            if values:
                self.effect_value_warnings(name, kind, values, effect, where)
                ops['values'].append(dict(name=name, actorClass=effect['actorClass'], **{kind: values}))
                self.c.entities.append(dict(kind=kind, op='values', target=target['actor'], actorClass=effect['actorClass'],
                                          **{kind: values}))
        if 'location' not in rec and 'rotation' not in rec:
            set_values()
            if follow is None:
                if not values:
                    self.c.error('malformed', 'the override of %s is deleted%s' % (
                        EFFECT_WORDS[kind], ' or gives a pose' if kind == 'flare' else ', gives a pose or values'), **where)
            else:
                # follow alone: carrying as the map has it ('auto') or not ('none', where it stands)
                if follow == 'none' and effect.get('carriedBy'):
                    self.own.add(target['actor'])
                    self.c.note('effect-detached', '%s stays where it is when %s moves' % (
                        name, short(effect['carriedBy'])), **where)
                elif not values:
                    self.c.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)
            return
        p = self.c.pose(dict(location=rec.get('location', effect['location']),
                           rotation=rec.get('rotation', effect['rotation'])), where)
        if not p:
            return
        loc, rot, rounding = p
        moved = not (all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, effect['location']))
                     and rot == [int(v) for v in effect['rotation']])
        if follow == 'auto' and effect.get('carriedBy'):
            self.c.error('malformed', '%s follows %s (follow auto), so it has no pose of its own'
                       % (name, short(effect['carriedBy'])), **where)
            return
        if not moved:
            set_values()
            if not values:
                self.c.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)
            return
        if not self.effect_usable(effect, 'move', name, where):
            return
        set_values()
        # its own pose: the piece it stood on no longer takes it along (plan Part C, ownership and precedence)
        self.own.add(target['actor'])
        if effect.get('carriedBy'):
            self.c.note('effect-detached', '%s has a place of its own, so it no longer moves with %s'
                      % (name, short(effect['carriedBy'])), **where)
        self.effect_script(name, effect, 'the script still acts on it where it stands now (and a Matinee can put it '
                           'back where it was)', where)
        if kind == 'effect':
            self.effect_floor_note(name, effect, loc, where)
        ops['moves'].append(dict(name=name, actorClass=effect['actorClass'], location=loc, rotation=rot,
                                 before=dict(location=list(effect['location']), rotation=list(effect['rotation']))))
        self.c.entities.append(dict(kind=kind, op='move', target=target['actor'], actorClass=effect['actorClass'],
                                  location=loc, rotation=rot, rotationRounding=tidy(rounding, 6)))

    def effect_add(self, rec, where):
        """A copy of one of the map's effects, sounds or lens flares (the effects and sounds plan, Part C): the Build
        clones the actor and what it owns (its component, light environment and own cue) and shares the system, the
        wave or the flare's template. A copy of
        another map's (`from` names a base map other than this one: stage FX4) comes from the library
        (foreign_effect): the Build stages its donor actor with what it needs (transplant.stage_edit) and clones that."""
        out = rec['actor']
        name = short(out)
        kind = rec.get('kind')
        for f in sorted(set(rec) - {'id', 'actor', 'kind', 'from', 'location', 'rotation', 'effect', 'sound', 'flare'}):
            if f in ('components', 'template', 'cover', 'light', 'flags', 'prefab', 'partner', 'tinted'):
                self.c.error('malformed', '%s is a copy of %s, so it has no %s' % (
                    name, EFFECT_WORDS.get(kind, 'an effect'), f), **where)
                return
            self.c.note('unknown-field', 'field %r is not part of an added effect, sound or lens flare and is ignored' % f,
                      **where)
        if kind not in EFFECT_KINDS:
            self.c.error('malformed', '%s: kind must be one of %s' % (name, ', '.join(EFFECT_KINDS)), **where)
            return
        if not isinstance(rec.get('id'), str) or not rec['id']:
            self.c.error('malformed', '%s has no id' % name, **where)
            return
        src = rec.get('from')
        donor, systems = None, None
        if (isinstance(src, dict) and src.get('level') == 'base' and isinstance(src.get('package'), str)
                and isinstance(src.get('actor'), str) and src['package'].casefold() != self.c.map.casefold()):
            source, donor, systems = self.foreign_effect(src, name, where)
            if source is None:
                return
        else:
            source = self.effect_of(src)
            if source is None:
                self.c.error('missing', '%s copies %s, which is no effect, sound or lens flare of the export'
                           % (name, short(str((src or {}).get('actor')))), **where)
                return
        if source['kind'] != kind:
            self.c.error('malformed', '%s says it is %s but copies %s, which is %s' % (
                name, kind, short(src['actor']), source['kind']), **where)
            return
        if src['level'] != 'base':
            self.c.error('effect-view-only', '%s copies %s of %s level %s; only a base map\'s own are copied'
                       % (name, short(src['actor']), src['package'], src['level']), **where)
            return
        if not self.effect_gate(kind, name, where):
            return
        follow, values, ok = self.effect_values(rec, kind, name, where, source,
                                                systems if donor else self.c.scene.get('effectSystems'))
        if not ok:
            return
        if follow is not None:
            self.c.note('unknown-field', '%s is a copy, which no piece carries: its follow is ignored' % name, **where)
        p = self.c.pose(rec, where)
        if not p or not self.effect_usable(source, 'copy', name, where):
            return
        loc, rot, rounding = p
        self.members.add('added|' + out)
        if kind == 'effect':
            self.effect_floor_note(name, None, loc, where)
        if source.get('referencedBy'):
            self.c.note('effect-script-copy', '%s is a copy of %s, which its map\'s Kismet names: the copy is an ordinary '
                      '%s, which the script doesn\'t switch on or off' % (
                          name, short(src['actor']), 'lens flare' if kind == 'flare' else kind), **where)
        if (values or {}).get('startsOn', source.get('startsOn')) is False:
            self.c.warn('effect-starts-off', '%s is a copy of %s, %s: nothing switches the copy on' % (
                name, short(src['actor']), 'set to start off' if (values or {}).get('startsOn') is False
                else 'which starts off and waits for the script to switch it on'), **where)
        self.effect_value_warnings(name, kind, {k: v for k, v in (values or {}).items() if k != 'startsOn'}, source,
                                   where, copy=True)
        if source.get('landingActor') or source.get('landingRole'):
            # Long War's landing mutator (XComLZMutator.HideDropShip) destroys every actor made from the grounded
            # Skyranger's archetypes when a battle loads, and a copy keeps its source's archetype (F-120)
            self.c.warn('effect-landing-copy', '%s is a copy of %s, one of the landing\'s actors: under Long War the '
                      'landing mutator takes out every actor made like the landing\'s when the battle loads, the copy '
                      'among them (plain Enemy Within keeps it)' % (name, short(src['actor'])), **where)
        copy = dict(id=rec['id'], name=name, source=short(src['actor']), actorClass=source['actorClass'], location=loc,
                    rotation=rot)
        if values:
            copy['values'] = values
        if donor:
            # the Build stages the donor's actor in the map (transplant.stage_edit) and clones the staged one
            copy['donor'] = donor
            row = self.c.donor_report.setdefault(donor['package'], dict(donor, pieces=[]))
            if short(src['actor']) not in row['pieces']:
                row['pieces'].append(short(src['actor']))
        self.ops[kind]['copies'].append(copy)
        self.c.entities.append(dict(kind=kind, op='add', entity=out, id=rec['id'], actorClass=source['actorClass'],
                                  template=src['actor'], location=loc, rotation=rot,
                                  rotationRounding=tidy(rounding, 6), **({'donor': donor} if donor else {})))

    def foreign_effect(self, src, name, where):
        """(record, donor, systems) of the effect, ambient sound or lens flare of another map a copy names (the effects
        and sounds plan, stage FX4; a flare since FX6b): its export 28 record as the library reads it from its map (library.effect), its donor
        {package, sha256} for the Build's staging and its system's record ({key: record}); (None, None, None) with an
        error. What the library can't bring is
        refused (a landing's actor, one riding on another, one whose closure the transplant refuses); one only the
        foreign gate holds back (FOREIGN_FAMILIES, which has listed effects and sounds since EXP-69 and lens flares
        since EXP-71) is built as any copy, as the pieces of a kind not brought before are (FOREIGN_SOFT)."""
        if self.c.library is None:
            self.c.error('no-library', '%s copies %s of %s, and this build has no library of other maps\' pieces'
                       % (name, short(src['actor']), src['package']), **where)
            return None, None, None
        try:
            template, entry = self.c.library.effect(src)
        except LibraryError as error:
            self.c.error(error.code, str(error), **where)
            return None, None, None
        if not entry['placeable'] and entry.get('blocked') != 'family':
            self.c.error('not-placeable', '%s copies %s of %s, which can\'t be placed in another map: %s'
                       % (name, short(src['actor']), template['source']['package'], entry['reason']), **where)
            return None, None, None
        source = template['source']
        return (template['record'], dict(package=source['package'], sha256=source['sha256']),
                template.get('systems') or {})
