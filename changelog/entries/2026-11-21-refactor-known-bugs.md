### Four bugs found during the refactor's last stage go into the known bug register

Editor refactor, stage G1 (steps 3 and 4). A review of the code the refactor left as it was (the server, the
exporter, the installs, the package readers) and the browser checks found four bugs a user can meet. None is fixed
here; each is in [KNOWN-BUGS.md](../../KNOWN-BUGS.md) with what a user sees and a workaround:

- **KB-8:** with a piece selected, the Map grid's panel opens under the Selected piece panel, which covers its Done.
- **KB-9:** a damaged or cut-short map-picture package in the install stops the Project manager's list (the package
  reader stops with an error the picture code does not expect).
- **KB-10:** saving a project, a prefab's picture, the library or a build record can fail while another program holds
  the file for a moment (only the install's records retry).
- **KB-11:** a hand-edited `DefaultMaps.ini` record with spaces around `=` is found but not taken out by a Replace
  build (two readers of the records' fields that differ).

The update-guide skill ([SKILL.md](../../.claude/skills/update-guide/SKILL.md)) names test_api.js as the maker of
`window.viewer`, which app.js no longer holds.

Checked: each cause read in the code (KB-9: `pictures._base_index` and `base_library` catch only `OSError`,
`ValueError`, `KeyError`, while the package header reader raises `struct.error` and `IndexError`; KB-10:
`projects._write` and the like try once; KB-11: `maplist.field` against `mapsini.field`); KB-8 seen by the browser
check that found it. The repo suite passes. Not checked: KB-9 to KB-11 were not made to happen.
