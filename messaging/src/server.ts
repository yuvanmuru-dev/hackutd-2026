import { createServer } from 'node:http';
import { configuration } from './config.js';
import { State } from './state.js';
import { Transport, DeliveryError } from './photon.js';
import { Brain } from './brain.js';
import { Service } from './service.js';
import { Serial, receive } from './receiver.js';

async function main() {
  const config = configuration();
  const state = new State(config.stateDir);
  await state.load();
  const service = new Service(config, state, new Transport(config, state), new Brain(config.brain));
  const serial = new Serial();
  const server = createServer(async (request, response) => {
    const reply = (status: number, body: unknown) => {
      response.writeHead(status, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(body));
    };
    if (request.url !== '/internal/send' || request.method !== 'POST') { reply(404, { error: 'not_found' }); return; }
    try {
      let size = 0; const chunks: Buffer[] = [];
      for await (const chunk of request) {
        size += Buffer.byteLength(chunk);
        if (size > 16_384) { reply(413, { error: 'request_too_large' }); return; }
        chunks.push(Buffer.from(chunk));
      }
      let body: unknown;
      try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
      catch { reply(422, { error: 'invalid_json' }); return; }
      await serial.run(() => service.send(body));
      // Photon accepted asynchronous dispatch. This does not assert phone delivery.
      reply(200, {});
    } catch (error) {
      if (error instanceof DeliveryError) reply(error.status, { error: error.code });
      else { console.error(JSON.stringify({ event: 'outbound_failed' })); reply(502, { error: 'delivery_failed' }); }
    }
  });
  server.requestTimeout = 30_000;
  const receiver = receive(config, state, serial, event => service.handle(event), () => {
    server.close(); process.exitCode = 1;
    setTimeout(() => process.exit(1), 1000).unref();
  });
  server.listen(config.port, '127.0.0.1', () => console.log(JSON.stringify({ event: 'messaging_listening', port: config.port })));
  const shutdown = () => { receiver.close(); server.close(); };
  process.on('SIGTERM', shutdown); process.on('SIGINT', shutdown);
}
main().catch(() => { console.error(JSON.stringify({ event: 'messaging_start_failed', hint: 'Check environment and checkpoint configuration' })); process.exitCode = 1; });
