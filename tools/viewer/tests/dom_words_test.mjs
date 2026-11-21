// The page's small DOM and word helpers (web/dom_words.js): a name's last part, a count with its noun, a sentence's
// capital, and the elements of text and of a term with its value (on a stand-in document, the only page node needs).
// Run: node tools/viewer/tests/dom_words_test.mjs
import assert from 'node:assert/strict';
import { field, plural, segButton, sentence, short, text } from '../web/dom_words.js';

assert.equal(short('TheWorld.PersistentLevel.XComLadder_3'), 'XComLadder_3');
assert.equal(short('NoDots'), 'NoDots');
assert.equal(plural(0, 'piece'), '0 pieces');
assert.equal(plural(1, 'piece'), '1 piece');
assert.equal(plural(2, 'light edit'), '2 light edits');
assert.equal(sentence('starting'), 'Starting');
assert.equal(sentence(''), '');

// a stand-in document: an element is its tag, class, text, children and data set
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.textContent = ''; this.className = ''; this.dataset = {}; }
  append(child) { this.children.push(child); }
}
globalThis.document = { createElement: tag => new Element(tag) };

const list = new Element('dl');
const note = text(list, 'div', 'A note', 'note');
assert.deepEqual([note.tagName, note.textContent, note.className], ['div', 'A note', 'note']);
assert.equal(text(list, 'span', 'plain').className, '', 'no class unless given');
const value = field(list, 'Pieces', '12');
assert.deepEqual(list.children.slice(2).map(e => [e.tagName, e.textContent]), [['dt', 'Pieces'], ['dd', '12']]);
assert.equal(value, list.children[3], 'field gives back the value');
const button = segButton('all', 'All', 'Every floor');
assert.deepEqual([button.tagName, button.type, button.textContent, button.title, button.dataset.value],
                 ['button', 'button', 'All', 'Every floor', 'all']);

console.log('dom_words: ok');
