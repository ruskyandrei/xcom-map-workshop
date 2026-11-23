### Lab staging finds a base map's record whatever the case of its name

Staging EXP-95's farm build in the lab copy refused with "no record for CsmallScout_Farm": the build named its base map
by its file's case (CsmallScout_Farm.upk), and the install's records name it CSmallScout_Farm. The game matches map
names whatever their case, and the editor's own installs did (installs.same_map); the lab's
[deploy_fixture.py](../../tools/bake/deploy_fixture.py) `plan_maps` now does too. The experiment's project script
names the map as the records do ([exp95_diagonal_project.py](../../tools/editor/examples/exp95_diagonal_project.py)).

Checked: [test_deploy.py](../../tools/bake/tests/test_deploy.py) (a base map named in another case gets its record).
