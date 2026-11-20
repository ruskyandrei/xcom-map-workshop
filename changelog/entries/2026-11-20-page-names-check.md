### The page's names check: an undefined name or an unused import in the page's modules, found without running them

Editor refactor, stage 0 (item 0.4, decision D9). A function moved from one page module to another without its import
throws only when its line runs, and no browser check runs every line. This check finds such a name without running
any.

- [web_names.py](../../tools/viewer/tests/web_names.py) runs ESLint over `tools/viewer/web/*.js` (not `vendor/`) as
  ES modules in the browser, with two rules only: `no-undef`, and an unused-import rule (an import binding nothing in
  its module reads; `export { name }` counts as a use). It prints each finding as `file:line: name` and exits 1 if
  there is any. It exits 2 if node, npm or npx is missing, or if ESLint can't be installed or run. Files given on the
  command line are checked instead of the page's modules.
- ESLint 10.14.0 and the `globals` package 17.14.0 are pinned in the script. npm installs them into a scratch folder
  (`.scratch/eslint`, ignored by Git, made on the first run; `--scratch` names another), and npx runs ESLint from
  there. The repository holds no `node_modules`.
- [web_names.config.mjs](../../tools/viewer/tests/web_names.config.mjs) holds the settings. The known globals are the
  browser's, less the window properties whose names read as a variable of the page's own: the
  confusing-browser-globals list (`name`, `status`, `open`, `parent`, `top`, ...) and `viewport`. app.js declares
  `open`, `moveTo` and `viewport` itself. A function moved out of app.js without its import would read the window's
  instead and not throw, so a bare use of one is reported. `location` and `history`, which app.js uses as the
  window's on purpose, are added back with their reasons. Inline ESLint comments in the page are not honoured: the
  exceptions live in the config, each with its reason.
- [requirements-dev.txt](../../tools/requirements-dev.txt)'s notes give the versions and how to run it. `run_tests.py`
  does not run it.
- Checked:
  - Its first run on the page's 50 modules is clean, so nothing in the page needed fixing.
  - A cross-check with ESLint's own `no-unused-vars` (every name) and `no-undef` with `typeof` found no unused
    import and no undefined name either. Only unused locals, which this check leaves alone.
  - A planted file is reported line by line: an unused import, an undefined name, a bare `name` and `open`, and a
    syntax error. So are a vendor file given by name and a missing Node.js (exit 2).
