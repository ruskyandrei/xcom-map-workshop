// The page's small DOM and word helpers (refactor stage P9): a name's last part, an element of text, a term and its
// value in a list, a count with its noun, a copy to the clipboard told on its button, a row of buttons used like a
// select, a sentence's first letter made a capital. Pure: it imports nothing and keeps no state, so any module can use
// it, and node reads it (dom_words_test.mjs).

export const short = path => path.split('.').at(-1);
export function text(parent, tag, value, className) {
  const el = document.createElement(tag); el.textContent = value;
  if (className) el.className = className;
  parent.append(el); return el;
}
export function field(parent, name, value) {
  text(parent, 'dt', name); return text(parent, 'dd', value);
}
export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
export async function copyText(button, value) {
  const label = button.textContent;
  try { await navigator.clipboard.writeText(value); button.textContent = 'Copied'; }
  catch { button.textContent = 'Copy failed'; }
  setTimeout(() => { button.textContent = label; }, 1500);
}
// A row of buttons used like a select: .value, buttons with data-value, onChange after a click.
export function segmented(el, onChange) {
  Object.defineProperty(el, 'value', {
    get: () => (el.querySelector('button.on') || el.querySelector('button'))?.dataset.value,
    set: v => { for (const b of el.querySelectorAll('button')) { b.classList.toggle('on', b.dataset.value === v); b.setAttribute('aria-pressed', b.dataset.value === v); } },
  });
  el.addEventListener('click', e => {
    const button = e.target.closest('button');
    if (!button || button.disabled || button.classList.contains('on')) return;
    el.value = button.dataset.value; onChange();
  });
}
export function segButton(value, label, title) {
  const button = document.createElement('button');
  Object.assign(button, { type: 'button', textContent: label, title });
  button.dataset.value = value;
  return button;
}
export const sentence = s => s.charAt(0).toUpperCase() + s.slice(1);
