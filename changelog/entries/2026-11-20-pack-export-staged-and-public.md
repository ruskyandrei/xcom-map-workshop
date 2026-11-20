### A map pack holds only the projects it packs, names no folder of this computer, and says why when a card line or the zip fails

Review findings 13, 14, 44 (its pack items) and 46 (its pack and Game maps items), in
[manager.py](../../tools/viewer/manager.py)'s pack export, [pack_card.py](../../tools/upk/pack_card.py) and
[gamemaps.py](../../tools/viewer/gamemaps.py).

- **A project left out leaves nothing in the pack (13).** A build's files went into the zip's list before a later
  conflict, such as a file of another build's name with other bytes, moved its project to `skipped`. The skipped
  map's file was then shipped. Each project's files, card lines and borrowed picture are now staged on their own and
  join the pack only once the whole project has passed.
- **No folder of this computer in a pack (14).** Each build's `packages/<variant>/manifest.json` used to be the
  build's own, with `project.file`, `source.file`, `work`, the stages' paths and each donor's file. It is now made
  from an explicit list of fields (`PUBLIC_MANIFEST`, and the project's, source's and donors' public ones): names,
  hashes, the project's id and revision. Then, as a last guard, every text the pack writes is scrubbed of the folders
  the editor knows. That covers the README files, `pack.json` (an error's words in a warning) and the public
  manifests, and the folders are the builds, projects, cache, game installs, temporary folder and home, each put
  back as a placeholder such as `<builds>`. The build's own manifest in the builds folder is unchanged, and the
  editor projects, when asked for, still go byte for byte as saved.
- **A card line the card can't hold (44).**
  - `InitialChance=abc` on one map's line raised out of the request with no answer. The card's lines are now typed
    for each project inside its own check, so such a project is left out, with why. The pack's card itself answers
    a 409 with why.
  - `pack_card` now refuses with a `CardError` a number it can't hold (`1e300`, a rotator of `inf`, a huge
    `ShipType`). It also refuses `StreamingMaps[n]` above slot 99 (`StreamingMaps[100000]` made a 12 MB card), and a
    `StreamingMaps` with no slot, which was taken a character or a key at a time.
  - A `DynamicAliens` with no slot is slot 0, as the ini reads it.
- **A zip that fails (46)** answers a 500 with why, and its `.zip.tmp` is deleted. Game maps' `POST /gamemaps/use`
  with records that are no ids (a list, an object) is a 400, where `set()` raised.

Checked:
- [test_pack_export.py](../../tools/viewer/tests/test_pack_export.py) covers each case. The left-out project has its
  conflict last in its manifest, and the zip's entries and hashes, the card and the README must hold only the
  accepted map. The folder check builds with sentinel paths and the test's own folders, then inspects every text and
  JSON member of the zip with the editor projects in it and not. A malformed card line, a failing zip and Game maps'
  bad ids are each covered too. Every case fails on the old code.
- [test_pack_card.py](../../tools/upk/tests/test_pack_card.py) covers each value a card can't hold. The manager and
  pack-script tests pass.
