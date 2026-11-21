### A tab's own storage through storage.js

Editor follow-ups, stage P3, item 3.20: the two modules that used the browser's `sessionStorage` themselves, each with
its own catch, go through [storage.js](../../tools/viewer/web/storage.js), the page's one home of the browser's storage.
Nothing the editor does changes.

- **[storage.js](../../tools/viewer/web/storage.js)** gets `recallSession`, `rememberSession` and `forgetSession`, the
  tab's own values while it stays open, catching a storage that is missing or blocked as `recall`, `remember` and
  `forget` do (null read, a write dropped).
- **[prefab_test.js](../../tools/viewer/web/prefab_test.js)** keeps and reads the prefab test the tab follows through
  them; **[prepare.js](../../tools/viewer/web/prepare.js)** the map prepared again once in the tab. (Before, a read that
  threw also skipped the write; now the write is tried and dropped: the same outcome.)
- **[one_home_test.mjs](../../tools/viewer/tests/one_home_test.mjs)** also finds `localStorage` and `sessionStorage`
  nowhere but storage.js; it failed on the stage's first commit (prefab_test.js 3, prepare.js 2) and passes now.
  [storage_test.mjs](../../tools/viewer/tests/storage_test.mjs) takes the three, with a blocked and a missing storage.
- [ARCHITECTURE.md](../../ARCHITECTURE.md) ("The page", Modules) names them.

Checked: the node suite and `web_names` clean; browser checks `prepare`, `prepare-routes`, `builder` and `prefab-test`
(whose reload finds the test the tab follows) pass; a probe with URB_Bar answered as outdated: its first open in a tab
prepares it at once, a reload of the tab waits for a click.
