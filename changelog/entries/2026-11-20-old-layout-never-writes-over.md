### A project folder of the old layout never writes over a newer project

Review finding 5. The store moved a folder of the layout before 8 November 2026 (`<id>\project.json`) onto the file
of the same project with no comparison, so a revision-1 backup restored beside a revision-2 library replaced
revision 2.

- [projects.py](../../tools/viewer/projects.py) `_migrate` now ranks the folder's document against the file that
  holds the project, as the listing ranks copies: the higher revision, then the later save, and the file there wins
  a tie. The other is kept beside it as `<name> (kept copy).json` (numbered when taken), which the listing shows as a
  copy of the project. The same bytes twice keep one.
- A previous revision or a draft whose name is taken is kept under a name of its own: a draft as another page's (so
  both are offered), a previous revision as `project.prev (2).json`.
- Each step is one rename, so a stop halfway leaves the folder to finish at the next listing.
- The listing's ranking and the migration's are one function (`_rank`).
- The [contract](../../research/editor-contracts.md) and the [viewer README](../../tools/viewer/README.md) say so.
- Checked: [test_projects.py](../../tools/viewer/tests/test_projects.py) covers both revision orders, equal revisions
  going by the later save, a tie, a second copy, the same bytes twice, drafts and previous revisions beside those
  there, and a stop between the two renames that the next listing finishes.
