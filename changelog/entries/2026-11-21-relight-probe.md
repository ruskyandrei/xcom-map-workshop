### The relight probe kept as a research tool: where a relight's time goes inside its workers

The editor refactor's stage B5 timed the relight's parts inside every pool worker with a scratch probe and replayed
the pool's clock with what-ifs; that is how the made pieces' second shadow maps (follow-up 2.2) and the workers'
start were found. The probe is now [relight_probe.py](../../tools/bake/relight_probe.py) (follow-up 1.5), with three
commands, its usage in its docstring (`--help` prints it; `tools/bake` has no README):

- `run --log <folder> -- <relight.py's arguments>` runs [relight.py](../../tools/bake/relight.py) as it is, with timers
  round its parts in the main process and in every spawned worker (each imports the probe as its main module and finds
  the folder in the environment the probe sets), one JSON line per timed call per process. A part the relight no longer
  has is named at the start and left;
- `report <folder>` (B5's `analyse.py`): the workers' start, the jobs by kind, each piece's preparation and its parts,
  the band computations' parts, and each shadow map's job with its component, its shadow map (the job's record now
  names it), its rectangle and seconds;
- `replay <folder> [--relight-json <record>]` (B5's `simulate.py`): the pool's clock from the measured jobs, as
  `run_jobs` hands them out, with what-ifs: a fresh piece's shadow maps of one light but the last it lists left out,
  the distance fields' window search four times faster, a band's preparation paid once a piece.

Folders come from the arguments, the tool folders through [paths.py](../../tools/paths.py)'s `use()`, and nothing heavy
is imported for `--help`, `report` or `replay`. It is listed as a research tool that does not ship
([structure.json](../../tools/repo/structure.json)'s `not shipped`).

Checked: [test_relight_probe.py](../../tools/bake/tests/test_relight_probe.py) (new, in the bake suite) runs `--help`
and the report and replay on made-up records (4 tests, 1 s). A real run on the made-ground Build's relight (the
follow-ups' baseline, 16 workers) wrote 17 processes' records: 269 jobs, 48 of them shadow maps (56.7 s summed, 44.3 s
of it the made pieces' second maps), the replayed clock 17.4 s as run and 14.6 s without the second maps; its relight
took 37 s with the timers on (31 s in the Build without; the computer was loaded by other work).
