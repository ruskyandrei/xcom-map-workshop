---
name: update-guide
description: Bring the XCOM Map Workshop user guide up to date with the editor - read the whole guide against the editor and the change ledger, fix what has fallen behind, add sections for new features with numbered screenshots made by take_shots.py on a test server, retake the pictures whose part of the editor changed, check every picture and the page, commit, and on the user's word push main so the guide page republishes. Use when the user asks to update, refresh, go over or republish the guide, its screenshots or pictures, or to document new features in it.
---

# Update the user guide

The guide is one HTML file, [guide.html](../../../tools/release/guide/guide.html), with its pictures in
[shots/](../../../tools/release/guide/shots). [take_shots.py](../../../tools/release/guide/take_shots.py) makes the
pictures by driving the editor in headless Edge on a test server, each with numbered marks that the guide's legends
explain. [guide.py](../../../tools/viewer/guide.py) makes it one page with the pictures inside: the release carries
that page, the editor serves it at `/guide.html`, and the
[guide workflow](../../../.github/workflows/guide.yml) publishes it at <https://ruskyandrei.github.io/xcom-map-workshop/>
whenever a push to main changes the guide, its pictures, `guide.py` or the version.

This skill is the guide alone. The guide's and README's "New in" tables belong to the
[release skill](../release/SKILL.md), which writes them for each version.

## Rules

- **Say what is true of the editor as it is.** Check each sentence you write against the code and the page, not
  against the plan or an earlier version of the guide.
- **Nothing is called untried, not played or "known to work"** (the user, 16 November 2026: what ships is usable,
  tried or not). Say what happens. `test_guide.py` fails on the usual words; still read for the rest ("only X has
  been played", lists of what was played).
- **The pictures are public.** No folder, name or account of this computer may show in one. `typical()` in
  take_shots.py swaps the server's answers that name folders (`play.json`, `projects.json`, `squad.json`,
  `manager.json`) for a usual install's. A new shot whose page shows a folder from another answer gets a route
  there too. Look at every picture before it goes in.
- **Keep the pictures that haven't changed.** A retaken picture of the same thing differs only in what stands
  behind see-through panels, and every new picture adds to the repository's history. Replace a picture only when its
  part of the editor changed.
- **Only test servers on ports 8790 to 8799**, with scratch projects, builds and squad, stopped when done
  (PowerShell: `Get-NetTCPConnection -LocalPort 8790 -State Listen`, then `Stop-Process` on its owner). Never touch
  8768.
- **A fresh scratch folder for each full run** (`.scratch/guide-<n>/`, which Git ignores). The demo project is saved
  under a fixed name, so the projects folder must start empty. Start a new folder rather than deleting the old one.
- Keep each file's line endings (`.gitattributes`: `* -text`): guide.html, take_shots.py and the ledger use LF.
  Python's `read_text`/`write_text` change them unless given `newline=''`.
- Keep the change ledger ([CHANGELOG.md](../../../CHANGELOG.md)): one entry, committed with the guide, its pictures
  and take_shots.py.
- **Push only on the user's word.** Pushing main republishes the guide page; "republish" or "push" in the request is
  that word. Without it, commit and say the page isn't updated yet.
- Follow the user's global rule: `wrap_up` gets a recap only, and questions go in the reply.

## Steps

1. **Find what changed since the guide was last gone over.**
   - The last ledger entry about the guide (`grep -n "guide" CHANGELOG.md`), and every entry above it: each new or
     changed thing a user sees is a candidate.
   - `git log --oneline -- tools/release/guide/` against `git log --oneline -- tools/viewer/web/`: page changes
     since the pictures were taken.
2. **Read the whole guide** against the editor. It is about 2,100 lines: read it all, not just the sections you
   expect to change.
   - The controls a section numbers against the page: `tools/viewer/web/index.html` (the header, the tool strip
     `#rail`, the Project menu `#projectMenu`, the piece panel `#inspector`, each dialog), and what the code says
     today.
   - List what is stale, what is missing (a new feature with no section or picture), what says untried, and where
     numbering no longer matches a picture.
   - Check a claim you are unsure of in the code, or on the test server in the browser.
3. **Start a test server** on a fresh scratch folder (in the background):
   `python tools/viewer/viewer.py serve --port 8790 --no-open --projects .scratch/guide-<n>/projects --builds .scratch/guide-<n>/builds --squad .scratch/guide-<n>/test-squad.json`.
   It serves the cache setting's maps. The Bar must be prepared there; a shot that opens another map reads it from
   the game on its first open.
4. **Explore what the new pictures will show** on that server in the browser pane, at 1440 × 900
   (`resize_window`): the element ids, the state that makes a clear picture (a piece with several of its kind, a
   flag that changes), what each mark should point at. `viewer.*` in the page (app.js's `window.viewer`) has hooks
   for selecting, the camera, the views and mission objects.
5. **Script the shots** in take_shots.py, following the shots there:
   - a method per shot (its name, with `-` for `_`, in `ORDER`; shots that build, save projects or open another
     map go last);
   - marks: `dict(n, sel=…)` or `rect=[x, y, w, h]`, with `side`, `gap`, `at`; `panel_rows(panel, rows)` puts them
     at a panel's edge, clear of its text; `frame=True` draws a dashed box;
   - a clip round the controls with `around(...)`, or the whole window with `resize=0.75`;
   - undo every edit a shot makes, and put back the view, floors and selection, so the next shot starts as before;
   - a shot that needs more room than 900 pixels sets a taller window for itself and puts it back (the piece panel
     does);
   - the module's docstring says what the run needs and does.
6. **Take the shots into the scratch folder**, never straight into `shots/`:
   `python tools/release/guide/take_shots.py --out .scratch/guide-<n>/shots --only <names>` while you work on them
   (each run saves the demo project again, so restart on a fresh folder when its name is taken), then every shot in
   one run on a fresh folder. The full run takes about five minutes: run it in the background.
7. **Look at every new and retaken picture** (Read the `.webp`): the marks on the right controls and clear of text,
   nothing cut off at the window's edge, nothing personal, the state the legend describes. Fix and take it again.
8. **Choose what replaces what.**
   - `python tools/release/guide/guide_tools.py compare .scratch/guide-<n>/shots`: NEW, SIZE or how far each differs.
   - `guide_tools.py sheet <png> .scratch/guide-<n>/shots <names>` puts the guide's and the new picture side by side
     for the ones in doubt.
   - Copy into `tools/release/guide/shots/` the new pictures and those whose part of the editor changed; leave the
     rest.
9. **Edit the guide.**
   - A new picture: `<figure>` beside its legend in `<div class="split">` for a panel, or `<figure class="zoom">`
     (click to enlarge) with the legend under it for a wide one. The legend's numbers are the marks', in order.
   - Each `<img>` has `width` and `height` at half the picture's pixels (the shots are taken at scale 2) and an
     `alt` saying what it shows. Keep a picture out of a list item: it is squeezed there.
   - A renumbered picture: renumber its legend and every "item 7"-style mention.
   - New sections get an `id`; links use `href="#id"`.
10. **Check.**
    - `python tools/run_tests.py viewer -k guide` (links, picture sizes, every picture used, no untried words),
      `release` and `repo`.
    - `python tools/release/guide/guide_tools.py look .scratch/guide-<n>/look "<alt start>" "#<id>"`: the page as it
      is published, photographed where each changed section is. Read those pictures: layout, legends, text.
    - Stop the test server.
11. **Ledger and commit.** One entry: what was stale and how it reads now, the new and retaken pictures, the
    take_shots.py changes, how it was checked, and that the last release's zip still has the earlier guide.
12. **Push and check the page**, when the user said to republish or push.
    - `git push origin main`.
    - `gh run list --repo ruskyandrei/xcom-map-workshop --workflow guide.yml --limit 1`, then
      `gh run watch <id> --repo ruskyandrei/xcom-map-workshop --exit-status`.
    - The live page equals the local one: `curl -sL https://ruskyandrei.github.io/xcom-map-workshop/` against
      `python -c "import guide,sys; sys.stdout.buffer.write(guide.inline())"` run in `tools/viewer`.
13. **Report**: what changed in the text, which pictures are new or retaken and which were kept, the checks, the
    page's state, and anything the run left in the editor's cache (a map read for a shot).
