// ESLint's settings for web_names.py (run it through that script, which names the scratch folder holding ESLint and
// the `globals` package): the page's modules (tools/viewer/web/*.js, not vendor/) as ES modules in the browser, checked
// for three things only: a name neither declared, imported nor a known global (no-undef), an import nothing uses, and
// an assignment to an imported name (no-import-assign: a write that must go through the owner's setter, which would
// throw only when its line runs).
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const scratch = process.env.WEB_NAMES_SCRATCH;
if (!scratch) throw new Error('run this through tools/viewer/tests/web_names.py: it names the scratch folder holding ESLint and globals');
const browser = JSON.parse(readFileSync(join(scratch, 'node_modules', 'globals', 'globals.json'), 'utf8')).browser;

// Window properties whose names read as a variable of the page's own (the list of the confusing-browser-globals
// package, and `viewport`): app.js declares `open`, `moveTo` and `viewport` itself, and many functions take a `name`,
// `status`, `parent` or `top`. A function moved out of its module without its import would read the window's instead
// and not throw, so these are not known globals here: a bare use of one is reported.
const CONFUSING = ['addEventListener', 'blur', 'close', 'closed', 'confirm', 'defaultStatus', 'defaultstatus', 'event',
  'external', 'find', 'focus', 'frameElement', 'frames', 'history', 'innerHeight', 'innerWidth', 'length', 'location',
  'locationbar', 'menubar', 'moveBy', 'moveTo', 'name', 'onblur', 'onerror', 'onfocus', 'onload', 'onresize', 'onunload',
  'open', 'opener', 'opera', 'outerHeight', 'outerWidth', 'pageXOffset', 'pageYOffset', 'parent', 'print',
  'removeEventListener', 'resizeBy', 'resizeTo', 'screen', 'screenLeft', 'screenTop', 'screenX', 'screenY', 'scroll',
  'scrollbars', 'scrollBy', 'scrollTo', 'scrollX', 'scrollY', 'self', 'status', 'statusbar', 'stop', 'toolbar', 'top',
  'viewport'];
const known = Object.fromEntries(Object.entries(browser).filter(([n]) => !CONFUSING.includes(n)));
// The page's own uses of those, by the window's name on purpose (no module declares them):
known.location = 'readonly';    // app.js: the address's map, project or prefab read, set, and the page reloaded
known.history = 'readonly';     // app.js: the address changed without a reload (replaceState)

// An import binding no code of its module reads (ESLint's no-unused-vars covers every name; this is its import part).
// `export { name }` of an imported name counts as a use.
const unusedImport = {
  meta: { type: 'problem', schema: [], messages: { unused: "'{{name}}' is imported but never used" } },
  create(context) {
    return {
      'Program:exit'(node) {
        const scopes = [context.sourceCode.getScope(node)];
        for (let k = 0; k < scopes.length; k++) scopes.push(...scopes[k].childScopes.filter(s => s.type === 'module'));
        for (const scope of scopes.filter(s => s.type === 'module'))
          for (const variable of scope.variables)
            if (variable.defs.some(d => d.type === 'ImportBinding') && variable.references.length === 0)
              context.report({ node: variable.identifiers[0], messageId: 'unused', data: { name: variable.name } });
      },
    };
  },
};

export default [
  { ignores: ['**/vendor/**'] },      // (three.js, the page's own copy: not the page's code)
  {
    files: ['**/*.js'],
    // (the exceptions live here, each with its reason, never in the page's own comments)
    linterOptions: { noInlineConfig: true, reportUnusedDisableDirectives: 'off' },
    // ES modules of the latest syntax (its built-in globals come with it); `three` and `three/addons/` are the import
    // map's (index.html), which no rule here resolves
    languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: known },
    plugins: { 'web-names': { rules: { 'unused-import': unusedImport } } },
    rules: {
      'no-undef': 'error',
      'no-import-assign': 'error',
      'web-names/unused-import': 'error',
    },
  },
];
