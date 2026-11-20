### Release tooling ships only what Git tracks, checks downloads first; the repository check sees more forms

Review finding 60, apart from detecting a running editor during an upgrade, which needs the server's side and comes
with the server changes.

- [make_release.py](../../tools/release/make_release.py):
  - The page is copied from the files Git tracks in `tools/viewer/web`, plus the three.js files
    [setup_vendor.py](../../tools/viewer/setup_vendor.py) pins. An untracked file there no longer ships.
  - Uncommitted changes under `tools/` get a warning, since the release takes the files as they are on disk.
  - A download is checked against its pin before it is kept, and a damaged cached file is fetched again.
  - `upk/map_inventory.py` no longer ships: nothing shipped runs it.
  - The notices read three.js's version from `setup_vendor.py`, which now writes it in one place.
- [tools/requirements-dev.txt](../../tools/requirements-dev.txt) names Playwright, pinned, for the browser checks,
  the guide's pictures and the release smoke. The [README](../../README.md) says so.
- [test_repo.py](../../tools/repo/tests/test_repo.py) now catches:
  - a drive path whose first folder starts with a digit or `_`;
  - the allowed folders matched whole (a prefix such as `Games…` no longer passes);
  - Git Bash and WSL profile folders (`/c/Users/<name>`, `/mnt/c/Users/<name>`, `/home/<name>`);
  - network paths with a host that isn't a placeholder;
  - the running account's name, and the words of an optional ignored `private/repo-denylist.txt`;
  - the pictures' metadata (PNG text, WebP EXIF and XMP, JPEG segments);
  - links into a folder that holds no file Git has.
  A new test shows each form caught and each allowed form passed.
- Checked: the release and repo suites pass. Two new release tests cover a download refused before it is kept, a
  damaged cache file, and an untracked page file left out.
