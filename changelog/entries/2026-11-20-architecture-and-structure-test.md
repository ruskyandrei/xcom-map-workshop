### ARCHITECTURE.md says how the code is shaped, and a structure test holds its limits

The first guidance for the code written from here on (editor refactor, stage 0, item 0.7). No product code changes.

- [ARCHITECTURE.md](../../ARCHITECTURE.md), first version, at the repository's root:
  - how the parts fit: the export, the page, the server, a project, the compiler, the native edit, the Build, the
    copy tool, the relight, and the packaged map and the install. Each paragraph names the module that owns the part
    and the contract it hands on;
  - where new code goes, as the code stands. app.js, the `Compiler` class and `native_copy.build` take no new code;
  - the rules, each with its reason;
  - the limits and the exceptions, as the test holds them;
  - changing the structure, with the stage-0 tools by path;
  - a checklist for a change.
- [test_structure.py](../../tools/repo/tests/test_structure.py) in the repo suite, with its numbers in
  [structure.json](../../tools/repo/structure.json) (sorted, one entry a line, so different entries' changes merge
  cleanly). Its rules:
  - **File size:** a tracked Python file or page module over 1,500 lines is listed with a ceiling.
  - **Function size:** a function over 150 lines in what the release ships is listed with a ceiling.
    `make_release.py`'s own `modules()` and `page_files()` say what ships.
  - **app.js's top level:** 112 module-level `let`s and 812 top-level functions, each a ceiling.
  - **The page's imports:** no page module imports app.js, and no import cycle beyond those listed. There are none.
  - **What ships imports:** no shipped module imports the lab, the research tools or a test beyond those listed, each
    with its reason. There are none.
  - **The import path:** no shipped function changes `sys.path` itself beyond those listed. Two are listed:
    `paths.use` itself, and `looks.measurer`.
  - **Compiler families:** the rule is written, with an empty list. `spawn_edits.py` still imports the compiler.
  - A ceiling fails over its size, and also when its file has shrunk more than a twentieth under it (lower the
    ceiling). An entry fails when its file or function is within the limit again or gone (take the entry out).
  - Every message names its rule and the document's section, and the test checks that the document has a part for
    each rule. `test_structure.py --root <folder>` checks another checkout.
- The limits stay at 1,500 lines a file and 150 a function. Among what ships, 16 exceptions are listed: six files
  (app.js, compiler.py, native_copy.py, relight.py, installs.py, build.py) and ten functions. That is about the
  fifteen the plan allowed before the limits would be raised.
  - A page module made as a factory (`createX`, declaring its functions inside and returning them) is measured by the
    functions it declares, not as one function.
  - Measured whole, eleven factories would be over 150 lines too, which would make 27 exceptions. Yet no function
    inside any factory is over 74 lines: a factory is a module made as a closure, which is the model the page's
    modules follow.
  - Four files that do not ship are listed as well: browser_smoke.py, test_compiler.py, test_build.py and
    wall_measure.py.
- [AGENTS.md](../../AGENTS.md) has a bullet: new code follows ARCHITECTURE.md, the checklist is read before a commit
  that adds a module or a format's reader, and a ceiling is lowered with its file and raised only with the user's
  word. [README.md](../../README.md)'s "This repository" links the document.
- Checked:
  - `run_tests.py repo release`: 40 and 14 tests pass. The test's own logic is checked on made-up numbers: a ceiling
    over, under by more than a twentieth, within the limit and gone; cycles; path changes inside functions.
  - Planted breaks, each in a scratch copy of the checkout (a Git index of its files, not committed). Each fails
    with its rule's message and the document's section, and the copy passes before and after:
    - a listed file grown past its ceiling (build.py, 1,769 over 1,759);
    - a new untracked file of 1,600 lines;
    - a shipped function grown to 160 lines (`native_lights.prepare`, from 149);
    - a page module importing app.js (walls.js), which also reported the cycle it made;
    - a shipped module importing a lab module (projects.py importing `labpaths`);
    - `sys.path.insert` inside a shipped function;
    - a ceiling more than a twentieth over its file (build.py listed at 1,900);
    - two more: a module-level `let` added to app.js, and structure.json with an entry out of order.
- [moved_code.py](../../tools/repo/moved_code.py): the byte-order mark its tokenizer skips is now written as an escape,
  not as the invisible character itself.
- Known gaps: the factory rule goes by the name (`create` and a capital) and by the factory declaring functions
  inside. A long function given that name and one small inner function would escape the function limit, though not
  its file's. The document says what a factory is.
