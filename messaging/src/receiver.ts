import { io } from 'socket.io-client';
import type { Config } from './config.js';
import type { State } from './state.js';
import { errorFields } from './logging.js';

export class Serial {
  private queue: Promise<unknown> = Promise.resolve();
  run<T>(work: () => Promise<T>): Promise<T> {
    const next = this.queue.then(work);
    this.queue = next.catch(() => {});
    return next;
  }
}

export function receive(config: Config, state: State, serial: Serial, handle: (event: unknown) => Promise<void>, fatal: () => void) {
  let pending = 0;
  let stopped = false;
  let ready = false;
  const socket = io('https://api.photon.codes', {
    path: `/v1/projects/${config.project}/events/ws`, addTrailingSlash: false,
    transports: ['websocket'], extraHeaders: { Authorization: `Bearer ${config.key}` }, autoConnect: false,
  });
  const stop = () => {
    if (stopped) return;
    stopped = true; ready = false; socket.disconnect(); fatal();
  };
  socket.on('connect', () => {
    socket.timeout(10_000).emit('subscribe', { startSeq: state.data.cursor, apiVersion: '2026-07-01' }, (error: unknown, result: { ok?: boolean } | undefined) => {
      if (error || !result?.ok) { console.error(JSON.stringify({ event: 'photon_subscribe_failed' })); stop(); }
      else { ready = true; console.log(JSON.stringify({ event: 'photon_subscribed' })); }
    });
  });
  socket.on('disconnect', () => { ready = false; });
  socket.on('delivery', (event: unknown, metadata: { seq?: number; replyExpected?: boolean }) => {
    if (stopped) return;
    const seq = metadata?.seq;
    if (!Number.isSafeInteger(seq) || seq! < 1 || metadata.replyExpected || ++pending > 128) { stop(); return; }
    void serial.run(async () => {
      if (stopped || seq! <= state.data.cursor) return;
      await handle(event);
      await state.save({ ...state.data, cursor: seq! });
      console.log(JSON.stringify({ event: 'photon_delivery_processed', seq }));
    }).catch(error => {
      console.error(JSON.stringify({ event: 'photon_processing_failed', seq, ...errorFields(error) })); stop();
    }).finally(() => { pending--; });
  });
  socket.on('delivery_error', (error: { fatal?: boolean }) => {
    console.error(JSON.stringify({ event: 'photon_delivery_error' }));
    if (error.fatal) stop();
  });
  socket.on('connect_error', () => { console.warn(JSON.stringify({ event: 'photon_connection_failed' })); });
  socket.connect();
  return { close: () => { stopped = true; socket.disconnect(); }, ready: () => ready };
}
