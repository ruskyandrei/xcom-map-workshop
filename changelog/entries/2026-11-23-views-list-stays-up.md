### The Views list stays up on the pointer's way from the button to a row

The user found the rail's Views list closing as the pointer went from the Views button to a row: only a click kept it
up. The list scrolled itself (for a short window), and a box that scrolls clips what stands outside it, so the
invisible bridge every rail list has over the gap between the button and the list was cut away. The rows scroll now,
inside the list, and the bridge is whole ([style.css](../../tools/viewer/web/style.css)).

Checked: by hand in a browser (hovered, then moved to a row: the list stays up); the browser check `diagonal` now moves
the pointer in small steps from the button to the Diagonal cover row and clicks it
([browser_diagonal.py](../../tools/viewer/tests/browser_diagonal.py)); floor-boxes and grid-panel.
