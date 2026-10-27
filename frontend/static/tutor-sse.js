/* Bounded SSE framing; shared by the browser and byte-boundary regression tests. */
(function (root) {
  class SSEParser {
    constructor(onEvent) { this.onEvent = onEvent; this.buffer = ''; this.event = ''; this.data = []; this.size = 0; }
    feed(text, final = false) {
      this.buffer += text;
      if (this.buffer.length + this.size > 262144) throw new Error('流式帧过大');
      let index;
      while ((index = this.buffer.search(/[\r\n]/)) >= 0) {
        const ending = this.buffer[index];
        if (ending === '\r' && index === this.buffer.length - 1 && !final) break;
        const length = ending === '\r' && this.buffer[index + 1] === '\n' ? 2 : 1;
        const line = this.buffer.slice(0, index); this.buffer = this.buffer.slice(index + length);
        if (!line) {
          if (this.data.length) {
            const name = this.event || 'message'; const value = JSON.parse(this.data.join('\n'));
            this.onEvent(name, value);
          }
          this.event = ''; this.data = []; this.size = 0;
        } else if (!line.startsWith(':')) {
          const colon = line.indexOf(':');
          const field = colon < 0 ? line : line.slice(0, colon);
          let value = colon < 0 ? '' : line.slice(colon + 1); if (value.startsWith(' ')) value = value.slice(1);
          if (field === 'event') this.event = value;
          if (field === 'data') { this.data.push(value); this.size += value.length; }
        }
      }
      if (final && (this.buffer || this.data.length)) throw new Error('回答流未完整结束');
    }
  }
  async function readSSE(response, onEvent) {
    if (!response.body || !response.headers.get('Content-Type')?.startsWith('text/event-stream')) throw new Error('未收到回答流');
    const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', {fatal: true});
    const parser = new SSEParser(onEvent); let state = 'start';
    parser.onEvent = (name, data) => {
      if (name === 'meta' && ['start', 'tools'].includes(state)) state = 'tools';
      else if (name === 'delta' && ['tools', 'stream'].includes(state) && typeof data.text === 'string') state = 'stream';
      else if (name === 'done' && ['tools', 'stream'].includes(state) && Number.isInteger(data.message_id)) state = 'done';
      else if (name === 'error' && ['tools', 'stream'].includes(state)) { state = 'error'; onEvent(name, data); throw new Error(data.error || '回答中断'); }
      else throw new Error('回答流顺序无效');
      onEvent(name, data);
    };
    try {
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        parser.feed(decoder.decode(value, {stream: true}));
      }
      parser.feed(decoder.decode(), true);
      if (state !== 'done') throw new Error('回答已中断，请重新打开历史后继续');
    } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
  }
  root.CampusSSE = {SSEParser, readSSE};
  if (typeof module !== 'undefined') module.exports = root.CampusSSE;
})(typeof window === 'undefined' ? globalThis : window);
