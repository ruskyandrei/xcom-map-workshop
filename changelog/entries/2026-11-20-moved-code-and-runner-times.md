### A checker that a move of code changed nothing, and the test runner's logs carry each line's times

Two of the tools the editor refactor's checks need (stage 0, items 0.3 and 0.5). No product code changes.

- [moved_code.py](../../tools/repo/moved_code.py): `moved_code.py <base commit> <old file> <new file> [--subst OLD=NEW
  ...] [--names a,b,c]`. The old file is read at the base commit through Git, the new one from the working tree.
  - Python: each function's or method's syntax tree, after the substitutions, is compared with the old one's.
    Whitespace, line breaks, comments and a docstring's wrapping make no difference. A method may change class:
    `--names effect_of` finds it in any class, `Compiler.effect_of` qualifies it, and `OLD=NEW` names each side
    (also a rename).
  - JavaScript: each top-level function (`function`, `async function`, `export function`, `const f = (...) =>`,
    `const f = function`) is compared by its tokens, so whitespace and a comment's wrapping make no difference.
  - Without `--names`, every function in both files is compared, by its qualified name, else by its own name when
    it is in one class only on each side. Those in only one file are listed.
  - It prints a diff of each function that differs, leaving out lines that differ only in whitespace. Exit status 1
    if any differs or a named one is missing, 2 if it could not compare.
  - Its readers (`python_functions`, `js_functions`, `js_inner_functions`, `js_top_level`) are also what the structure
    test measures with.
- [run_tests.py](../../tools/run_tests.py): each line of a suite's log starts with two times in seconds since the suite
  started, `[begun ended] `: when the line's first character came and when its end did.
  - unittest writes a test's name when the test starts and its verdict when it ends, so a test's line gives its start
    and end. The gap before a class's first test is the class's set-up.
  - `--times` prints the twenty slowest tests and classes of each suite after a run. `--times --log <folder>` with
    logs already there reads them and runs nothing. For node, each test file counts as a test.
  - The screen shows no times. The failure blocks, the skips and the outcome are read the same from stamped or
    unstamped output.
- Checked:
  - [test_moved_code.py](../../tools/repo/tests/test_moved_code.py) runs on made-up files:
    - Python: a method moved into another class with `self.` to `self.c.` is the same, though its docstring was
      rewrapped and a comment and a line break were added. A changed method differs and shows in the diff.
    - Python: names are qualified, renamed and missing, and a name found in two classes is refused.
    - JavaScript: regular expressions, template literals and strings that hold braces are read right. A re-indented
      function with a rewrapped comment is the same; a changed one differs.
    - The command line, against a Git tree of the old file: exit status 0, 1 and 2.
  - The tool on real history: `moved_code.py ee5ae99~1 tools/editor/compiler.py tools/editor/spawn_edits.py --subst
    self.=self.c.` pairs the nine spawn methods with their new class. Three are the same. Six differ, and the diff
    shows each difference: the round's own changes (`self.spawn_actors` to `self.actors`, calls within the family).
    `compiler.py` and `app.js` compared with themselves at HEAD are all the same: 182 functions and 812.
  - [test_run_tests.py](../../tools/repo/tests/test_run_tests.py):
    - A made-up log parses the same with and without its times.
    - The slowest tests and classes come out right, with a class's set-up, a test with a docstring and a test that
      printed before its verdict.
    - Node's files are timed.
    - A real subprocess that pauses 0.4 s inside a line gives that line two times 0.4 s apart.
    - `--times --log` reads a folder without running.
  - `run_tests.py editor --times`: 359 tests, all 359 timed (10 s on a computer running other agents' work, so the
    times are noisy). The slowest five: `test_patchtool_record.ShipRecord.test_set_ship_config_on_copies_of_the_installs_files`
    1.20 s, `test_compiler.ForeignTests.test_the_installs_library_gives_a_piece_and_says_what_it_lacks` 0.84 s,
    `test_prefab_stage.StageTests.test_real_blank_map_compiles_building_only_and_light_only_and_checks_actual_bounds`
    0.80 s, `test_patchtool_record.ShipRecord.test_the_records_on_real_lines` 0.47 s,
    `test_spawn_edit_fixtures.SpawnEditFixtures.test_each_case_gives_what_was_recorded` 0.30 s. The slowest class is
    `test_build.Builds`: 4.8 s for 66 tests, 0.6 s of it set-up.
- Known gaps: the JavaScript reader is a tokenizer, not a parser. A `/` after a `}` is read as the start of a regular
  expression, and an arrow function's expression body ends at a line break that no operator carries on. Neither
  occurs in the page's top-level functions today.
