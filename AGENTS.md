# Working in this repository (for any coding agent: Codex, Claude Code)

- **Keep the change ledger.** Each change adds one entry file to [changelog/entries](changelog/entries/README.md) in
  the same commit: `<YYYY-MM-DD>-<what>.md`, starting with a `### <title>` line. Say what changed, where (link the
  files, relative to the entry file: `../../tools/...`), how it was checked, and any known gaps. Never edit another
  entry's file or a month file for a new change; each release gathers the entries into the month's file
  ([CHANGELOG.md](CHANGELOG.md) is the index). Experiment results still go in `research/experiments/` and the
  findings register; the ledger records changes to the tools and documents.
- **Keep the known bug register.** A bug in the editor or its builds that is found and left unfixed (a failed game
  check, a report, a review) gets an entry in [KNOWN-BUGS.md](KNOWN-BUGS.md): what a user sees, since when, a
  workaround, the cause in a line and its finding. The commit that merges its fix takes it out, and says so in its
  ledger entry.
- **Commit whenever a piece of work is done**, without waiting to be asked: a fix, a feature or a stage of a plan,
  once its tests pass, on the branch it was done on, with its ledger entry in the same commit. Leave nothing finished
  lying uncommitted at the end of a turn. Push only when the user asks.
- **Clean up when work is merged.** In the turn that merges a branch into main, remove its worktree
  (`git worktree remove`) and delete the branch (`git branch -d`, which refuses a branch that is not merged). The
  same holds for the worktrees subagents make under `.claude/worktrees`: whoever merges an agent's branch removes
  that worktree and that branch, its resume checkpoint going with it. A worktree or branch stays only while its work
  is not merged, or when the user asks to keep it. Never force-delete a branch that is not merged without the
  user's word.
- Line endings are kept byte for byte (`.gitattributes`: `* -text`). Keep each file's existing endings; new files use
  LF. Python's `write_text` on Windows writes CRLF unless given `newline=""` or `newline="\n"`.
- **One main viewer/editor server, on port 8768.** It serves the whole cache library
  (`python tools/viewer/viewer.py serve`, the cache setting's folder, 8768 being the default port), and it is the one the
  user keeps open. [xcom_editor.cmd](xcom_editor.cmd) starts it, or restarts it if it is running
  (`xcom_editor.cmd restart` does the same; `xcom_editor.cmd start` leaves a running one alone), and
  `xcom_editor.cmd status` reports what holds the port.
  Deploy updates there and nowhere else:
  - web changes (`tools/viewer/web/`) show after a browser reload;
  - a re-export, new map or server change needs that server restarted, because it picks its exports when it starts.
    If it is the user's own process and you can't restart it, ask them to run `xcom_editor.cmd` again.

  Never start a second server on 8768, and leave no other long-running viewer servers behind.
- **Test servers** use ports 8790–8799. Start one for a check, point it at what you are testing (including scratch
  caches), and stop it when the check is done.
- **The editor's Snap setting governs movement, sizing and rotation on every axis**, including vertical edits.
  With Snap off, placement, drag handles, gizmos and numeric edits must allow continuous values. With Snap on,
  they use the selected linear or angular step. Apply the same rule to map and prefab editing. A tool may offer
  an explicit alignment command or preset. Never silently round an edit to a unit, tile, storey or quarter turn.
  If the game cannot represent an edit, explain the specific limitation and preserve the authored value.
- **No folder of one computer in anything checked in.** Code takes folders from the settings
  (`Documents\XCOM Map Workshop\settings.json`: `python tools/viewer/viewer.py settings`), from arguments, or relative
  to the repository; docs and usage lines write placeholders such as `<LWR install>`, `<cache>`, `<udk>` or `<lab>`.
  Experiment notes, the findings register and the change ledger write placeholders too.
- **This repository is public.** Nothing that identifies a person or a computer goes into it: no name, account,
  folder, hardware or anyone's Discord name. What cannot be public lives in `private/`, which Git ignores: our diff
  of the unlicensed XComGame stubs, copies of other projects' source files, the Discord feedback list, the plans
  (`private/plans/todo` for the ones not built yet, `private/plans/done` for the ones built or replaced), and every
  picture of an experiment or check (`private/shots/`, where `mark_shots.py` writes). A note says in words what a
  picture showed. The `repo` suite checks this; run it before a commit that adds notes or documents.
- **Run the suites with [tools/run_tests.py](tools/run_tests.py)** (all, or by name; `-k` for some tests). It prints
  each failure with its traceback and keeps the full logs, so a failure never needs a second run to be found. Run a
  test file on its own only through it or `unittest discover`: some test files import their neighbours.
- **New code follows [ARCHITECTURE.md](ARCHITECTURE.md):** where it goes, the rules, the guideline sizes. Read its
  checklist (section 6) before a commit that adds a module, a long function, or a reader or writer of a format. The
  `repo` suite's structure test holds the rules a test can (the page's and the release's imports, the import path,
  the compiler's families); sizes are guidance, listed by `python -B tools/repo/tests/test_structure.py --sizes`.
- **A change to what the editor's user sees or does follows [UI-GUIDELINES.md](UI-GUIDELINES.md):** edit in the 3D
  view with handles and gizmos where that can be done, without crowding it; one way to do a thing, in the stylesheet's
  parts; short panels, and buttons that look like buttons. For a larger change (a new window, panel or view, or one
  laid out anew) show the user a few mock designs first and build the one chosen (its section 4).
- See [README.md](README.md) for the layout and the setup this depends on.
