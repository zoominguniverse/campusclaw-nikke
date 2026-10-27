const assert = require('node:assert/strict');
const {SSEParser, readSSE} = require('../static/tutor-sse.js');
const encode = new TextEncoder();
const protocol = 'event: meta\r\ndata: {"status":"ok","skill":null,"citations":[]}\r\n\r\nevent: delta\ndata: {"text":"中文😀第一段"}\n\n: keep-alive\n\nevent: delta\ndata: {"text":"第二段"}\n\nevent: done\ndata: {"message_id":7}\n\n';
async function test() {
  const bytes = encode.encode(protocol);
  // Every byte boundary, including UTF-8 code points and CRLF separators.
  for (let boundary = 1; boundary < bytes.length; boundary++) {
    const chunks = [bytes.slice(0, boundary), bytes.slice(boundary)];
    const response = new Response(new ReadableStream({start(controller) { chunks.forEach(chunk => controller.enqueue(chunk)); controller.close(); }}), {headers: {'Content-Type': 'text/event-stream'}});
    const events = []; await readSSE(response, (name, data) => events.push([name, data]));
    assert.deepEqual(events.map(item => item[0]), ['meta', 'delta', 'delta', 'done']);
    assert.equal(events.filter(item => item[0] === 'delta').map(item => item[1].text).join(''), '中文😀第一段第二段');
  }
  for (const invalid of [protocol.replace('event: done\ndata: {"message_id":7}\n\n', ''), protocol + 'event: delta\ndata: {"text":"late"}\n\n', protocol.replace('event: done\ndata: {"message_id":7}', 'event: error\ndata: {"error":"中断"}')]) {
    await assert.rejects(readSSE(new Response(invalid, {headers: {'Content-Type': 'text/event-stream'}}), () => {}));
  }
  assert.throws(() => new SSEParser(() => {}).feed('a'.repeat(262145)));
  assert.throws(() => new SSEParser(() => {}).feed('event: meta\ndata: {\n\n'));
  const update = 'event: meta\ndata: {"status":"ok","skill":null,"citations":[],"tool_calls":[{"call_id":"a","status":"ok","text":"工具提示😀"}]}\n\n';
  const repeated = protocol.replace('event: delta\ndata: {"text":"中文😀第一段"}', update + 'event: delta\ndata: {"text":"中文😀第一段"}');
  const toolBytes = encode.encode(repeated);
  for (let boundary = 1; boundary < toolBytes.length; boundary++) {
    const chunks = [toolBytes.slice(0, boundary), toolBytes.slice(boundary)];
    const response = new Response(new ReadableStream({start(controller) { chunks.forEach(chunk => controller.enqueue(chunk)); controller.close(); }}), {headers: {'Content-Type': 'text/event-stream'}});
    const events = []; await readSSE(response, (name, data) => events.push([name, data]));
    assert.deepEqual(events.map(item => item[0]), ['meta', 'meta', 'delta', 'delta', 'done']);
    assert.equal(events.filter(item => item[0] === 'delta').map(item => item[1].text).join(''), '中文😀第一段第二段');
  }
  await assert.rejects(readSSE(new Response(protocol.replace('event: done', update + 'event: done'), {headers: {'Content-Type': 'text/event-stream'}}), () => {}), /顺序/);
  console.log('SSE byte boundaries, CRLF, multiple frames, EOF, errors and budget passed');
}
test().catch(error => { console.error(error); process.exitCode = 1; });
