"""The folders of this computer that the lab tools use, from the editor settings (tools/viewer/settings.py).

No checked-in file names a folder of one computer: the lab tools take theirs from the settings file
(<Documents>\\XCOM Map Workshop\\settings.json, or the file XCOM_MAP_WORKSHOP_SETTINGS names), set with
`python tools/viewer/viewer.py settings --lab <folder> --udk <folder> --lwr <folder>`:

- lab: our lab's working folder (logs, bake fixtures, patchtool work, snapshots, compiled helpers in bin, re);
- udk: UDK 2011-09 with the XComGame stubs;
- lwr: the LWR install, or the folder holding the game folders (Steam's steamapps\\common), where
  tools/lab/switch_install.ps1 swaps the lab copy and LWR in and out of XCom-Enemy-Unknown.

Each function reads the settings when it is called, never at import, and raises ValueError saying how to set a
missing one; configured() and lwr_cooked() give None instead, for defaults that may be absent (the unit tests).
tools/lab/LabSettings.ps1 does the same for the PowerShell scripts.
"""
import os
from pathlib import Path
import sys

VIEWER = Path(__file__).resolve().parents[1] / 'viewer'
if str(VIEWER) not in sys.path:
    sys.path.append(str(VIEWER))
import settings  # noqa: E402


def lab_root():
    """Our lab's working folder (the lab setting)."""
    return settings.require(settings.load_settings(), 'lab')


def udk():
    """UDK 2011-09 (the udk setting)."""
    return settings.require(settings.load_settings(), 'udk')


def steam_common():
    """The folder holding the installs side by side: the lwr setting when it holds game folders, else the parent of
    the game folder it names."""
    lwr = settings.require(settings.load_settings(), 'lwr')
    return lwr.parent if settings.is_game(lwr) else lwr


def active_game():
    """The game folder Steam runs, <Steam common>\\XCom-Enemy-Unknown: the lab copy while its root holds the marker
    XComLab-copy.txt (switch_install.ps1 lab), else LWR itself."""
    return steam_common() / settings.STEAM_NAME


def lwr_game():
    """The LWR install's game folder, never the lab copy (settings.lwr_game)."""
    game, note = settings.lwr_game(settings.load_settings())
    if game is None:
        raise ValueError(note)
    return game


def configured(key, *parts):
    """A setting's folder joined with `parts`, or None when it is unset or the settings can't be read."""
    folder = settings.configured(key)
    return None if folder is None else folder.joinpath(*parts)


def lwr_cooked(name=None):
    """The LWR install's EW CookedPCConsole (or the file `name` in it), or None when the install is not configured."""
    folder = settings.lwr_cooked()
    return folder if folder is None or name is None else folder / name


def test_file(env, default, what):
    """For the unit tests: (the file or None, why a test without it skips). The file is the one the environment
    variable `env` names, else `default` (from configured() or lwr_cooked(), None when the settings lack it). Tests
    skip with @unittest.skipUnless(path and path.exists(), reason)."""
    if os.environ.get(env):
        path = Path(os.environ[env])
        return path, f'{what} not found at {path} (from {env})'
    if default is None:
        name = env or 'XCOM_COOKED'
        return None, f'{what} not configured: set {name}, or the settings (python tools/viewer/viewer.py settings)'
    return Path(default), f'{what} not found at {default}'


def install_map(name):
    """For the unit tests: the package `name` (a map or stream, no extension) of the configured install, as
    test_file gives it: (the file or None, why a test without it skips). XCOM_COOKED names another CookedPCConsole
    folder to take it from."""
    if os.environ.get('XCOM_COOKED'):
        path = Path(os.environ['XCOM_COOKED']) / (name + '.upk')
        return path, f'{name}.upk not found at {path} (from XCOM_COOKED)'
    return test_file('', lwr_cooked(name + '.upk'), name + '.upk')
