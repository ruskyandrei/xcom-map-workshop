### Play in game starts beside another copy's open XCOM

- With another game folder's XCOM open (the user's own play of another copy), Steam refused the play ("game is
  already running"). Play in game now starts the install's own `XComEW.exe` itself in that case, with the lab's
  side-by-side change: started suspended, the one-instance call replaced in the new process's memory with
  `mov eax, 1`, resumed (T-52); no file is changed, and an exe whose bytes differ is ended before it runs, the play
  saying why. It gets `-FROMLAUNCHER`, Steam's two variables (F-84) and `__COMPAT_LAYER=HIGHDPIAWARE` (T-48), and
  breaks away from the server's job where Windows allows it.
- The install's own game is never started twice: a play is still refused while it runs, now in words that say it is
  this install's ("XCOM is running from this install: close it first").
- A game folder outside a Steam library is started the same way.
- Where: [side_by_side.py](../../tools/viewer/side_by_side.py) (the start, ported from
  [XComSideBySide.cs](../../tools/lab/XComSideBySide.cs)), [gamelaunch.py](../../tools/viewer/gamelaunch.py)
  (`command`'s `beside`, `other_game_running`, `start`), [procs.py](../../tools/viewer/procs.py)
  (`running_elsewhere`), [play.py](../../tools/viewer/play.py) (hands the start its how),
  [installs.py](../../tools/viewer/installs.py) (`ready`'s words), [play.js](../../tools/viewer/web/play.js) (the play
  window's line and the Game menu's Started row), the guide's Play in game section.
- Checked: the viewer, node and repo suites; [test_side_by_side.py](../../tools/viewer/tests/test_side_by_side.py)
  changes a 32-bit program of Windows' own in a suspended process (its header, written back as it was) and ends it;
  the lab copy's `XComEW.exe` started suspended from the server's 64-bit Python, its bytes found at the right place
  and changed, and ended before it ran.
- Not tried: a whole play beside another open game (the lab's own side-by-side start, which this ports, is played
  daily).
