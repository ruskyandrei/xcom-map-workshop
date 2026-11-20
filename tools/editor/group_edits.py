"""The user's groups, for the compiler: which of them break together, and what of each breaks with it
(research/editor-contracts.md, section 2).

Only "break together" reaches the game. groups reads the project's `groups` records, and each group that breaks
together with pieces enough to link gets a number: its copies take it (`break_copies`, the spec's copy's
`breakGroups`), and so do the base map's own pieces of it left in place (`break_originals`, the spec's
`breakOriginals`), its made walls, whose columns list the group's props and cover blocks (`break_walls`, the copy's
`wallGroups`), and its cover blocks that break (their `breakGroup`, on the compiler's cover blocks, whose entity it
makes a destructible prop's). compiler.native_split hands the numbers to the Build's writer (tools/bake/native_copy.py,
cover_blocks.py, frac_walls.group_columns). `report` is the report's `groups`. A group's lock and nesting are the
editor's alone: groups checks the nesting and says what is wrong with it in notes.

This family was moved out of compiler.Compiler as SpawnEdits was (review finding 23). A GroupEdits works for one
Compiler: it reads the document, the map, the export's pieces, lights and effects, the copies, the cover blocks and the
entities from it, with the lights', effects' and buildings' families' state, and says what it finds through its
leave_out, warn and note, so the report and what is left out are the compiler's as before.

Its own tables and helper (BREAKABLE, BREAKING_COVERS, member_key) are here, and the compiler names again the one
others read through it (compiler.member_key, the compiler's tests). What the family shares with the compiler
(MADE_KINDS, map_building_id, original_key, short) it takes from compiler_tables, so it never imports the compiler.
"""
from compiler_tables import MADE_KINDS, map_building_id, original_key, short

# Pieces that can break in the game and be linked to break together: destructible props (collectibles build as such).
BREAKABLE = ('XComDestructibleActor', 'XComCollectible')
# Cover blocks that break with their group (the Build makes them as hidden props), blockers too; an invisible floor
# does not.
BREAKING_COVERS = ('high', 'low', 'block')


def member_key(m):
    """The viewer's key for a group member: an added piece by its output name ({added}), an original by its target
    ({package, level, actor}), another group by its id ({group}: groups nest; prefab plan 5.4), one of the project's
    buildings by its id ({building}; plan 5.4a); None if it is none. A light is a member as a piece is."""
    if isinstance(m, dict) and set(m) == {'building'} and isinstance(m['building'], str):
        return 'building|' + m['building']
    if isinstance(m, dict) and set(m) == {'group'} and isinstance(m['group'], str):
        return 'group|' + m['group']
    if isinstance(m, dict) and set(m) == {'added'} and isinstance(m['added'], str):
        return 'added|' + m['added']
    if isinstance(m, dict) and set(m) == {'package', 'level', 'actor'} and all(isinstance(v, str) for v in m.values()):
        return original_key(m)
    return None


class GroupEdits:
    def __init__(self, compiler):
        self.c = compiler
        # the user's groups that break together (groups): each copy's break group by its member key (the copy's
        # `breakGroups`), the map's own pieces left in place that break with a group ({name, group}), and the report's
        # groups
        self.break_copies, self.break_originals, self.report = {}, [], []
        self.break_walls = {}       # a made wall's member key -> the break group whose pieces its columns list

    def groups(self):
        """The user's groups (research/editor-contracts.md, section 2). Only "break together" reaches the game: each
        such group with two or more breakable pieces gets a number, given to its copies (breakGroups) and to the base
        map's own pieces left in place (breakOriginals), which the copier links at load. A cover block (high or low,
        not an invisible floor) of such a group breaks with it: it takes the group's number (its `breakGroup`), is
        built as a hidden prop (tools/bake/cover_blocks.py) and goes when a breakable piece of the group is
        destroyed; with a block one breakable piece is enough, and it may be the map's own. A wall made from numbers
        in such a group (custom geometry plan, M3 item 4) lists the group's props and cover blocks in its columns by
        them (wallGroups; tools/bake/frac_walls.group_columns), so they go when that part of the wall breaks: with a
        made wall one prop or cover block is enough, and the group's props are made in the map. A locked group's moving as one
        is the editor's alone, and so is nesting: a member that is another group ({group}) names a group of the
        project that is in no other group and does not hold this one (else a note, group-nesting: nothing of nesting
        reaches the game), and takes no part in breaking together, which is over a group's own pieces. A group this
        compiler can't read is left out (it doesn't break together), and so is a list that is no list. Nor do a light or one of the project's buildings ({building};
        prefab plan 5.4a), which only move with their group in the editor; a building named must be the project's
        (group-member, a warning: the member is ignored)."""
        # (`prefab`: the prefab a group was placed from, a label the editor keeps; nothing of it reaches the game)
        known = {'id', 'locked', 'breakTogether', 'members', 'prefab'}
        copies = {c['member']: c for c in self.c.copies}
        covers = self.c.cover_members
        deleted = {original_key(r['target']) for r in self.c.doc.get('overrides') or []
                   if isinstance(r, dict) and isinstance(r.get('target'), dict) and r.get('deleted') is True}
        linked = {}   # member key -> the group that links it
        listed = self.c.building_edits.building_records()[0]
        made = {b['id'] for b in listed if b.get('deleted') is not True}
        # the map's own buildings that can be edited, by the id made from their actor, record or none (map buildings
        # plan, section 2); a deleted one is no member
        gone = {b['id'] for b in listed if b.get('deleted') is True}
        made |= {map_building_id(b) for b, why in self.c.building_edits.map_buildings().values() if why is None} - gone
        records = self.c.doc.get('groups', [])
        if not isinstance(records, list):
            self.c.leave_out('malformed', '"groups" must be a list of groups: the groups are left out, so none of them '
                           'breaks together', record='groups')
            return
        number = 0
        # nesting: each group named as a member is a group of the project, in one group at most, and in no loop
        ids = {rec['id'] for rec in records if isinstance(rec, dict) and isinstance(rec.get('id'), str)}
        holder = {}
        for k, rec in enumerate(records):
            if not isinstance(rec, dict) or not isinstance(rec.get('members'), list):
                continue
            for m in rec['members']:
                if not (isinstance(m, dict) and set(m) == {'group'} and isinstance(m['group'], str)):
                    continue
                where = dict(record='groups[%d]' % k, group=rec.get('id'))
                if m['group'] not in ids or m['group'] == rec.get('id'):
                    self.c.note('group-nesting', 'a group names the group %s as a member, which is %s'
                              % (m['group'], 'itself' if m['group'] == rec.get('id') else 'not a group of the project'), **where)
                elif m['group'] in holder:
                    self.c.note('group-nesting', 'the group %s is a member of two groups; a group is in one at most' % m['group'], **where)
                else:
                    holder[m['group']] = rec.get('id')
        for start in sorted(holder):
            seen, at = set(), start
            while at in holder and at not in seen:
                seen.add(at)
                at = holder[at]
            if at in seen:
                self.c.note('group-nesting', 'the group %s is inside itself, through the groups it is in' % start, group=start)
                break
        for k, rec in sorted(enumerate(records), key=lambda e: str(e[1].get('id') if isinstance(e[1], dict) else '')):
            where = dict(record='groups[%d]' % k)
            members = rec.get('members') if isinstance(rec, dict) else None
            keys = [member_key(m) for m in members] if isinstance(members, list) else []
            if not isinstance(rec, dict) or not isinstance(rec.get('id'), str) or len(keys) < 2 or not all(keys) \
                    or len(set(keys)) != len(keys) or any(not isinstance(rec.get(f, False), bool) for f in ('locked', 'breakTogether')):
                self.c.leave_out('malformed', 'a group needs an id, two or more different members ({added}, {package, '
                               'level, actor}, {group} or {building}) and true or false for locked and breakTogether: '
                               'this one is left out, so its pieces don\'t break together', **where)
                continue
            where['group'] = rec['id']
            for f in sorted(set(rec) - known):
                self.c.note('unknown-field', 'field %r is not part of a group and is ignored' % f, **where)
            entry = dict(id=rec['id'], locked=rec.get('locked', True), breakTogether=rec.get('breakTogether', False),
                         number=0, copies=[], originals=[], blocks=[], walls=[], notBreakable=[])
            self.report.append(entry)
            for m in members:
                if 'building' in m and m['building'] not in made:
                    self.c.warn('group-member', 'the group names the building %s, which is neither one of the project\'s '
                              'buildings nor one of the map\'s; it is ignored' % m['building'], **where)
            if not entry['breakTogether']:
                continue
            links = []   # (kind, member key, label): a copy, or an original left in place (by its short name)
            blocks = []  # member keys of its cover blocks, which break with it
            walls = []   # (member key, label) of its made walls, whose columns list the rest
            for m, key in zip(members, keys):
                if 'group' in m:
                    continue   # a group inside it breaks by its own option
                if 'building' in m or key in self.c.light_edits.members or key in self.c.effect_edits.members \
                        or ('actor' in m and ((m['package'], m['level'], m['actor']) in self.c.lights
                                              or (m['package'], m['level'], m['actor']) in self.c.effect_actors)):
                    continue   # a building's boxes, a light, an effect or a sound move with the group in the editor;
                    # they don't break
                if key in deleted:
                    continue   # it isn't there to break
                if key in linked:
                    self.c.warn('group-member', '%s is in two groups that break together; it breaks with group %s only'
                              % (short(m.get('added') or m.get('actor')), linked[key]), **where)
                    continue
                if key in covers:
                    if self.c.cover_by_member[key]['kind'] in BREAKING_COVERS:
                        blocks.append(key)
                    else:
                        entry['notBreakable'].append(short(m['added']))     # an invisible floor stays
                    continue
                if key in copies:
                    c = copies[key]
                    if c['actorClass'] in BREAKABLE:
                        links.append(('copy', key, c['label']))
                    elif (c.get('generated') or {}).get('kind') in MADE_KINDS:
                        walls.append((key, c.get('whole') or c['label']))
                    else:
                        entry['notBreakable'].append(c['label'])
                    continue
                if 'added' in m:
                    self.c.warn('group-member', 'group member %s is not built (see its own error), so it can\'t break with the group'
                              % short(m['added']), **where)
                    continue
                parts = self.c.actors.get((m['package'], m['level'], m['actor']))
                if not parts or m['level'] != 'base' or m['package'].casefold() != self.c.map.casefold():
                    self.c.warn('group-member', 'group member %s is not a piece of %s\'s base level in the export, so it can\'t break '
                              'with the group' % (short(m['actor']), self.c.map), **where)
                    continue
                if parts[0]['actorClass'] in BREAKABLE:
                    links.append(('original', key, short(m['actor'])))
                else:
                    entry['notBreakable'].append(short(m['actor']))
            for name in entry['notBreakable']:
                self.c.note('group-unbreakable', '%s moves with its group but can\'t break with it (only props, cover '
                          'blocks and made walls break)' % name, **where)
            if walls and (links or blocks):
                if len(walls) > 1:
                    self.c.note('group-walls', 'the group has %d made walls: each lists the group\'s props and cover blocks '
                              'it stands by' % len(walls), **where)
            elif len(links) < (1 if blocks else 2):
                self.c.note('group-unbreakable', 'the group breaks together but has %d breakable piece(s), so nothing is linked'
                          '%s' % (len(links), ' (a cover block goes when a prop of its group is destroyed)' if blocks else ''),
                          **where)
                continue
            # a cover block is made in the map, so its group is linked there even when its props are all the map's own
            # (and so is a made wall)
            if not blocks and not walls and not any(kind == 'copy' for kind, _, _ in links):
                self.c.warn('group-not-linked', 'the group\'s breakable pieces are all the map\'s own, left in place; the patch '
                          'links pieces only through its copies yet, so move or copy one of them', **where)
                continue
            number += 1
            entry['number'] = number
            for kind, key, label in links:
                linked[key] = rec['id']
                if kind == 'copy':
                    self.break_copies[key] = number
                    entry['copies'].append(label)
                else:
                    self.break_originals.append(dict(name=label, group=number))
                    entry['originals'].append(label)
            for key, label in walls:
                linked[key] = rec['id']
                self.break_walls[key] = number
                entry['walls'].append(label)
            for key in blocks:
                linked[key] = rec['id']
                self.c.cover_by_member[key]['breakGroup'] = number
                entry['blocks'].append(self.c.cover_by_member[key]['name'])
                for e in self.c.entities:
                    if e.get('kind') == 'add' and 'added|' + e['entity'] == key:
                        e['actorClass'] = 'XComDestructibleActor'    # built as a hidden prop
