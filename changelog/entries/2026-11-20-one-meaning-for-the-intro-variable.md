### XCOM_INTRO_UPK names one package: the copy tool's tests take the tutorial's map as the other tests do

Refactor stage T5 (review finding 58, the runner's environment). `XCOM_INTRO_UPK` named the game's landing intro
(CIN_DropshipIntros.upk) for [test_intro_copy.py](../../tools/bake/tests/test_intro_copy.py) and the viewer's
[test_manager.py](../../tools/viewer/tests/test_manager.py), and the tutorial's map (Act1_IntroLevel.upk) for
[test_native_copy.py](../../tools/bake/tests/test_native_copy.py): set for one, it gave the other the wrong package.
test_native_copy takes Act1_IntroLevel from the configured install (or the folder `XCOM_COOKED` names) through
`labpaths.install_map`, as test_native_effects.py and test_shell.py already did, so the variable means the landing
intro alone. The default file is the same as before; the skip message names `XCOM_COOKED`.

Checked: the bake tests named Intro (14, among them test_native_copy's RebuildTemplateIntro and WalkableScenery, both
run with the install).
