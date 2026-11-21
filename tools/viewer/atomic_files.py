"""One writer for a file replaced whole: a project, a record, a picture, an index (KB-10).

A file the editor keeps is written to a temporary file beside it and then put in its place with one replace, so a
crash or a full disk never leaves it cut short. On Windows the replace is refused for a moment (a PermissionError)
while another program holds either file: a virus scanner, a backup or search indexer, an editor that has it open.
`replace` tries again through that moment, as the game install's records always did; before this module only they
did, and a project's Save could fail with "could not be written" where a second try a moment later would have worked.

  replace(temp, path)       os.replace, tried again while Windows refuses it; also for a file moved aside
  write_bytes(path, data)   the bytes written to a temporary file beside `path`, then replace; the temporary file
                            removed on a failure
  write_text(path, text)    the same for text, its line ends as they are in `text`

A writer keeps what is its own around these: its lock, whether it flushes to the disk (`sync`), a read-back before
the replace (mapsini.write_checked), the temporary file's name where something else looks for it (the install's
change journal), and its error's words."""
import os
from pathlib import Path
import time

# a replace that Windows refuses is tried this many times in all, PAUSE seconds apart (about a second): what the game
# install's ledger and config writers always waited
TRIES = 50
PAUSE = 0.02


def replace(temp, path):
    """os.replace(temp, path), tried again while Windows refuses it with a PermissionError (another program holds one
    of the two files for a moment), the last refusal raised after TRIES tries. Any other error is raised at once.
    `temp` is left where it is when the replace fails: it may be a file moved aside, not a temporary one."""
    for attempt in range(TRIES):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == TRIES - 1:
                raise
            time.sleep(PAUSE)


def write_bytes(path, data, temp=None, sync=False):
    """`path` given the bytes `data` whole: written to `temp` (by default `<name>.tmp` beside it), flushed to the disk
    too when `sync`, then put in its place with `replace`. On any failure the temporary file is removed and the error
    raised, and the file at `path` is as it was."""
    path = Path(path)
    temp = path.with_name(path.name + '.tmp') if temp is None else Path(temp)
    try:
        with open(temp, 'wb') as stream:
            stream.write(data)
            if sync:
                stream.flush()
                os.fsync(stream.fileno())
        replace(temp, path)
    except BaseException:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_text(path, text, temp=None, sync=False, encoding='utf-8'):
    """`path` given `text` whole, as write_bytes gives bytes: encoded with `encoding`, its line ends as they are in
    `text` (Windows' '\\r\\n' is never added)."""
    write_bytes(path, text.encode(encoding), temp=temp, sync=sync)
