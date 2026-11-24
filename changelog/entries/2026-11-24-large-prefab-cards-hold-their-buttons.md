### A prefab's card in the large Add panel holds all its buttons

In the Add panel made large, a prefab's card kept the fixed height of the other tabs' cards (238 pixels), so where its
five buttons (Edit, Rename, Duplicate, Export, Delete) did not fit one row, the row they wrapped to hung under the
card's border. Six cards across a window 1440 wide showed it: Delete stood below every card. Found while the mock
designs of the prefab menus plan were made on the real page.

- [style.css](../../tools/viewer/web/style.css): a prefab's card in the large panel is as tall as the other cards at
  least and grows by the row its buttons wrap to (`#library.large .libitem.prefab`). The cards of one row stay the
  same height. This map's and All maps' cards are as they were (All maps' windowed list needs their fixed height).

Checked: on a test server with a library of six prefabs, the Prefabs tab small and large in windows 1024, 1280, 1440
and 1920 wide (4, 6, 6 and 9 cards across): every button of every card lies inside its card, the cards 271 pixels
high where the buttons take two rows; This map's cards unchanged; no page error. Looked at 1440 wide. The browser
check `rail-lists`. Not done: no check of its own was added, since the buttons' place on these cards is one of the
prefab menus plan's open decisions.
