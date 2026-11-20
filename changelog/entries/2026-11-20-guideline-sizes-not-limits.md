### Sizes are guidance, not limits: the structure test lists them and fails on none

At the user's word ("I don't want to be too strict about this but general guidance is good"), about 1,500 lines a
file and 150 a function, and app.js's counts of module-level `let`s and top-level functions, are guideline sizes:
- [test_structure.py](../../tools/repo/tests/test_structure.py) no longer fails on a size. Its file, function and
  app.js rules are gone, with their ceilings and the rule that a ceiling must be lowered when its file shrinks.
  `python -B tools/repo/tests/test_structure.py --sizes` lists what is over the guideline sizes, largest first, and
  app.js's counts (exit 0). The rules it still holds are unchanged: no page module imports app.js, no import cycle
  among the page's modules, what ships imports no lab, research or test module, no shipped function changes
  `sys.path` itself, a compiler family does not import the compiler, and `structure.json`'s form.
- [structure.json](../../tools/repo/structure.json) holds `guideline sizes` in place of `limits`, and no ceilings.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): section 3's rule on sizes is guidance (past them, see whether the new code
  is a module or a function of its own); section 4 is "Sizes, and the rules a test holds", with the sizes as
  guidance and how `--sizes` measures; the checklist's last question asks about growing well past the guideline
  sizes. [AGENTS.md](../../AGENTS.md)'s bullet says the same and drops the ceilings.

Checked: the repo and release suites pass (37 and 15 tests); `--sizes` lists 10 files and 10 shipped functions over
the guideline sizes and app.js's 105 `let` statements and 811 top-level functions.
