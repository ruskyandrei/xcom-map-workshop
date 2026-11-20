### The suite runner fails a selection that runs nothing and counts skips by reason

Review findings 24 (the runner's part) and 58 (a run with nothing configured).

- [run_tests.py](../../tools/run_tests.py) used to call a `-k` that matched no Python test "did not finish (exit 5)".
  It now says `no test matched -k <pattern>` and fails. The node suite fails the same way when no file matches, where
  it used to pass as "OK (0 files)".
- A missing Node.js is reported as a failed suite with the reason, not a traceback with no summary.
- Skipped tests are counted by reason under their suite and in the summary, so a run on a computer with no install
  shows what it left out.
- The help lists the lab suite and gives today's times.
- Checked: [test_run_tests.py](../../tools/repo/tests/test_run_tests.py) covers the skip counts and an empty Python
  and node selection. Running `release -k nomatch`, `node -k nomatch` and `upk -k game_grid` by hand gave the
  expected lines.
