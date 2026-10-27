const assert = require('node:assert/strict');
const {mergeCalls} = require('../static/tutor-tools.js');
const first = {call_id: 'a', ref: 'tool@server', status: 'ok'};
assert.deepEqual(mergeCalls([first], [first, {call_id: 'b', status: 'denied'}]).map(c => c.call_id), ['a', 'b']);
assert.equal(mergeCalls([first], [{call_id: 'a', status: 'error'}])[0].status, 'error');
assert.deepEqual(mergeCalls([first]), [first]);
console.log('tool metadata merge passed');
