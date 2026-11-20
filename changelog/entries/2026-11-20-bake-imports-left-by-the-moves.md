### Imports the bake tools' moves left unused taken out

Review finding 63, a follow-up to finding 53's moves.

- [deploy_fixture.py](../../tools/bake/deploy_fixture.py) no longer imports `os`, `re` and `time`, which only the
  config readers used before they moved to [mapsini.py](../../tools/viewer/mapsini.py).
  [test_deploy.py](../../tools/bake/tests/test_deploy.py)'s whole-or-nothing write test stops the replace through
  `mapsini.os`, the writer's own module, instead of reaching `os` through `deploy_fixture`.
- [lightmap_stats.py](../../tools/bake/lightmap_stats.py) no longer imports `io` and `PIL.Image`, which only the
  texture readers used before they moved to [lightmap_textures.py](../../tools/bake/lightmap_textures.py);
  [test_dxt1.py](../../tools/bake/tests/test_dxt1.py)'s note names the module that reads with PIL now.

Checked: both tools compile, import and print their usage; every name `lab_install.py` and the deploy and lab-install
tests take from `deploy_fixture` is still there; a search of the bake and package tools for top-level imports no name
uses finds none left; the deploy, lab-install, DXT1 and UDK calibration tests pass.
