### The recorders' and the page names check's help say what they are for

The help texts of [compile_record.py](../../tools/editor/tests/compile_record.py),
[build_outputs.py](../../tools/editor/tests/build_outputs.py) and [web_names.py](../../tools/viewer/tests/web_names.py)
named a private plan's stage or decision as their reason; each now says what the tool checks and when to run it
(follow-up 5.3, for these three tools only: the comments elsewhere that cite a plan stay, decision D8). The compile
recorder's help, its `record` command's among it, says that a compile made in a process a test starts (a tool or an
example's generator run as a script) is not recorded (follow-up 4.4).

Checked: each tool's `--help` and `record --help`; the editor suite's record tools tests pass.
