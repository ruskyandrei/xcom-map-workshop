### The game folder's backups and the ledger's history keep the newest 20 and 200

Review finding 49, the game folder's part. Each play made two backup folders in `<game>\XCOM Map Workshop\backups`
(up to three ini copies each) and two history entries in `installs.json`, and nothing ever took them away.
[installs.write_ledger](../../tools/viewer/installs.py) now keeps the newest `KEEP_BACKUPS` = 20 backups (about ten
plays' worth) and `KEEP_HISTORY` = 200 history entries, and deletes the older backup folders.

Nothing still needed is deleted:
- a backup folder that keeps a lab file to go back (`labFiles`);
- one an interrupted change's roll-back kept (`interrupted-*`, the only copy of a config file's text from before);
- no folder at all while a change is under way or a stopped one waits (its journal, or the prefab test's), so a
  roll-back never brings back a ledger naming a folder that is gone.

A folder that can't be deleted stays listed.

Checked: [test_install_recovery.py](../../tools/viewer/tests/test_install_recovery.py)'s `Pruning` writes a ledger
with 30 backups and 250 history entries, an old backup holding a lab file, and an old roll-back's folder. The newest
20 and the two needed ones stay, on disk and in the ledger (the caller's dict too), and the history keeps its newest
200. With a change's journal waiting, no folder goes. The build folders' part of finding 49 (`.work`, the piece
cache) is not in this change.
