// The server through api.js, the browser's storage through storage.js (ARCHITECTURE.md, "The page", Modules;
// follow-ups 3.28 and 3.20): the page's modules read for the browser's fetch, which only api.js uses (call, ask,
// sendPng) besides the plain fetches named here, each with why it stays, and for localStorage and sessionStorage, which
// only storage.js uses. A new one fails here: ask the server through api.js and keep a value through storage.js, or
// name the place here with its reason and in ARCHITECTURE.md. So too a module's own plural or short (follow-up 3.22):
// dom_words.js has them, and only the variants named here differ. The modules are read as code: comments and the text
// of strings are left out, a template's ${...} kept. Run: node tools/viewer/tests/one_home_test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const web = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..', 'web');

// name -> module -> [how many, why]
const ALLOWED = {
  fetch: {
    'api.js': [3, 'the one home: call, ask and sendPng'],
    'effects_wiring.js': [1, "the wave's range probe: one byte asked again for the server's words on a wave the browser could not play"],
    'loading.js': [1, "the scene's layout read with its progress (call reads an answer whole)"],
    'map_settings.js': [1, "the background sound's range probe: one byte asked again for the server's words on a wave the browser could not play"],
    'map_picture.js': [2, "the project's kept picture and a map's own picture, read as blobs"],
    'prefabs.js': [1, "a prefab's picture read as a blob, for its duplicate"],
    'scene_pieces.js': [1, "a texture file of the game's blocks (DDS) read as bytes for the GPU"],
    'baked_light.js': [1, "a lightmap atlas (DDS) read as bytes, its blocks packed into the map's one atlas"],
  },
  localStorage: { 'storage.js': [6, 'the one home: recall (an older key moved), remember, forget'] },
  sessionStorage: { 'storage.js': [3, "the one home of a tab's own: recallSession, rememberSession, forgetSession"] },
};

const KEYWORD = /(?:^|[^\w$])(?:return|typeof|case|do|else|in|of|new|delete|void|throw|yield|await)$/;
/** `text` (a module's source) as code: comments gone, a string's text gone (its quotes kept), a template's text gone and
 *  its ${...} kept, a regex literal's body gone. Throws when the module does not end as it began (an open string,
 *  template or brace), so that a misread can't hide what it should find. */
function codeOf(text) {
  let out = '', i = 0, prev = '', braces = 0;
  const templates = [];       // the brace depth each open ${ of a template began at
  const regexMay = () => !prev || /[(,=:[!&|?{};+\-*%<>~^]/.test(prev) || KEYWORD.test(out.trimEnd());
  while (i < text.length) {
    const c = text[i];
    if (c === '/' && text[i + 1] === '/') { while (i < text.length && text[i] !== '\n') i++; continue; }
    if (c === '/' && text[i + 1] === '*') {
      const end = text.indexOf('*/', i + 2);
      if (end < 0) throw new Error('a comment that does not end');
      i = end + 2; out += ' '; continue;
    }
    if (c === "'" || c === '"') {
      for (i++; text[i] !== c; i += text[i] === '\\' ? 2 : 1) if (i >= text.length || text[i] === '\n') throw new Error('a string that does not end');
      i++; out += c + c; prev = c; continue;
    }
    if (c === '`' || (c === '}' && templates.at(-1) === braces)) {
      if (c === '}') templates.pop();
      for (i++; text[i] !== '`' && !(text[i] === '$' && text[i + 1] === '{'); i += text[i] === '\\' ? 2 : 1)
        if (i >= text.length) throw new Error('a template that does not end');
      if (text[i] === '`') { i++; out += '``'; prev = '`'; } else { i += 2; templates.push(braces); out += '`${'; prev = '{'; }
      continue;
    }
    if (c === '/' && regexMay()) {
      let inClass = false;
      for (i++; inClass || text[i] !== '/'; i++) {
        if (i >= text.length || text[i] === '\n') throw new Error('a regex that does not end');
        if (text[i] === '\\') i++; else if (text[i] === '[') inClass = true; else if (text[i] === ']') inClass = false;
      }
      for (i++; /[a-z]/i.test(text[i] ?? ''); i++);
      out += '/r/'; prev = '/'; continue;
    }
    if (c === '{') braces++;
    else if (c === '}') braces--;
    out += c;
    if (!/\s/.test(c)) prev = c;
    i++;
  }
  if (braces !== 0 || templates.length) throw new Error(`ends with ${braces} braces and ${templates.length} templates open`);
  return out;
}

/** How many times each of `names` is used in `code` as the browser's own (not a property of something else, but
 *  window.<name>, globalThis.<name> or self.<name> counted). */
function uses(code, names) {
  const found = {};
  for (const name of names) {
    const pattern = new RegExp(`(?:(?<![\\w$.])|(?<=(?<![\\w$.])(?:window|globalThis|self)\\.))${name}(?![\\w$])`, 'g');
    const n = [...code.matchAll(pattern)].length;
    if (n) found[name] = n;
  }
  return found;
}

// the reading itself
const sample = "a = '// fetch(' + `x ${fetch(`/y/${n}`)} z` /* fetch( */; // fetch(\nb = /fetch\\(/g.test(s) ? 1 / 2 : f.fetch(c); window.fetch(d);";
assert.deepEqual(uses(codeOf(sample), ['fetch']), { fetch: 2 });
assert.equal(codeOf("x = { a: `${ { b: 1 }.b }` }; y = '}'"), "x = { a: `${ { b: 1 }.b `` }; y = ''");
assert.throws(() => codeOf('a = `open'), /template/);
assert.throws(() => codeOf('f() {'), /braces/);

// the page's modules
const names = Object.keys(ALLOWED);
const files = fs.readdirSync(web).filter(f => f.endsWith('.js')).sort();
assert.ok(files.length > 90, files.length);
const problems = [];
for (const file of files) {
  let code;
  try { code = codeOf(fs.readFileSync(path.join(web, file), 'utf8')); } catch (error) { problems.push(`${file}: not read (${error.message})`); continue; }
  const found = uses(code, names);
  for (const name of names) {
    const [allowed = 0, why = null] = ALLOWED[name][file] ?? [];
    const n = found[name] ?? 0;
    if (n !== allowed) problems.push(`${file}: ${name} ${n} times, ${allowed} named here${why ? ` (${why})` : ''}`);
  }
}
for (const name of names)
  for (const file of Object.keys(ALLOWED[name])) if (!files.includes(file)) problems.push(`${file}: named for ${name}, not a module of the page`);

// The words helpers (follow-up 3.22): dom_words.js' plural and short are declared nowhere else, but for the variants
// named here, each with how it differs (its comment in the module says the same).
const WORDS = {
  plural: {
    'dom_words.js': 'the one home',
    'library.js': "groups the count's digits as the browser's language does",
    'precache.js': "groups the count's digits in British English",
  },
  short: {
    'dom_words.js': 'the one home',
    'effects_rules.js': "'' for a missing path",
    'spawn_rules.js': "'' for a missing path",
    'spawns_view.js': "'' for a missing path",
  },
};
/** Whether `code` declares a function named `name` (a function statement, or a const, let or var given an arrow). */
const declares = (code, name) => new RegExp(`\\bfunction\\s+${name}\\s*\\(|\\b(?:const|let|var)\\s+${name}\\s*=\\s*(?:async\\s+)?(?:\\([^()]*\\)|[\\w$]+)\\s*=>`).test(code);
assert.ok(declares('const plural = (n, word) => n;', 'plural') && declares('function short(p) {}', 'short'));
assert.ok(!declares('const short = plan.free != null && need > plan.free;', 'short') && !declares('const shortName = a => a;', 'short'));
for (const file of files) {
  const code = codeOf(fs.readFileSync(path.join(web, file), 'utf8'));
  for (const name of Object.keys(WORDS))
    if (declares(code, name) !== Boolean(WORDS[name][file]))
      problems.push(`${file}: ${declares(code, name) ? `its own ${name}: import dom_words.js' (or name it here with how it differs)` : `${name} named here, not declared`}`);
}
assert.deepEqual(problems, []);
console.log(`one home: ok (${files.length} modules)`);
