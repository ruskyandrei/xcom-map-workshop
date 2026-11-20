"""The records and helpers the editor suite's tests share (review finding 58: a fixtures module per suite, rather than
tests that import other tests). Named for its suite, as file names are unique across the repository (the bake
suite's is fixtures.py). The records more than one suite shares come from their one home,
tools/tests/shared_fixtures.py."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests'))
from shared_fixtures import record  # noqa: E402,F401  (the records every suite shares)
