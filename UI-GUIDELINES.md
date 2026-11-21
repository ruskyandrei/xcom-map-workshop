# How the editor looks and is used

This is for anyone who changes what the editor's user sees or does, person or agent: a control, a panel, a window, a
marker in the view. [ARCHITECTURE.md](ARCHITECTURE.md) says where the code goes; this says what the result should be
like. Section 1 is editing in the 3D view, section 2 keeping the interface one thing, section 3 panels, messages and
buttons, section 4 what to do before a larger change, and section 5 is a checklist.

It describes the interface as it is meant to be. A change that sets a new pattern (a new kind of handle, a new place
for controls, a new style) writes the pattern here in the same commit.

## 1. Edit in the view

- **What has a place, a size, a direction or a reach in the map is edited in the 3D view:** with the gizmo, with drag
  handles on the thing itself, or in a view of its own (Lights, Effects, Spawns, Landing zones, Buildings, the Map
  grid). Number fields stand beside the visual control for an exact value; they are never the only way, and a dialog
  of fields is not how a thing in the map is placed or sized.
- **Show a value where it is.** A light's reach is a shape round the light, a piece's tiles are marked on the ground,
  a building's floor is a box, a landing zone is drawn on the map. A number in a panel that could be drawn in the view
  is drawn, and the panel keeps the number for reading and typing.
- **The Snap setting governs every such edit**, as [AGENTS.md](AGENTS.md) says: continuous with Snap off, the chosen
  step with it on, for handles, gizmos and fields alike.
- **Keep the view readable.** Every handle and marker added makes the others harder to see and to click:
  - Only what is picked shows its handles. Nothing unpicked carries controls.
  - A kind of thing with many markers has a view of its own, shown when its rail button is on, and steps aside in the
    others. A new kind of marker joins the view it belongs to, or gets one, before it is drawn in the normal view.
  - Handles that would sit on each other are spread out, put on a stem or shown one set at a time. Two handles are
    never closer than they can be told apart by the pick distance (`HANDLE_PICK` in
    [`handles.js`](tools/viewer/web/handles.js)).
  - A colour and a shape mean one thing across the editor: a white handle sizes the thing it stands on, and the
    accent colour is what is on. A new marker takes the look of the meaning it shares, or a look nothing else has.
  - What a handle does is said in the hint line while it is held, not in a label standing in the view.
  - A made piece's size handles (since 21 November 2026): one white handle on a stem out of each face it is sized by
    (a wall's two ends, its top, its bottom under the floor line and the face toward the camera for its thickness; a
    floor's, roof's or ground shape's sides, top and bottom), the face's number moving and the opposite face and the
    piece's pivot staying. Its cut-outs' blue handles a set at a time: the picked gap's or hole's own handles, every
    other one's middle alone, which picks it. Its commands (Pivot to corner, Join ends, how a wall taller than its
    look is made) stand in its section of the piece panel.
- A check that a new handle or marker can be seen and clicked is made with other things around it (a busy map, several
  things picked), not on an empty one.

## 2. One interface

- **One way to do a thing.** Before adding a control, look for the one that already does it, and make that one do
  more if it must. A second entry point is a shortcut to the first (the Map menu's Map grid starts the rail's tool; a
  spawn panel's button opens the Landing zones view), never a second set of controls for the same edit.
- **Each kind of control has its place:**
  - the header: the project, the map, Build and Play, and the menus;
  - the rail: the tools, the views and the modifiers (snap, pivot, axes);
  - the panel on the right: what is picked, and only that;
  - the Add panel: what can be placed;
  - a dialog: work apart from the map (files, a build, the project manager, settings);
  - the hint line: what the pointer is doing now.

  A new control goes where its kind is. A new place is a larger change (section 4).
- **Use the stylesheet's parts.** [`style.css`](tools/viewer/web/style.css) has a panel (`.panel`), a folding section
  with its value shown when shut (`.fold`, `.foldval`), a row of buttons (`.row`), icon buttons (`.icon`, `.actions`),
  a chip for a state (`.chip`), a choice of a few (`.seg`), a tick box (`.check`), a note (`.lightnote`), a dialog
  (`.modal`, `.dialoghead`) and the colours as variables on `:root`. A new part is built of these. A new colour, size
  or class is added only for something none of them is, in `style.css` with a comment saying what it is for.
- **The same thing has the same name, icon and key everywhere:** in the panel, the menu, the tooltip, the hint and the
  guide. A menu item that opens a window ends in `…`; one that acts at once does not.
- What a change replaces goes out with it: the old control, its style and its words.

## 3. Panels, messages and buttons

- **A panel holds what is needed to act on the thing, and no more:** its name, what state it is in, its controls. It
  does not repeat what the view shows or what another section says.
- **Explanation is kept out of the way.** How a panel works goes behind its info button (`.howbutton`, with the text
  in `.how`); what a control does goes in its tooltip (`title`), with its key. Sections used less fold, with their
  value on the shut line.
- **State is shown short:** a chip, a count, a mark on the control that changed. A sentence is for what the user has
  to know before acting.
- **A message says what will happen in the game, in one sentence.** A warning is for what can cause a problem in the
  game, and it does not stop the edit; the rest is left unsaid or is a note.
- **A button looks like a button.** It has a border and a fill (`.row button`, `.actions button`, `.barbutton`), and
  an icon where the editor has one for the action. The action a panel or a dialog is there for is in the accent
  colour (`.primary`, `.labelled`). Bare text that acts on a click (the `.link` style) is not used for a new control;
  the few there are get a button's look when their panel is next changed.
- A panel is looked at in a narrow window too (1280, 1024 and 800 wide): it stays clear of the other panels, and its
  rows still read.

## 4. Before a larger change: mock designs

A larger change is a new window, dialog, panel or view, a window or panel laid out anew, a new place for controls, or
a new way of doing something users already do. One control added to a panel in the panel's own pattern is not one,
nor is a wording or a bug fix.

For a larger change, before any of it is built:

1. Make a few designs (two to four) that differ in something that matters: the layout, where the function lives, how
   much is shown at once. Variants that differ only in a colour or a margin are one design.
2. Show each as a picture or a static page in the editor's own style (its stylesheet and parts), with the real words
   and realistic content, and a line on what it gains and what it costs. Say which one you would choose and why.
3. The person who asked for the change chooses, or mixes. Nothing is built until then, and the choice goes into the
   change's plan.

The mock designs are working material, kept in `private/` with every other picture: they do not go into the
repository.

## 5. A checklist for a change

Before a commit that changes what a user sees:

1. Could this be edited or shown in the 3D view rather than in fields (section 1)?
2. With it on, can every handle and marker near it still be told apart and clicked?
3. Is there already a control that does this, and does the new one sit where its kind goes (section 2)?
4. Is it built of the stylesheet's parts, with the names, icons and keys used elsewhere?
5. Can anything in the panel go: a sentence, a repeated value, a section (section 3)? Do its buttons look like buttons?
6. Is it a larger change? Then were the mock designs shown and one chosen (section 4)?
