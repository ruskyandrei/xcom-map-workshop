### Two windows saving the favourites at once no longer lose one's change

Review finding 21, in [library.save_state](../../tools/viewer/library.py).

- The revision check and the file's replacement are one step under a lock on `library.json.lock` beside the file (the
  operating system's, so it holds across threads and across servers). Two saves from the same revision get revision 1
  and a 409 with that revision; the page already reloads and applies its change again on a 409. Before, both could
  read revision 0 and both be told revision 1, and the first star was lost.
- The temporary file has a name of its own for each save, so two saves never write the same one (a fixed name could
  also fail the replace on Windows), and it is removed if the replace fails.
- Checked: [test_library.py](../../tools/viewer/tests/test_library.py) holds two saves (a star and a recently used
  piece) until both have read revision 0: one wins with revision 1, the other gets a 409 with revision 1, the file
  holds the winner's change, the merged save gets revision 2, and no temporary file is left.
