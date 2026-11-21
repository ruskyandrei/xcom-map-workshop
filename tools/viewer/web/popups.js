// The header's menus (refactor stage P9): the Project, Map and Game menus, Settings, the import notes, View options and
// the help, each opened by its button (data-pop), one at a time, a press elsewhere (or Escape, the keys) closing it
// (showPop). Opening the Project menu draws it afresh (app.js's renderProjectMenu), the Game menu the test squad's line
// and the installs (build_play.js).
//
// createPopups takes what it needs of app.js as one argument object, when app.js makes it, before the first area that
// is given showPop: its buttons' handlers and the press that closes a menu are set then (the Map menu's button is given
// its own handler after, map_menu.js); it keeps no state.

export function createPopups({ $, refreshInstalls, refreshSquadLine, renderProjectMenu, viewport }) {
  // Header menus: one open at a time; a press elsewhere or Escape closes it.
  function showPop(id) {
    for (const button of document.querySelectorAll('[data-pop]')) {
      const on = button.dataset.pop === id, pop = $(button.dataset.pop);
      pop.hidden = !on;
      button.setAttribute('aria-expanded', on);
      if (on && pop.classList.contains('left')) pop.style.left = `${button.getBoundingClientRect().left - viewport.getBoundingClientRect().left}px`;
    }
    if (id === 'projectMenu') renderProjectMenu();
    if (id === 'playMenu') { refreshSquadLine(); refreshInstalls(); }
  }
  for (const button of document.querySelectorAll('[data-pop]')) button.onclick = () => showPop($(button.dataset.pop).hidden ? button.dataset.pop : null);
  document.addEventListener('pointerdown', e => { if (!e.target.closest('.pop, [data-pop]')) showPop(null); });

  return { showPop };
}
