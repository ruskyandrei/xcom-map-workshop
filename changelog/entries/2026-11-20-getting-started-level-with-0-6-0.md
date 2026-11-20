### The release's getting-started page is level with 0.6.0

Review finding 64, the release README's part. [GETTING-STARTED.md](../../tools/release/GETTING-STARTED.md):

- **Game maps… → Undo everything** and **Test squad setup…** are in the Game menu on Play's arrow, where 0.6.0
  moved them (it said the Project menu and Settings).
- The test battle can be saved with **Enable saving**. The page had said it can't be saved.
- Mission objects' markers come from the Normal view's **Spawn points and objectives** switch, not the old View
  options entry. They are listed under what builds (moved, not copied or deleted), no longer as "not editable".
- **What builds** names 0.6.0's additions: made walls, floors and ground with looks and damage, effects, sounds and
  flares, spawn points, missions, the map picture and map packs.
- The opening no longer says how few maps a feature was played on.
- Upgrading: close the editor first, since Setup replaces the files a running editor holds open.
- Checked: release, repo and `viewer -k guide` pass. Each menu location was read from `index.html`'s Game menu and
  Normal view flyout.
