// Play in game's words and requests (web/play.js; moved out of app.js, review finding 22): why a play can't start,
// a mission as the server takes it, and the "Starting XCOM" message. Run: node tools/viewer/tests/play_test.mjs
import assert from 'node:assert/strict';
import { missionRequest, playBlocked, playedMessage } from '../web/play.js';

// why not: unknown yet, the server's error, the install, the launch
assert.equal(playBlocked(null), null);
assert.equal(playBlocked({ error: 'offline' }), 'offline');
assert.equal(playBlocked({ install: { ready: false, why: 'XCOM is running' } }), 'XCOM is running');
assert.equal(playBlocked({ install: { ready: false } }), 'asking the server');
assert.equal(playBlocked({ install: { ready: true }, launch: { how: null, why: 'no Steam' } }), 'no Steam');
assert.equal(playBlocked({ install: { ready: true }, launch: { how: 'steam' } }), null);

// a record's index, or an added kind
assert.equal(missionRequest('3'), 3);
assert.equal(missionRequest('kind:bomb'), 'bomb');
assert.equal(missionRequest('x'), 0);

// the message: what is played, the launcher, saving's key, the squad, what the play goes without
const label = id => ({ URB_Bar: 'Bar' }[id] ?? id);
assert.equal(playedMessage({ played: { kind: 'map', map: 'URB_Bar', how: 'steam', mission: { label: 'Abduction' } } }, label),
             'Starting XCOM: Bar (original map), Abduction.\nPick Enemy Within if the game\'s launcher asks.');
assert.equal(playedMessage({ played: { kind: 'project', project: { name: 'Pub', revision: 4 }, quick: true, how: 'dry', saving: { key: 'F5' },
                                       squad: { name: 'Six', count: 6, warnings: ['a'] }, mission: { missing: ['No bomb.'] }, note: 'Noted.' } }, label),
             ['Starting XCOM is left out here (serve --dry-play): Pub, revision 4 (lighting not baked).', 'At the main menu, press F5 to start the battle.',
              'Squad: Six, 6 units (1 warning: Test squad setup lists them).', 'No bomb.', 'Noted.'].join('\n'));
console.log('play: ok');
