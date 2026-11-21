### The lab's test slot takes its name from the one home of the first mission's name

[deploy_fixture.py](../../tools/bake/deploy_fixture.py)'s `TEST_SLOT` was a hand copy of the record name a new
campaign's first mission asks for, which [installs.py](../../tools/viewer/installs.py) holds as `FIRST_MISSIONS`
(follow-up 3.14). It is now `installs.FIRST_MISSIONS[0]`, as the lab's pack test takes it. The name is the same, so
nothing changes: the bake fixtures' installer, the lab's install and their tests read the same slot.

Checked: the bake suite's deploy and lab install tests (24), the lab suite (49) and the viewer suite's manager tests
(23) pass.
