### The page's names check names files by their path in the repository

[web_names.py](../../tools/viewer/tests/web_names.py) handed ESLint every page module by its absolute path on one
command line through npx and cmd.exe. In a worktree's deep folder, from about seventy modules on, that passed cmd.exe's
8,191-character limit ("The command line is too long") and nothing was checked; the refactor's page stages, which
add modules, met it. The files are now named relative to the repository, where ESLint runs (a file given from outside
it keeps its whole path): 73 modules take about 2,300 characters.

Checked: clean on the page's 73 modules in a worktree; a planted undefined name is reported with its file and line.
