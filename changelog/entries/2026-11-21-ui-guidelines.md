### A guidance page for the editor's interface

[UI-GUIDELINES.md](../../UI-GUIDELINES.md) is new, beside ARCHITECTURE.md: what a change to the editor's interface
should be like. Its sections:

- editing in the 3D view (handles, gizmos and views of their own for what has a place or a size, a value drawn where
  it is, and the view kept readable: handles only on what is picked, markers in their own views, one meaning to a
  colour);
- one interface (one way to do a thing, each kind of control in its place, the stylesheet's parts, the same name, icon
  and key everywhere);
- panels, messages and buttons (a panel holds what is needed to act and no more, explanation behind the info button
  and in tooltips, a button has a border and a fill, with the main action in the accent colour; the bare-text `.link`
  style is not used for a new control);
- mock designs before a larger change (a new window, dialog, panel or view, or one laid out anew): two to four
  designs shown, one chosen, then built; the mock designs stay in `private/`;
- a checklist.

[AGENTS.md](../../AGENTS.md) has a bullet that points to it, and the [README](../../README.md) a line.

Checked with the `repo` suite. Nothing in the editor changed: the `.link` buttons there are (the piece panel's Copy
full paths, the project manager's and the test squad's few) keep their look until their panels are next changed.
