### A project file the editor can't read is a row with its reason, and the others still list

Review finding 9. A file of the project schema whose `source` was a string made the whole listing fail, so the healthy
projects beside it could not be listed, and the page threw on a project whose edits were not lists.

- [projects.py](../../tools/viewer/projects.py) `shape_problem` checks the least the listing, the page and the Build
  read, the same for schema 1 to 4: the name is text, the base map and its SHA-256 are named, the edits (overrides,
  added, groups, area light bindings, buildings) are lists of records when present, and the revision is a whole
  number. The store's check runs it.
  - The listing gives such a file a row of its own with the reason, which the Load dialog and the project manager
    show greyed out with the reason in the tooltip.
  - Opening, the Build's capture and a save over it are refused with the same words.
  - A copy that can be read is the project before a newer copy that can't.
  - Edits that name pieces the map lacks are carried as before.
- [app.js](../../tools/viewer/web/app.js) `openProject` no longer throws on edits that are not lists: such a document
  is refused with a banner instead of being opened without them and saved back so.
- The [contract](../../research/editor-contracts.md) says so.
- Checked:
  - [test_projects.py](../../tools/viewer/tests/test_projects.py): a mixed folder (a string base map, an object of
    overrides, numbers as added pieces, a revision in text, no SHA-256, a name that is a list) beside a healthy
    project and a schema-1 one, through list, load and capture, and a broken newer copy;
  - [test_manager.py](../../tools/viewer/tests/test_manager.py): the project manager's listing of a mixed folder.
