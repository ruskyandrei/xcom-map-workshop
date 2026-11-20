### Setup asks for a running editor to be closed before it upgrades or uninstalls

Review finding 60, its first item.

- The server holds a named mutex while it runs, in the session's namespace and in `Global\`
  ([appmutex.py](../../tools/viewer/appmutex.py), taken in [viewer.py](../../tools/viewer/viewer.py) once the port
  is bound).
- [installer.iss](../../tools/release/installer.iss) names it with `AppMutex`, so Setup and the uninstaller ask for
  the editor to be closed. They used to delete the `python` and `tools` folders under a running editor.
- The [getting-started page](../../tools/release/GETTING-STARTED.md) already says so.
- Checked: [test_appmutex.py](../../tools/viewer/tests/test_appmutex.py) holds and releases a test-named mutex, and
  the release test checks the installer's line. A test server on port 8799 was seen holding the real mutex, and it
  was gone once the server stopped. The installer itself was not run.
