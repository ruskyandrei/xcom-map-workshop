### Drafts for recovery belong to the page that keeps them; Replace saves over the revision it showed

Review findings 3 and 4, and the waiting change of finding 34.

- **Drafts for recovery** (finding 3). Each page makes an id as it loads, and keeps its unsaved changes in a draft of
  its own: `.workshop\<id>\recovery-<page>.json` in [projects.py](../../tools/viewer/projects.py), for prefabs too
  ([prefabs.py](../../tools/viewer/prefabs.py)). Two tabs on one project keep a draft each.
  - A page deletes only its own draft (on saving, discarding or leaving), or the one it showed the user and the user
    restored or discarded, and that one only while it is still the one shown. A clean tab leaving deletes nothing.
  - A save deletes the saving page's draft only. The `DELETE` route must say whose draft (`?owner=`, plus `savedAt`
    for one shown) ([viewer.py](../../tools/viewer/viewer.py)).
  - A draft based on an older revision than the saved one (another tab saved meanwhile) is kept, answered as stale,
    and the page says so once. Prefabs refused such drafts, and the page dropped the refusal silently.
  - Opening offers the newest draft, with the revision it was made on when that is older and how many more are kept.
    Restoring makes it the page's own. Discard offers the next. A draft that equals the saved state goes.
  - A draft write that fails is said in a banner for projects as for prefabs, once until a write goes through.
  - An owner-less `recovery.json` from before is listed and goes only when shown and discarded or restored.
- **Replace** (finding 4). Save as onto another project saves over the revision the confirmation showed
  ([app.js](../../tools/viewer/web/app.js) `saveProject`). One saved since is asked about again, with its revision
  now ([project_files.js](../../tools/viewer/web/project_files.js)). A prefab file imported over one of the library's
  names the revision its question showed (`expectedRevision`): a bare replace is refused, and one saved since is a
  clash again, with its new revision ([prefabs.js](../../tools/viewer/web/prefabs.js)).
- **A failed save keeps the waiting change** (finding 34). A map or prefab change waiting for the Save dialog waits
  through a refused save: the next save that succeeds goes on to it, and Cancel calls it off.
- The [contract](../../research/editor-contracts.md) and the [viewer README](../../tools/viewer/README.md) say how
  drafts are kept now.
- Checked:
  - [test_projects.py](../../tools/viewer/tests/test_projects.py): two pages' drafts, a clean page leaving, saves and
    discards in either order, a stale draft, a draft refused once kept again, owner-less drafts and bad owners, and
    the routes.
  - [test_prefabs.py](../../tools/viewer/tests/test_prefabs.py): the import's revision.
  - [test_prefab_builder.py](../../tools/viewer/tests/test_prefab_builder.py): a prefab's stale draft kept.
  - A new browser check, [browser_documents.py](../../tools/viewer/tests/browser_documents.py), on a test server:
    - two windows: two dirty pages and a clean third, saves and discards in either order, a stale draft and its
      banner, a lost tab's draft restored in another page, a failed draft write and reopening after it;
    - Replace after another window saved the target, and a prefab file replaced after the library's copy changed;
    - a save refused, then a save that goes on to the waiting change.

    It runs on its own or as [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) `--only documents`
    (with `--projects`). The builder check passes as it was.
  - [browser_builder.py](../../tools/viewer/tests/browser_builder.py) names the revision its import replaces.
