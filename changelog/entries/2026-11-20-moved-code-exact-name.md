### The move check takes an exact name for a module-level function beside a method of that name

[moved_code.py](../../tools/repo/moved_code.py) refused `--names records` when the new file held both a module-level
`records` and a method `PlayInstalls.records` (the name matched both, so it asked to be qualified, and a module-level
function has no qualifier). A name that is exactly one function's qualified name is now that function; a dotted or
partial name still matches on whole components and is refused when it matches two. Met by the refactor's stage T5,
which checked that move by hand.

Checked: the repo suite (a module-level function beside a method of its name compares by its exact name, and the
method by `spec=EffectEdits.spec`).
