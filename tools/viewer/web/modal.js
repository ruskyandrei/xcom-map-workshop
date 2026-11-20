// Every dialog of the page (a `.modal`) holds the keyboard while it is open (review finding 11): Tab and Shift+Tab go
// round its own controls, from the last back to the first; a dialog that opens without taking the focus is given it;
// and when it closes the focus goes back to where it was. Each dialog keeps its own keys (its module's listener, for
// Escape and its shortcuts); one with an order of its own for Tab gives it here (tabOrder). The editor's shortcuts
// ask anyModal() and take no keys while a dialog is open (app.js modalOpen).

const orders = new WeakMap();      // a dialog's root -> (event, stops) => the control Tab goes to (undefined: round)

/** The controls Tab stops at in `root`, in order: drawn, enabled and not taken out of the order. */
export function tabStops(root) {
  return [...root.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')]
    .filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length > 0 && !el.closest('[hidden]'));
}
/** The control after (Shift: before) the one with the focus among `stops`, round from the last to the first; the
 * first (Shift: the last) when the focus is on none of them. */
export function nextStop(e, stops) {
  if (!stops.length) return null;
  const at = stops.indexOf(document.activeElement), step = e.shiftKey ? -1 : 1;
  return at < 0 ? stops[e.shiftKey ? stops.length - 1 : 0] : stops[(at + step + stops.length) % stops.length];
}
/** A dialog's own Tab order: `next(event, stops)` gives the control Tab goes to, or undefined for the usual round. */
export function tabOrder(root, next) { orders.set(root, next); }
/** The dialog on top: the last `.modal` shown in the page, or null. */
function topModal(doc = document) {
  const open = doc.querySelectorAll('.modal:not([hidden])');
  return open[open.length - 1] ?? null;
}
/** Whether a dialog is open. */
export const anyModal = (doc = document) => topModal(doc) !== null;

const shown = el => Boolean(el?.isConnected) && el.getClientRects().length > 0 && !el.closest('[hidden]');

/** The behaviour for every `.modal` of the page, put in once (before any listener that stops keys at the window, so
 * Tab is kept in a dialog that takes every key, such as the build window). */
export function holdModals(win = window) {
  const doc = win.document, openers = new WeakMap();
  let last = null;
  // the control a dialog was opened from: the one with the focus before the focus first went into it
  doc.addEventListener('focusin', e => {
    const m = e.target.closest?.('.modal');
    if (m && !openers.has(m) && last && !m.contains(last)) openers.set(m, last);
    last = e.target;
  });
  win.addEventListener('keydown', e => {
    if (e.key !== 'Tab' || e.ctrlKey || e.altKey || e.metaKey) return;
    const m = topModal(doc);
    if (!m) return;
    e.preventDefault();
    const stops = tabStops(m), next = orders.get(m)?.(e, stops) ?? nextStop(e, stops);
    (next ?? (m.hasAttribute('tabindex') ? m : null))?.focus({ preventScroll: true });
  }, true);
  new MutationObserver(records => {
    for (const { target: m } of records) {
      if (!m.classList?.contains('modal')) continue;
      if (!m.hidden) {
        // opened: one that didn't take the focus (its OK disabled, say) gets it on its first control
        if (m.contains(doc.activeElement)) continue;
        if (!openers.has(m) && doc.activeElement && doc.activeElement !== doc.body) openers.set(m, doc.activeElement);
        (tabStops(m)[0] ?? (m.hasAttribute('tabindex') ? m : null))?.focus({ preventScroll: true });
        continue;
      }
      // closed: the focus, if it went with the dialog, goes back to where the dialog was opened from (the dialog
      // still open under it, else nowhere)
      const opener = openers.get(m), focus = doc.activeElement;
      openers.delete(m);
      if (focus && focus !== doc.body && !m.contains(focus)) continue;
      const under = topModal(doc), back = shown(opener) && (!under || under.contains(opener)) ? opener
        : under ? tabStops(under)[0] ?? null : null;
      if (back) back.focus({ preventScroll: true }); else focus?.blur?.();
    }
  }).observe(doc.body, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
}

// Outside a dialog, a select, tick box, radio button or slider gives the focus up once it has changed (review finding
// 33): the editor's shortcuts ignore keys typed in a field, so with the focus left there Up and Down would go on
// changing a select, and Delete, Ctrl+Z or B would do nothing until the view was clicked. A dialog keeps its focus
// (its Tab ring, above).
const LET_GO = 'select, input[type=checkbox], input[type=radio], input[type=range]';
/** Put in once: the focus leaves such a control, outside a dialog, after its change (its own listeners first). */
export function releaseAfterChange(doc = document) {
  doc.addEventListener('change', e => {
    const t = e.target;
    if (t?.matches?.(LET_GO) && !t.closest('.modal, dialog') && t === doc.activeElement) t.blur();
  });
}
