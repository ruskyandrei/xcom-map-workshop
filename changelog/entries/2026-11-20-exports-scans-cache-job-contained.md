### Exports, library scans and the cache job are contained as builds are, and the install waits for them

Review finding 48.

- **Contained**: a map export ([exports.py](../../tools/viewer/exports.py)), a library scan
  ([library.py](../../tools/viewer/library.py)) and "Cache everything"'s pieces process
  ([precache.py](../../tools/viewer/precache.py)) start through `procs.launch`, as builds do: each is a process tree in
  a job object of its own, so Cancel ends the whole tree by its job (never `taskkill` of a bare process id that may
  have been reused), the cache job's workers end with it, and a server that dies takes them with it instead of leaving
  them writing into the cache with no owner. When a process ends, what it left running is ended before its result is
  taken. An export, a scan or the cache job that can't start says so (500 with the reason) instead of failing the
  request.
- **The pieces folders are locked across processes** (`library.donor_lock`: the operating system's lock on
  `<cache>/library/locks/<map>.lock`, `publication.FileLock`). The server's piece requests and the cache job's workers
  write a donor's pieces, effects and drawings under it, and a piece is read again once the lock is held, so the two
  never export the same piece into the same files. Reading a kept piece takes no lock.
- **Temporary files have names of their own** (`library.part_of`): piece, effects and drawing records, the library's
  index (two scans at once no longer write the same `index.json.part`) and thumbnails.
- **Choosing another game install** is refused (409, saying what runs) while a map export, a library scan or the cache
  job runs, as it already was while the build queue runs (`viewer.install_busy`); before, the old runner's job went on
  into the old catalogue beside a new runner that allowed a second. When the server can't load the new install, the
  setting is put back as it was ([gamesetup.py](../../tools/viewer/gamesetup.py)), so the settings file and the server
  agree, and the page is told why.
- Checked: [test_contained_jobs.py](../../tools/viewer/tests/test_contained_jobs.py) (new) cancels an export that
  started a child of its own and sees both processes end, an export that can't start, a donor's lock held by another
  process (409, another donor free, free again once it ends), unique temporary names, the install refused for each of
  the three jobs, and a failed switch putting the setting back. [test_precache.py](../../tools/viewer/tests/test_precache.py)
  checks the stopped cache job is not killed. The viewer suite passes.
- Not done: `builds.stop_process` stays for the code that still uses it (builds.py, which this change does not own);
  nothing here uses it any more.
