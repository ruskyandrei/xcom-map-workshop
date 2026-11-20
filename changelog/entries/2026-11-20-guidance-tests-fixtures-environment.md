### ARCHITECTURE.md's tests rules level with the fixtures modules and the environment list

Refactor stage T5, the guidance brought level (plan section 11). [ARCHITECTURE.md](../../ARCHITECTURE.md):

- **Where new code goes:** a test's shared records and helpers go in its suite's fixtures module (viewer_fixtures.py,
  the bake suite's fixtures.py, editor_fixtures.py, upk_fixtures.py; a suite without one makes one named for the
  suite), and what more than one suite needs in tools/tests/shared_fixtures.py; a new row says an environment
  variable a test or a tool reads goes into `run_tests.py`'s `ENVIRONMENT` in the commit that reads it.
- **The rules, Tests:** no test file imports another, so each runs alone; a helper made of a test class's methods is
  a mixin in the fixtures module; no suite reaches into another's tests folder (the node and Python case files
  aside); every environment variable is listed, and names one thing.

The [README](../../README.md)'s part on the tests says in a line where the shared fixtures are and how one test
file is run alone.

Checked: the repo suite (its links, the public-repository checks, the names and structure tests).
