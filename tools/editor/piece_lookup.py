"""The library of other maps' pieces as the compiler asks it (Library): tools/viewer/library.py's scan of the
install's maps, kept in the cache, and a piece's or an effect's record, exported from the install on first request.

The compiler's foreign_piece asks it for a piece of another map (record) and the effects family's foreign_effect for
an effect, ambient sound or lens flare (effect); what can't be had is a LibraryError (compiler_tables: no-library,
donor-missing, donor-changed or not-placeable), which the compiler reports as the error that leaves the record out.

It was moved out of compiler.py (review finding 23). The compiler names it again (compiler.Library), and what makes
one makes it there: the Build (build.py), the prefab stage, the compiler's command line, the tests and the examples'
generators. It takes LibraryError and short from compiler_tables, so it never imports the compiler.
"""
from compiler_tables import LibraryError, short


class Library:
    """The library of other maps' pieces as the compiler asks it (tools/viewer/library.py): the scan's index in the
    cache, and a piece's record, exported from the install on first request."""

    def __init__(self, cache, game):
        self.cache, self.game = cache, game
        self.index = None
        self.shared = {}        # library.piece's: the install's maps listed once, each map opened once

    def record(self, target, sky=False):
        """(the piece record, its index entry) of a target {package, level, actor}; LibraryError otherwise. `sky`: a sky
        dome (every mesh a Skybox one), which the library leaves out, is taken too: a test stage's backdrop (prefab plan
        5.11)."""
        import library
        from projects import ProjectError
        index, entries, donors = self.load()
        try:
            record = library.piece(self.cache, self.game, dict(package=target['package'], level=target['level'],
                                                               actor=short(target['actor'])), self.shared)
        except ProjectError as error:
            code = error.extra.get('code')
            if code == 'donor-missing':
                raise LibraryError('donor-missing', 'the game install has no map %s, which %s comes from'
                                   % (target['package'], short(target['actor'])))
            if code == 'piece-missing':
                raise LibraryError('donor-changed', 'the map %s has no piece %s any more'
                                   % (target['package'], short(target['actor'])))
            raise LibraryError('not-placeable', error.message)
        known = donors.get(record['source']['package'].casefold())
        if known is None or known['sha256'] != record['source']['sha256']:
            raise LibraryError('donor-changed', 'the map %s is not the file the library was scanned from: scan the '
                               'library again' % record['source']['package'])
        entry = entries.get(record.get('key'))
        if entry is None and sky and record['objects'] and all(
                (record['meshes'].get(o.get('mesh')) or {}).get('name', '').startswith('Skybox.') for o in record['objects']):
            entry = dict(placeable=True, actorClass=record['objects'][0]['actorClass'])
        if entry is None:
            raise LibraryError('not-placeable', '%s of %s is not a piece the library lists'
                               % (short(target['actor']), record['source']['package']))
        return record, entry

    def load(self):
        """(index, {key: entry}, {package folded: donor}), read once; LibraryError when it was never scanned."""
        import library
        if self.index is None:
            index = library.load_index(self.cache)
            if index is None:
                raise LibraryError('no-library', 'the library of other maps\' pieces has not been scanned: open the '
                                   'Add panel\'s "All maps" and scan, then build again')
            self.index = (index, {e['key']: e for e in index['entries']},
                          {d['package'].casefold(): d for d in index['donors']})
        return self.index

    def effect(self, target):
        """(the template, its index entry) of an effect or ambient sound of another map, `target` {package, level,
        actor} (library.effect: its export 28 record, its system or waves); LibraryError otherwise. The donor must be
        the file the library was scanned from, and the effect one the library lists as it is now."""
        _, entries, donors = self.load()       # (the viewer's folder on the path first)
        import library
        from projects import ProjectError
        try:
            template = library.effect(self.cache, self.game, dict(package=target['package'], level=target['level'],
                                                                  actor=short(target['actor'])), self.shared)
        except ProjectError as error:
            code = error.extra.get('code')
            if code == 'donor-missing':
                raise LibraryError('donor-missing', 'the game install has no map %s, which %s comes from'
                                   % (target['package'], short(target['actor'])))
            if code == 'effect-missing':
                raise LibraryError('donor-changed', 'the map %s has no effect, ambient sound or lens flare %s any more'
                                   % (target['package'], short(target['actor'])))
            raise LibraryError('not-placeable', error.message)
        known = donors.get(template['source']['package'].casefold())
        if known is None or known['sha256'] != template['source']['sha256']:
            raise LibraryError('donor-changed', 'the map %s is not the file the library was scanned from: scan the '
                               'library again' % template['source']['package'])
        entry = entries.get(template['key'])
        if entry is None or entry.get('family') != template['kind']:
            raise LibraryError('not-placeable', '%s of %s is not an effect, sound or lens flare the library lists'
                               % (short(target['actor']), template['source']['package']))
        return template, entry
