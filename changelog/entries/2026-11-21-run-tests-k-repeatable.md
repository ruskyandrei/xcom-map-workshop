### The suite runner takes -k more than once

[run_tests.py](../../tools/run_tests.py) kept only the last `-k`: `-k test_shadowmaps -k test_relight` ran the
relight's tests alone and said nothing of the shadow maps' (follow-up 4.5). Each `-k` is now passed on to unittest,
which runs a test whose name holds any of them; for the node suite a file whose name holds any of them runs. A
selection that runs nothing names every pattern in its failure line (`no test matched -k a -k b`). The usage lines
show a two-pattern run.

Checked: [test_run_tests.py](../../tools/repo/tests/test_run_tests.py) gains a run of the repo suite with two `-k`
(both tests ran: 2 tests; before the change only the second ran and the test failed) and the node files' selection by
any of two patterns (before, no such selection existed and the test failed); the repo suite's runner tests pass (13).
