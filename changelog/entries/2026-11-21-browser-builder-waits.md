### The builder check's held draft: its answer waited for, not 1.1 s

Editor refactor, stage P10. In [browser_builder.py](../../tools/viewer/tests/browser_builder.py), the recovery-edges
part holds a draft's write (PUT) 300 ms, saves meanwhile, and checks that no draft is left: a draft written after the
save would show. It waited 1.1 s after the save for that write; it now waits for the held write's answer (Playwright's
`expect_response`), which is already in when the save waited for it, as it should, and comes after the save if a
change ever lets the save go first. The 300 ms hold itself stays: it is the slow server the check makes, not a wait.

Checked on a test server: `--only builder` five times in a row, all passing; `browser_smoke.py --all` twice (its
`builder` run).
