"""The base map's spawn points edited in a project (the editor spawns plan, SP6 and SP7), for the compiler.

A pod, Meld point, drop-in point or no-spawn volume moved, turned, sized or given values in place (spawn_override); a
point deleted where nothing names it (spawn_delete); a pod or Meld point copied from a plain template, or a no-spawn
volume copied or made (spawn_add, volume_add). Each edit checked goes into `ops`, the spec's `spawns` object, which
compiler.native_split hands to the Build's writer (tools/bake/native_spawns.py), and into the report's entities.

This family was the first moved out of compiler.Compiler (review finding 23). A SpawnEdits works for one Compiler: it
reads the map, its package and the export from it, asks it whether the spawn family builds (builds) and for a pose
(pose), and says what it finds through its error, warn and note, so the report and the pieces left out are the
compiler's as before. tests/test_spawn_edit_fixtures.py holds what the family gave for the compiler's fixtures when it
was moved, and checks it still does.

Its own tables (SPAWN_*) are here, and the compiler takes the one it reads (SPAWN_COPY_KINDS) from this module.
What the family shares with the compiler (FAMILIES, EPS_LOCATION, short, tidy) it takes from compiler_tables, so
it never imports the compiler.
"""
import math

# (compiler_tables puts tools/viewer on the path, for missions)
from compiler_tables import EPS_LOCATION, FAMILIES, short, tidy
import missions

# the spawn points an edit may change (the export's `spawns` kinds), each kind's values, and what a value may be; a
# no-spawn volume is moved and sized by its box (export 34 reads its two switches)
SPAWN_EDIT_KINDS = ('pod', 'meld', 'dropIn', 'noSpawn')
SPAWN_VALUE_KEYS = {'pod': ('commander', 'secondary', 'use'), 'meld': ('difficulty', 'destroyedOnTurn', 'spawnGroup'),
                    'dropIn': (), 'noSpawn': ('aliens', 'civilians')}
SPAWN_WORDS = {'pod': 'a pod', 'meld': 'a Meld point', 'dropIn': 'a drop-in point', 'noSpawn': 'a no-spawn volume'}
# the kinds a project copies (SP7: an added record of `kind` pod, meld or noSpawn; a noSpawn one with no `from` is a
# new volume, made from one of the map's plain volumes)
SPAWN_COPY_KINDS = ('pod', 'meld', 'noSpawn')
SPAWN_BOOLS = ('commander', 'secondary', 'use', 'aliens', 'civilians')


class SpawnEdits:
    def __init__(self, compiler):
        self.c = compiler
        # the base map's spawn points moved, given values, copied and deleted: the spec's `spawns` object
        self.ops = dict(moves=[], deletes=[], copies=[], values=[])
        self.pod_index = None       # the next free pod index for a copy (free_pod_index)
        self.actors = {}            # the base map's spawn points by actor path (index)

    def index(self, scene):
        """The base map's spawn points by actor path (export 33's `spawns`)."""
        self.actors = {r['actor']: r for r in scene.get('spawns') or [] if isinstance(r, dict) and r.get('actor')}

    def spawn_of(self, target):
        """The base map's spawn point a target {package, level: base, actor} names (export 33's `spawns` record), or
        None."""
        if not isinstance(target, dict) or target.get('level') != 'base' or not isinstance(target.get('actor'), str):
            return None
        if str(target.get('package')).casefold() not in (str(self.c.map).casefold(), str(self.c.package).casefold()):
            return None
        return self.actors.get(target['actor'])

    def spawn_values(self, rec, record, name, where):
        """An override's `spawn` values checked against the point's kind: (values that differ from the map's, ok). A
        pod's `commander`, `secondary` and `use` are true or false; a Meld point's `difficulty` is Easy or Hard, its
        `destroyedOnTurn` a whole number from -1 (never) to 99 and its `spawnGroup` one from 0 to 99. A key of another
        kind is an error; one of no kind is noted and carried. A value the map has already builds nothing."""
        values = rec.get('spawn')
        if values is None:
            return {}, True
        if not isinstance(values, dict):
            self.c.error('malformed', 'the spawn values of %s must be an object' % name, **where)
            return {}, False
        kind = record['kind']
        allowed = SPAWN_VALUE_KEYS.get(kind, ())
        known = {k for keys in SPAWN_VALUE_KEYS.values() for k in keys}
        out, ok = {}, True
        for key, value in sorted(values.items()):
            if key not in known:
                self.c.note('unknown-field', 'spawn value %r of %s is not one this editor knows; it is carried and not '
                            'built' % (key, name), **where)
                continue
            if key not in allowed:
                self.c.error('spawn-values', '%s is %s, which has no %s' % (name, SPAWN_WORDS.get(kind, kind), key), **where)
                ok = False
                continue
            good = (isinstance(value, bool) if key in SPAWN_BOOLS else
                    value in ('Easy', 'Hard') if key == 'difficulty' else
                    isinstance(value, int) and not isinstance(value, bool) and (-1 <= value <= 99 if key == 'destroyedOnTurn'
                                                                                else 0 <= value <= 99))
            if not good:
                self.c.error('spawn-values', '%s: %s %r is not a value it can have (%s)' % (name, key, value, dict(
                    commander='true or false', secondary='true or false', use='true or false', difficulty='Easy or Hard',
                    destroyedOnTurn='a whole number from -1, never, to 99', spawnGroup='a whole number from 0 to 99',
                    aliens='true or false', civilians='true or false')[key]),
                    **where)
                ok = False
                continue
            have = ((record.get('values') or {}).get(key) or {}).get('value')
            if have != value:
                out[key] = value
        return out, ok

    def spawn_box(self, box, name, where):
        """A no-spawn volume's box [x0, y0, z0, x1, y1, z1] checked: six numbers, each side longer than the other.
        Returns it rounded to a thousandth of a unit, or None (an error)."""
        if not (isinstance(box, list) and len(box) == 6 and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                                and math.isfinite(v) for v in box)):
            self.c.error('malformed', '%s: its box must be six numbers, [x0, y0, z0, x1, y1, z1]' % name, **where)
            return None
        if not (box[3] > box[0] and box[4] > box[1] and box[5] > box[2]):
            self.c.error('malformed', '%s: its box %s is empty (each far side must be past the near one)' % (name, box), **where)
            return None
        return [round(float(v), 3) for v in box]

    def spawn_override(self, target, rec, where, record):
        """A base pod, Meld point, drop-in point or no-spawn volume moved, turned, sized or given values (the editor
        spawns plan, SP6), in place: the Build keeps its actor, so what names it (Kismet, wave groups, pod events by
        index) still does. A no-spawn volume moves and sizes by its `box` alone, never a pose."""
        kind, name = record.get('kind'), short(target['actor'])
        for f in sorted(set(rec) - {'target', 'location', 'rotation', 'deleted', 'spawn', 'box'}):
            self.c.note('unknown-field', 'field %r is not part of the override of a spawn point and is ignored' % f, **where)
        if kind != 'noSpawn' and 'box' in rec:
            self.c.error('malformed', '%s is %s, which moves by its place, not a box' % (name, SPAWN_WORDS.get(kind, 'a spawn record')), **where)
            return
        if kind == 'noSpawn' and ('location' in rec or 'rotation' in rec):
            self.c.error('malformed', '%s is a no-spawn volume: it moves and is sized by its box, not a place and turn' % name, **where)
            return
        if kind not in SPAWN_EDIT_KINDS:
            self.c.error('spawn-view-only', '%s is %s, which the editor shows but doesn\'t change' % (
                name, missions.object_words(record) if kind else 'a spawn record'), **where)
            return
        if not self.c.builds('spawn'):
            self.c.error('family', '%s is %s edit. %s' % (name, SPAWN_WORDS[kind], FAMILIES['spawn']['note']),
                         family='spawn', **where)
            return
        if record.get('listed') is False:
            self.c.error('spawn-unlisted', '%s is not in the level\'s actor list, so the game never has it: there is '
                         'nothing to %s' % (name, 'delete' if rec.get('deleted') is True else 'move'), **where)
            return
        if rec.get('deleted') is True:
            self.spawn_delete(target, rec, where, record)
            return
        if record.get('unread'):
            self.c.error('spawn-unread', '%s: the export could not read its values (%s), so the Build leaves it as it is'
                         % (name, record['unread']), **where)
            return
        values, ok = self.spawn_values(rec, record, name, where)
        if not ok:
            return
        moved = False
        if 'box' in rec:
            # a no-spawn volume stretched over its new box in place (native_spawns: its Location and DrawScale3D)
            box = self.spawn_box(rec['box'], name, where)
            if box is None:
                return
            if not record.get('box'):
                self.c.error('spawn-unread', '%s: the export could not read its box, so the Build leaves it as it is' % name, **where)
                return
            before = [float(v) for v in list(record['box']['min']) + list(record['box']['max'])]
            moved = any(abs(a - b) >= EPS_LOCATION for a, b in zip(box, before))
            if moved:
                middle = [round((box[k] + box[k + 3]) / 2, 3) for k in range(3)]
                self.ops['moves'].append(dict(name=name, actorClass=record['actorClass'], kind=kind, box=box,
                                              before=dict(box=before)))
                self.c.entities.append(dict(kind='spawn', op='move', target=target['actor'], actorClass=record['actorClass'],
                                            location=middle, box=box))
        elif 'location' in rec or 'rotation' in rec:
            p = self.c.pose(dict(location=rec.get('location', record['location']),
                                 rotation=rec.get('rotation', record['rotation'])), where)
            if not p:
                return
            loc, rot, rounding = p
            moved = not (all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, record['location']))
                         and rot == [int(v) for v in record['rotation']])
            if moved:
                if record.get('links'):
                    self.c.note('spawn-links', '%s moves; %s stay where the map has them' % (name, ', '.join(sorted(
                        {'its %s %s' % (lk.get('property'), short(str(lk.get('actor') or ''))) for lk in record['links']}))[:240]),
                        **where)
                self.ops['moves'].append(dict(name=name, actorClass=record['actorClass'], kind=kind, location=loc,
                                              rotation=rot, before=dict(location=list(record['location']),
                                                                        rotation=list(record['rotation']))))
                self.c.entities.append(dict(kind='spawn', op='move', target=target['actor'], actorClass=record['actorClass'],
                                            location=loc, rotation=rot, rotationRounding=tidy(rounding, 6)))
        if values:
            self.ops['values'].append(dict(name=name, actorClass=record['actorClass'], kind=kind, spawn=values))
            self.c.entities.append(dict(kind='spawn', op='values', target=target['actor'], actorClass=record['actorClass'],
                                        spawn=values))
        if not moved and not values:
            self.c.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)

    @staticmethod
    def spawn_names(record):
        """What names a base spawn point, in words, as export 33 reads its map: the Kismet that uses it (directly or
        through an object list), a wave system's place, a pod event for its index, another actor's typed reference, and
        what lists it by name."""
        out = []
        for u in record.get('uses') or []:
            by = short(str(u.get('by') or ''))
            how = u.get('how')
            out.append('%s (%s)' % (by, {'direct': 'Kismet', 'indirect': 'Kismet, through an object list',
                                         'wave': 'a wave system\'s place', 'event': 'a pod event for its index',
                                         'typed': 'its %s' % u.get('property', 'reference')}.get(how, how or 'a use')))
        out += ['%s (lists it by name)' % short(str(r)) for r in record.get('referencedBy') or []]
        return sorted(set(out))

    def spawn_delete(self, target, rec, where, record):
        """A base pod, Meld point or drop-in point deleted (the editor spawns plan, SP7): built only when nothing names
        it (spawn_names) and its uses were read; otherwise warning spawn-delete-named, and the point stays."""
        name = short(target['actor'])
        for f in sorted(set(rec) & {'location', 'rotation', 'spawn'}):
            self.c.note('unknown-field', '%s is deleted, so its %s is ignored' % (name, f), **where)
        names = self.spawn_names(record)
        if record.get('unread') or names:
            why = ('the export could not read what uses it (%s)' % record['unread'] if record.get('unread') else
                   '%s %s' % ('; '.join(names[:4]) + ('; and %d more' % (len(names) - 4) if len(names) > 4 else ''),
                              'names it' if len(names) == 1 else 'name it'))
            # (on a map whose triggers are cleared, its mission script cut off from them, it is said only: the user,
            # 23 November 2026)
            say = self.c.note if self.c.mission_edits.triggers_cleared else self.c.warn
            say('spawn-delete-named', '%s stays: %s, and a deleted point would leave %s pointing at nothing'
                % (name, why, 'that' if len(names) <= 1 else 'them'), actor=target['actor'], **where)
            return
        self.ops['deletes'].append(dict(name=name, actorClass=record['actorClass'], kind=record['kind']))
        self.c.entities.append(dict(kind='spawn', op='delete', target=target['actor'], actorClass=record['actorClass']))

    def free_pod_index(self):
        """The next pod index no pod of the variant has and no pod event names (a copy's, SP7): above every index the
        base map's pods and its streams' save, every event the export's uses name, and the copies made so far."""
        if self.pod_index is None:
            used = [-1]
            records = list(self.c.scene.get('spawns') or [])
            for s in (self.c.scene.get('streams') or {}).values():
                if isinstance(s, dict):
                    records += list(s.get('missionObjects') or []) + list(s.get('spawns') or [])
            for r in records:
                if not isinstance(r, dict):
                    continue
                if r.get('kind') == 'pod':
                    v = ((r.get('values') or {}).get('podIndex') or {}).get('value')
                    if isinstance(v, int) and not isinstance(v, bool):
                        used.append(v)
                for u in r.get('uses') or []:
                    if u.get('how') == 'event' and isinstance(u.get('podId'), int):
                        used.append(u['podId'])
            self.pod_index = max(used) + 1
        index, self.pod_index = self.pod_index, self.pod_index + 1
        return index

    def volume_add(self, rec, where):
        """A no-spawn volume the project adds over its `box`: a copy of one of the map's (`from`; the Build clones it)
        or a new one (no `from`: the Build makes it from one of the map's plain volumes, retyped), with its own values
        (`aliens`, `civilians`)."""
        out = rec['actor']
        name = short(out)
        for f in sorted(set(rec) - {'id', 'actor', 'kind', 'from', 'box', 'spawn'}):
            if f in ('location', 'rotation', 'components', 'template', 'cover', 'light', 'flags', 'prefab', 'partner', 'tinted',
                     'effect', 'sound'):
                self.c.error('malformed', '%s is a no-spawn volume the project adds, so it has no %s (a box places it)' % (name, f), **where)
                return
            self.c.note('unknown-field', 'field %r is not part of an added no-spawn volume and is ignored' % f, **where)
        if not isinstance(rec.get('id'), str) or not rec['id']:
            self.c.error('malformed', '%s has no id' % name, **where)
            return
        src = rec.get('from')
        tname = None
        template = {'kind': 'noSpawn', 'actorClass': 'XComNoSpawnVolume',
                    'values': {'aliens': {'value': True, 'from': 'class'}, 'civilians': {'value': True, 'from': 'class'}}}
        if src is not None:
            template = self.spawn_of(src)
            if template is None:
                self.c.error('missing', '%s copies %s, which is no spawn point of this map\'s export'
                             % (name, short(str((src or {}).get('actor')))), **where)
                return
            tname = short(src['actor'])
            if template.get('kind') != 'noSpawn':
                self.c.error('malformed', '%s says it is a no-spawn volume but copies %s, which is %s' % (
                    name, tname, SPAWN_WORDS.get(template.get('kind'), template.get('kind'))), **where)
                return
            if template.get('listed') is False or template.get('unread'):
                self.c.error('spawn-copy-template', '%s copies %s, %s' % (name, tname, 'which is not in the level\'s actor list'
                             if template.get('listed') is False else 'whose values the export could not read (%s)'
                             % template['unread']), **where)
                return
        if not self.c.builds('spawn'):
            self.c.error('family', '%s is a no-spawn volume. %s' % (name, FAMILIES['spawn']['note']), family='spawn', **where)
            return
        box = self.spawn_box(rec.get('box'), name, where)
        if box is None:
            return
        values, ok = self.spawn_values(rec, template, name, where)
        if not ok:
            return
        middle = [round((box[k] + box[k + 3]) / 2, 3) for k in range(3)]
        copy = dict(id=rec['id'], name=name, source=tname, kind='noSpawn', actorClass='XComNoSpawnVolume', box=box)
        if values:
            copy['spawn'] = values
        self.ops['copies'].append(copy)
        self.c.entities.append(dict(kind='spawn', op='add', entity=out, id=rec['id'], actorClass='XComNoSpawnVolume',
                                    template=src['actor'] if src else None, location=middle, box=box,
                                    **({'spawn': values} if values else {})))

    def spawn_add(self, rec, where):
        """A copy of one of the map's pods or Meld points (the editor spawns plan, SP7): the Build clones the template
        (with its components) under the level and sets the copy's own values; a pod's copy gets a free pod index
        (free_pod_index). A copy is made only from a plain template: a pod with no commander or secondary flag, no
        forced type and no link to another actor (so the copy takes no patrol, volume or contingent link); any Meld
        point."""
        out = rec['actor']
        name = short(out)
        kind = rec.get('kind')
        if kind == 'noSpawn':
            self.volume_add(rec, where)
            return
        for f in sorted(set(rec) - {'id', 'actor', 'kind', 'from', 'location', 'rotation', 'spawn'}):
            if f in ('components', 'template', 'cover', 'light', 'flags', 'prefab', 'partner', 'tinted', 'effect', 'sound'):
                self.c.error('malformed', '%s is a copy of %s, so it has no %s' % (name, SPAWN_WORDS[kind], f), **where)
                return
            self.c.note('unknown-field', 'field %r is not part of an added spawn point and is ignored' % f, **where)
        if not isinstance(rec.get('id'), str) or not rec['id']:
            self.c.error('malformed', '%s has no id' % name, **where)
            return
        src = rec.get('from')
        template = self.spawn_of(src)
        if template is None:
            self.c.error('missing', '%s copies %s, which is no spawn point of this map\'s export'
                         % (name, short(str((src or {}).get('actor')))), **where)
            return
        tname = short(src['actor'])
        if template.get('kind') != kind:
            self.c.error('malformed', '%s says it is %s but copies %s, which is %s' % (
                name, SPAWN_WORDS[kind], tname, SPAWN_WORDS.get(template.get('kind'), template.get('kind'))), **where)
            return
        if not self.c.builds('spawn'):
            self.c.error('family', '%s is a copy of %s. %s' % (name, SPAWN_WORDS[kind], FAMILIES['spawn']['note']),
                         family='spawn', **where)
            return
        if template.get('listed') is False or template.get('unread'):
            self.c.error('spawn-copy-template', '%s copies %s, %s' % (name, tname, 'which is not in the level\'s actor list'
                         if template.get('listed') is False else 'whose values the export could not read (%s)'
                         % template['unread']), **where)
            return
        v = lambda key: ((template.get('values') or {}).get(key) or {}).get('value')  # noqa: E731
        if kind == 'pod':
            why = [w for w, bad in (('the commander\'s place', v('commander')), ('a secondary pod', v('secondary')),
                                    ('of a forced alien type', v('forceType')),
                                    ('linked to %s' % ', '.join(sorted(short(str(lk.get('actor'))) for lk in template.get('links') or [])),
                                     template.get('links'))) if bad]
            if why:
                self.c.error('spawn-copy-template', '%s copies %s, which is %s: a copy is made only from a plain pod'
                             % (name, tname, ' and '.join(why)), **where)
                return
        values, ok = self.spawn_values(rec, template, name, where)
        if not ok:
            return
        p = self.c.pose(rec, where)
        if not p:
            return
        loc, rot, rounding = p
        copy = dict(id=rec['id'], name=name, source=tname, kind=kind, actorClass=template['actorClass'], location=loc,
                    rotation=rot)
        if kind == 'pod':
            copy['podIndex'] = self.free_pod_index()
        if values:
            copy['spawn'] = values
        self.ops['copies'].append(copy)
        self.c.entities.append(dict(kind='spawn', op='add', entity=out, id=rec['id'], actorClass=template['actorClass'],
                                    template=src['actor'], location=loc, rotation=rot, rotationRounding=tidy(rounding, 6),
                                    **({'podIndex': copy['podIndex']} if kind == 'pod' else {}), **({'spawn': values} if values else {})))
