# EXP-65: the build queue with real builds, stopped, killed and restarted

Date: 16 November 2026. Status: **passed** (offline: no game was started, nothing was installed). The build queue
plan's stage Q4: the queue (tools/viewer/buildqueue.py) building real projects with the real build.py, its Stop, a
server killed outright mid-build, and a server killed after a package went in but before the queue could write the
result. Each check below says what was seen.

## Set-up

- A test server on port 8791 (`viewer.py serve --port 8791 --no-open --dry-play`) with a scratch projects folder
  (`<scratch>/projects`) and a scratch builds folder (`<scratch>/builds`); the cache and the game install (LWR) from
  the settings, read only. The server was stopped afterwards; nothing else ran on its port.
- Three projects copied from the editor's projects into the scratch folder:
  - **A**, a small edit on URB_Bar (EXP-17's moved pool table: two original pieces moved), which the relight's kept
    pieces (PieceCache) can serve;
  - **B**, a copy-heavy edit on another map (EXP-24's cars at the police station: ten pieces changed, five copies on
    URB_PoliceStation);
  - **C**, A with every edit taken out (it must fail).
- A driver of the queue's routes (envelopes, receipts) and the process checks (procs.tree_alive), kept in the scratch
  folder with the run.

The first attempt at A and B was refused at once, before any costly stage: their output names (from the projects
they were copied from) are held in the game install by files an earlier experiment put there. That is the
Build's name check (output names plan) working on the queue's private snapshots, with the projects folder and the
installs passed explicitly (build.py `--projects`, `--check-game`). For the runs, A and B were given ids, names and
output names of their own, as Save as does (`URB_Bar_Q4Pool_00a4`, `URB_PoliceSt_Q4Cars_00b4`).

Correction, later on 16 November: those files were the lab's own deploys of the same projects' earlier tests (the bake
fixtures' installer and patchtool, EXP-17 and EXP-24), not anyone else's, and the refusal was a fault of the name
check, not a proof of it: [findings register](../findings-register.md) T-40, fixed the same day. The snapshot's name
check against the projects folder still stands (test_build checks it with another project's names).

## Runs

| Run | What was done | What was seen |
| --- | --- | --- |
| 1 | C, A and B queued, cold (no kept pieces) | C failed alone in 0.3 s ("the project changes nothing in the map"); A built in 47 s, B in 63 s, one after another. Both packages verified (installs.read_package: every file's hash), each manifest naming its own attempt. A's relight: "pieces kept from the last build: 0 of 207", 205 kept afterwards; B's: 0 of 224, 213 kept. |
| 2 | A saved again (revision 2), queued, stopped while relighting | The build tree at Stop: build.py, native_copy.py and the relight with six workers (eight processes, conhost apart). After Stop: the queue stopped, A waiting ("Stopped: it starts again on Resume"), no writer record left, nothing but the server running under the server (procs.tree_alive), each of the eight processes gone. A's package was still revision 1's (its build id and hashes as before); no journal left. |
| 3 | A saved again (revision 3), Resume | Built from revision 3, the latest save, as a new attempt: 21 s, "pieces kept from the last build: 205 of 207". Package verified, revision 3. |
| 4 | B saved again (revision 2), queued, the server killed outright (`taskkill /F`) while relighting | Every process of the build ended with the server (its Job Object closed with it): the writer record's tree was empty two seconds later. The queue's file still said running and building, as a crash leaves it. Restarted: the earlier server's writer proved gone and its record dropped, the queue stopped ("The editor stopped while the queue was building. Resume goes on."), B waiting with the reason, the build slot idle (nothing started by itself), B's revision 1 package valid, no journal. Resume built revision 2 in 51 s, 213 of 224 pieces kept. |
| 5 | A saved again (revision 4), queued; once its row was building on disk the queue's file was made read-only; the server killed after the build had put its package in | The queue said it could not be saved (WinError 5) and held. The package in place was revision 4's, of that attempt. Restarted (file writable again): the row became built with `recovered: true`, the queue finished. |

## Timings

A cold full build and a warm one of the same edits (only the revision moved): **A 47 s cold, 21 s warm** (205 of its
207 reached pieces served by the kept pieces); **B 63 s cold, 51 s warm** (213 of 224 kept; its five copies and the
pieces of other maps are always relit). Run 2's interrupted attempt is not counted: a part of a build against a whole
one is no speed measure. The queue's own overhead (capture, snapshot, verification) was under a second a row.

## Findings

No new game or package finding. Two toolchain findings came out of building this stage and are in the
[findings register](../findings-register.md): T-38 (a leftover process holding a build's output pipe kept the
server's build running) and T-39 (a Job Object's count of active processes drops a moment before they have ended).

## Not covered

No shots were taken (nothing was seen in the game). Play in game, Install and the map pack while the queue builds were
checked by the suites with stand-ins, not here. The second server refused the store (one owner) and the bind failure
were checked by the suites, not with real builds.
