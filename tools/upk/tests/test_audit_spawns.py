"""The spawn census's --values pass (audit_spawns.value_survey; editor spawns implementation plan, SP1): the editor's
own reader over one base map, on the install's URB_Bar and CSmallScout_Roadhouse (skipped without the install)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import audit_spawns  # noqa: E402
import labpaths  # noqa: E402

# the configured install's packages, or the folder XCOM_COOKED names
COOKED = Path(labpaths.lwr_cooked() or 'no-install-configured')


def survey(name):
    path = COOKED / f'{name}.upk'
    if not path.exists():
        raise unittest.SkipTest(f'{name} not available')
    found, entry = audit_spawns.value_survey(str(path))
    return entry


class Values(unittest.TestCase):
    def test_bar_reads_whole_with_its_values_tallied(self):
        entry = survey('URB_Bar')
        self.assertNotIn('error', entry)
        self.assertEqual(entry['unread'], [])
        self.assertEqual(entry['kinds']['pod'], 5)
        self.assertEqual(entry['kinds']['meld'], 4)
        self.assertEqual(entry['tallies']['meld difficulty=Hard (saved)'], 2)
        self.assertEqual(entry['tallies']['meld difficulty=Easy (class)'], 2)
        self.assertEqual(entry['tallies']['pod use=True (class)'], 5)
        self.assertEqual(entry['odd'], [])

    def test_a_map_whose_pods_repeat_an_index_says_so(self):
        entry = survey('CSmallScout_Roadhouse')
        self.assertTrue(any(o.startswith('pod indices repeat') for o in entry['odd']))


if __name__ == '__main__':
    unittest.main()
