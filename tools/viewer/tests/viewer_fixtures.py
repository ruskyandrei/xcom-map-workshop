"""The records the viewer suite's tests share (review finding 58: a fixtures module per suite, rather than tests that
import other tests). Named for its suite, as file names are unique across the repository (the bake suite's is
fixtures.py). The records more than one suite shares come from their one home, tools/tests/shared_fixtures.py."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests'))
from projects import SCHEMA, SCHEMA_VERSION  # noqa: E402
from shared_fixtures import minimal_mesh, record  # noqa: E402,F401  (the records every suite shares)

# two projects' ids
ID = '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc'
OTHER = '1a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d'


def document(project_id=ID, **changes):
    """A project on Bar that deletes one piece, with `changes` over it."""
    doc = dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, id=project_id, name='Bar remix', mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256='a' * 64, exporterVersion=12),
               overrides=[dict(target=dict(package='URB_Bar', level='base', actor='TheWorld.PersistentLevel.A_1'), deleted=True)],
               added=[])
    doc.update(changes)
    return doc
