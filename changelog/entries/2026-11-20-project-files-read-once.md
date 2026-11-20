### Each project file is read once until it changes; a save that can't be written says why

Review finding 20, and the save half of finding 46.

- **Reads** (finding 20). The project manager's listing read each project four times, the build status read the
  project on every poll (every 2 s), and the queue view and the map names' check read projects again.
  - [projects.py](../../tools/viewer/projects.py) keeps what each file in the folder said, by its modified time,
    size and file id: its id, rank, summary, name, revision and output names. A file is read again only when that
    stamp changes, and a file renamed or changed outside the editor is seen at the next listing.
  - `listing()` gives the [project manager](../../tools/viewer/manager.py) each project read once, its summary made
    from the very document it gives.
  - `cached()` answers the build status ([builds.py](../../tools/viewer/builds.py), two lines) and the queue view's
    name and estimate ([buildqueue.py](../../tools/viewer/buildqueue.py)).
  - `claimed()` gives [outputnames.Claims](../../tools/viewer/outputnames.py) every project's output names.
  - Prefabs' summaries, which validate and measure the whole prefab, are kept the same way.
- Measured on ten projects, with the store before this change and after:
  - a project manager refresh read project files 40 times, now 10 (20 the first time a server lists them);
  - five build status polls read 10 times, now none.
- **Save errors** (finding 46). A save that can't be written (a full disk, a file open in another program, a
  read-only folder) is a ProjectError that says which, so the page shows "Not saved:" with the reason. Before, the
  connection dropped.
  - The temporary file goes, and the revision before stays the project.
  - A draft write says the same. A renamed project whose old file can't be removed is saved, and the page says the
    old file is listed as a copy until it is deleted.
- Checked: [test_projects.py](../../tools/viewer/tests/test_projects.py) counts the reads:
  - a listing, a second listing, the polled lookups, the manager's listing and a load;
  - a file renamed and one changed outside the editor;
  - a full disk, a refused copy of the revision before and a refused draft write.

  The viewer suite's manager, builds, queue, output names, pictures and play tests pass as they were.
