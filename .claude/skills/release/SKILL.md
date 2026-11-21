---
name: release
description: Make a new XCOM Map Workshop release - merge the work into main after the full suites, raise the version, write the release notes and the guide's and README's "New in" lists, build the zip and Setup.exe, run the release smoke tests, then stop and show the user the notes; only after the user confirms, push main, publish it as a GitHub release of the repository, check it, and give a short Discord-formatted summary. Use when the user asks to make, prepare, cut or publish a release, a patch release or a new version.
---

# Make a release

A release is the editor bundled with its own Python, as `XCOM-Map-Workshop-<version>-Setup.exe` and
`XCOM-Map-Workshop-<version>.zip`. It is built by [make_release.py](../../../tools/release/make_release.py) and
published as a GitHub release of this repository, `ruskyandrei/xcom-map-workshop`, which is public. The release's tag
sits on the commit it was built from, so main is pushed before the release is created.

## Rules

- **Stop before publishing.** Steps 1 to 8 make and check the release. Then show the user the release notes in full
  and wait for them to confirm. Publishing is outward-facing: tell them that, and never publish without their yes in
  this conversation. Pushing main is part of publishing, so it waits too.
- **Patch number by default** (0.5.1 → 0.5.2). Raise the minor or major number only when the user asks for it.
- **Release from main.** If the work is on another branch, its full suites must pass on that branch first, and then
  it is merged into main as a fast-forward. If the user didn't say to merge it, ask first.
- **Build into `dist/release`.** Never build in the scratchpad: the bundled Python's paths go past Windows' 260
  characters there. `dist/` is ignored by Git. A trial build in a worktree in a deep folder (an agent's, under
  `.claude/worktrees`) goes to `dist/rf`: a longer name passes 260 characters there too.
- **The notes say what is true.**
  - Check each "works" or "fixed" claim against its source: the experiment notes, the findings register,
    and [missions.py](../../../tools/viewer/missions.py)'s `KINDS` states.
  - Call nothing untried or not played: what ships is usable, tried or not (the user, 16 November 2026). Known
    problems are said as what happens in the game.
- Keep each file's line endings (`.gitattributes`: `* -text`). The notes, guide and README use LF.
- The repository is public: the notes, the ledger and the commit hold no name, account or folder of one computer
  (`python tools/run_tests.py repo` checks the files).
- Keep the change ledger ([CHANGELOG.md](../../../CHANGELOG.md)), one file per entry in `changelog/entries/`: one entry for making the release, one for
  publishing it, each committed with its files.
- Only test servers on ports 8790 to 8799, stopped when done. Never touch 8768.
- If you're asked to change only the notes after the build, leave the zip and installer as they are: the notes aren't
  inside them. If the guide, the README or code changes, the release must be built again, which gives new SHA-256s.
- Follow the user's global rule: `wrap_up` gets a recap only, and questions go in the reply.

## Steps

1. **Find where things stand.**
   - `git status`, the branch, and how far main is ahead of `origin/main`.
   - The last release: `gh release list --repo ruskyandrei/xcom-map-workshop --limit 3`,
     [version.py](../../../tools/viewer/version.py), and `tools/release/notes/`.
   - What changed since: the ledger's entry files in `changelog/entries/` (the last release gathered everything
     before them; `python tools/release/gather_changelog.py --list` prints them newest first), the
     "### Release <last> published" entry among them, and
     `git log --oneline origin/main..<branch>`.
2. **Run every suite on the branch being released**, in the background (about eleven minutes):
   `python tools/run_tests.py`. With every suite it also checks the tile grid of every map the editor lists
   (`tools/upk/tests/test_game_grid.py`, two of those minutes), so a new install or DLC is covered.
   - All must pass. If one fails, stop and report it with its traceback; its logs folder is printed.
   - When they pass: `git checkout main`, then `git merge --ff-only <branch>`.
3. **Raise the version** in [version.py](../../../tools/viewer/version.py). Then search `tools` for the old version
   string; nothing else should hold it, apart from the earlier notes and the guide's older "New in" tables.
4. **Write the notes**, `tools/release/notes/<version>.md`.
   - Copy the previous file's structure: the preview line, Download, **Upgrading from <last>**, New features, Changes,
     Bugs fixed, Known limits, Checksums.
   - Write for testers: what they can do now and where in the editor it is. Leave out code names, file names, finding
     IDs and EXP numbers.
   - **Upgrading:**
     - Did the export number change? Compare `EXPORT_VERSION` in [export.py](../../../tools/viewer/export.py) with
       the last release's (`git show <last release commit>:tools/viewer/export.py | grep "^EXPORT_VERSION"`; the
       commit is in the last "Release <last>" ledger entry). If it changed, every map is read again on its first
       open.
     - Can the last release still open what this one saves? Compare the project and prefab checks in
       [project.js](../../../tools/viewer/web/project.js) and [prefabs.py](../../../tools/viewer/prefabs.py) with
       the last release's commit (`git show <commit>:<path>`).
   - **Known limits:** four at most, the most important, each said as what happens in the game (no list of what
     isn't played: see the rules). Read [KNOWN-BUGS.md](../../../KNOWN-BUGS.md) for the open bugs and take any a
     tester is likely to meet, with its workaround. Ask for reports through **Save a bug report** in the Build window.
   - **Checksums:** leave `SETUP_SHA` and `ZIP_SHA` placeholders until step 7.
5. **The "New in" lists.** These go inside the release.
   - [guide.html](../../../tools/release/guide/guide.html)'s "New in this version": add a `New in <version>` table
     above the last one, each row linking to its section (`id=` anchors), and update the sentence above the tables.
   - [GETTING-STARTED.md](../../../tools/release/GETTING-STARTED.md): add a "New in <version>:" list above the last
     one.
   - Then run `python tools/run_tests.py release viewer -k guide`.
6. **Build:** `python tools/release/make_release.py --out dist/release`. It takes about three minutes and prints
   each file's size and SHA-256. (In an agent's worktree: `--out dist/rf`, and `smoke_release.py --dist dist/rf`.)
7. **Smoke tests:** `python tools/release/smoke_release.py`. All steps must print PASS.
   - It checks the files, then reads the zip back: the version, the README, the guide's table, and every file of ours
     against the repository.
   - Then it unpacks the zip to `dist/smoke-<version>` and starts it with its own Python on port 8795, with scratch
     projects and builds and `--dry-play`. It checks `/setup.json`, the page and the map list.
   - In headless Edge it opens URB_Bar, checks that the help names the version and that the page logs no errors, and
     runs `browser_smoke.py --only light-grid,text-select`.
   - Finally it stops the server and deletes the folder.
   - `--map <id>` opens another map, ready in the cache: use it for a map whose fix is in this release. `--only`
     changes the browser checks. `--keep` keeps the folder and its `server.log` when something fails.
   - Put the SHA-256s it prints into the notes' Checksums, and confirm them with `sha256sum dist/release/*<version>*`.
   - It doesn't run the installer. Say so in the report.
8. **Ledger and commit.**
   - Add a "### Release <version>: <headline features>" entry. It says what changed in the version, notes, guide and
     README; the files with their sizes and SHA-256s; each suite's count; the smoke results; "Not published (ask
     first)"; and the known gaps.
   - Gather the ledger: `python tools/release/gather_changelog.py` moves every entry file, this one included, into
     the month's file under its day. Then `python tools/run_tests.py repo release` (the month file's links must
     resolve).
   - Commit it on main with the version, notes, guide, README and the gathered ledger. Don't push.
9. **Stop and show the notes.**
   - Put the whole notes file in the reply, as it will be published. Under it give the two files with their sizes
     and SHA-256s, the suites and smoke results, and what wasn't checked (the installer, anything not played).
   - Ask whether to publish. Wait. If the user asks for changes to the notes, make them, commit them with a short
     ledger entry, show the changed part, and ask again.
10. **Publish**, only after the user's yes.
    - `git push origin main`, and check that `git rev-parse origin/main` is the commit the release was built from.
    - Then:
      `gh release create v<version> dist/release/XCOM-Map-Workshop-<version>-Setup.exe dist/release/XCOM-Map-Workshop-<version>.zip --repo ruskyandrei/xcom-map-workshop --title "XCOM Map Workshop <version> (preview)" --notes-file tools/release/notes/<version>.md --target main --latest`
11. **Check what was published.**
    - Each file's size and digest: `gh release view v<version> --repo ruskyandrei/xcom-map-workshop --json assets --jq '.assets[] | "\(.size) \(.digest) \(.name)"'`.
      Both must equal the local ones.
    - `gh api repos/ruskyandrei/xcom-map-workshop/releases/latest --jq .tag_name` must name the new version.
    - Both `https://github.com/ruskyandrei/xcom-map-workshop/releases/latest/download/<file>` links must answer 200 to
      `curl -s -o /dev/null -L -w "%{http_code}"`.
    - The published notes (`--json body --jq .body`) must equal the file. Allow for one trailing blank line.
12. **Ledger, commit, push.** Add a "### Release <version> published" entry: the go-ahead in the user's words, the
    link, and what step 11 found. Commit it and push main.
13. **The Discord summary.** End the reply with it, in a fenced code block so it copies as is (template below).

## The Discord summary

Short, for the LW Rebalance Discord's editor channel.

- Under 2,000 characters: Discord's limit for one message.
- Discord's markdown: `**bold**`, `-` bullets, and the link in `<...>` so Discord shows no preview card.
- No headings over two words, and no tables.
- Draw it from the notes, keeping the features players will notice most. Each bullet is one line: the feature in
  bold, then what it does for them.
- Add the upgrade warning only if there is one that matters (maps read again, files the last version can't open).

```
**XCOM Map Workshop <version> is out** 🎉
<https://github.com/ruskyandrei/xcom-map-workshop/releases/tag/v<version>>

**New**
- **<feature>:** <what it does for the player, one line>
- ...

**Fixed**
- <bug, as the player saw it>
- ...

⚠️ <the upgrade note that matters, if any>
Please report problems with **Save a bug report** from the Build window.
```
