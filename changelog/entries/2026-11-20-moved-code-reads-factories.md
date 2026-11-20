### The move check reads the functions inside a page factory

[moved_code.py](../../tools/repo/moved_code.py) counts the functions a page factory declares (`createX`, a module made
as a closure) as functions of its file, named `createX.f`, so a function moved from app.js into a factory is found by
its own name (`--names f`, or paired by name without names). The refactor's page stages move code into factories;
stage P3 had to copy each factory's body into a scratch file to check its move. [ARCHITECTURE.md](../../ARCHITECTURE.md)
says so beside the tool.

Checked: the repo suite (a function moved into a factory compares the same by name and when paired, and a changed one
differs); on stage P3's own move, `--names saveProject,loadProject,navigate` finds all three inside
`createDocumentSession` (`saveProject` differs by the setter substitutions P3 stated in its pairs).
