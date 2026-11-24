### A prefab saved by an earlier editor is placed as it is

Placing a prefab from the Prefabs tab sends the file as it is stored to `POST /prefabs/size`, and to
`POST /prefabs/recover-sources` when one of its pieces needs finding again. Both ran the check a save runs, which
takes only the schema the server writes. So every prefab saved before the prefab schema last went up (5, on
23 November) was refused with "This page is older than the editor's server … Reload the page and save again".
Reloading didn't help, because the old thing was the file, not the page. Opening it in the prefab editor and saving
it again was the only way round. 0.7.0 did the same to prefabs saved before schema 4. Reported on Discord ("Old
prefabs can't be loaded in new versions of the editor").

- [prefabs.py](../../tools/viewer/prefabs.py): `PrefabStore.validate` takes `writing` (true by default, as for a
  save). When it is false, the document is checked whole at any schema the server reads.
- [viewer.py](../../tools/viewer/viewer.py): the two routes call it with `writing=False`. A save of an older schema
  is still refused, because a page older than the server would drop the newer fields. A schema the editor doesn't
  read is refused on placing too, as before ("A newer editor is needed to open it").
- [editor-contracts.md](../../research/editor-contracts.md), section 4: only a save is refused at an older number.

Checked: [test_prefab_builder.py](../../tools/viewer/tests/test_prefab_builder.py)'s
`test_an_earlier_editors_prefab_is_placed_as_it_is` sends prefabs of schemas 1 to 4 to both routes, then checks
that a save of schema 4 and a placing of schema 99 are still refused. Without the fix it fails with the message
from the report. The `viewer` and `repo` suites pass. Not checked in the browser: the page didn't change, only the
server's answer to it.
