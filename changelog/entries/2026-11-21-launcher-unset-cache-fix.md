### The editor's launcher starts again with no VIEWER_CACHE set

`xcom_editor.cmd` closed at once without starting the editor whenever `VIEWER_CACHE` was not set, which is the usual
case: since the launcher's change of 20 November (review finding 47), its line for a cache folder ending in a backslash
read the variable with `%...%`, which cmd expands while it parses the line, before the `if defined` test; an unset
variable left the line malformed ("The syntax of the command is incorrect") and the start ended there. The line now
reads it with delayed expansion (`!...!`, on already), when it runs.

- [xcom_editor.cmd](../../xcom_editor.cmd)

Checked: the launcher run through cmd on test ports: start and stop with no `VIEWER_CACHE` (it starts, answers and
stops), and start with `VIEWER_CACHE` ending in a backslash (the server's command line takes it doubled, as meant).
