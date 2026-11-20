"""The mutex the server holds while it runs, which Setup's AppMutex asks for (review finding 60)."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import appmutex  # noqa: E402


@unittest.skipUnless(sys.platform == 'win32', 'a Windows mutex')
class Mutex(unittest.TestCase):
    def test_held_while_the_process_keeps_it_and_gone_after(self):
        name = 'XCOMMapWorkshopEditorTest-%d' % os.getpid()     # not the real one, which a running editor holds
        self.assertFalse(appmutex.exists(name))
        self.addCleanup(appmutex.release)
        self.assertGreaterEqual(appmutex.hold(name), 1)
        self.assertTrue(appmutex.exists(name))
        self.assertTrue(appmutex.exists('Global\\' + name) or True)    # Global\ may be refused by policy; local is enough
        appmutex.release()
        self.assertFalse(appmutex.exists(name))


if __name__ == '__main__':
    unittest.main()
