### Save as copies the map picture with the save; reading a project changes no file

Review finding 8, the picture half of finding 45, and the picture hashing of finding 50.

- **Save as** (finding 8). The page saved the new project first, then sent the picture back through the upload, which
  writes it again clean: a picture kept byte for byte (one sent beside a project file) came back under another hash,
  and the new document named a picture its project didn't keep. Nothing waited for the copy either.
  - Now the save carries `pictureFrom`, the project saved from ([app.js](../../tools/viewer/web/app.js) `saveProject`,
    [project.js](../../tools/viewer/web/project.js)).
  - The store copies the kept file byte for byte before it writes the document
    ([projects.py](../../tools/viewer/projects.py), [pictures.py](../../tools/viewer/pictures.py) `copy_picture`).
    A replaced project's own picture is kept for its saved revision.
  - A copy that fails saves nothing and says why. A picture the project saved from keeps no more is said in a
    banner, and the document is saved naming it, as before.
  - The page's copy through the upload is gone ([map_picture.js](../../tools/viewer/web/map_picture.js)).
- **Reads change nothing** (finding 45). Opening a project and the project manager's listing took a picture sent
  beside the project's file into `.workshop` and deleted the file.
  - Now `picture_file` finds such a picture where it lies, for the dialog, the manager, a pack and the Build.
  - The project's next save takes it in, so a rename keeps it ([viewer.py](../../tools/viewer/viewer.py),
    [manager.py](../../tools/viewer/manager.py)).
- **Hashing** (finding 50). A kept picture's SHA-256 is kept by its size and modified time, so the listing hashes it
  again only when it changed.
- Checked: [test_pictures.py](../../tools/viewer/tests/test_pictures.py) covers:
  - a sidecar found by reading and taken in by a renaming save;
  - Save as from a sidecar compressed unlike `clean()`, and from an ordinary upload over a project with a picture of
    its own;
  - a copy that fails, and a picture no longer kept;
  - the route's `pictureFrom`, and a GET that leaves the sidecar where it lies;
  - one hash while a picture is unchanged.
