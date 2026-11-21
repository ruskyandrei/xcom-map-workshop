### The EXP-26 project's generator saves again

[exp26_projects.py](../../tools/editor/examples/exp26_projects.py) made its document at project schema 1 and stopped
at its own save, which the projects store refuses below the schema it writes (4). EXP-26's runs 2 to 6 are still
open, and [build_outputs.py](../../tools/editor/tests/build_outputs.py) takes the generator's compile for its
bar-pieces input. It now compiles the document as it was made (schema 1, so that compile is unchanged) and saves it
at the store's schema, which its fields still meet; if the store ever refuses it, it stops after the compile with a
line saying the generator is historical. Its docstring says so.

Checked: a new test in [test_build.py](../../tools/editor/tests/test_build.py), failing before with the store's
refusal, runs the generator on a stand-in export: one compile at schema 1, the project saved at the store's schema;
the generator run on the real export saves into a scratch projects folder; `build_outputs.py` against the stage's
start: the bar-pieces input's documents and compiles are the same (the manifests' `tools` names differ, from the
change of the manifest's tools).
