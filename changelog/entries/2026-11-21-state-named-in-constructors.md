### The exporter's and the server handler's state named where they are made

Three attributes were first set outside their class's constructor (follow-ups item 6.9): the exporter's `landings`
(made in `effects()`, read by `run()`) and `area_matcher` (made in `run()`) in
[export.py](../../tools/viewer/export.py), and the server handler's `answered` in
[viewer.py](../../tools/viewer/viewer.py), which `answer` read with `getattr(self, 'answered', False)`. Each is now
named in `__init__` with what fills it; `answered` is set before the base class's `__init__`, which serves the
handler's requests, and each request still starts unanswered (`parse_request`); `answer` reads it plainly.

Nothing changes. Checked: the viewer's server guard, damaged inputs, effects metadata, streams, material rules and
area light tests pass (65 tests).
