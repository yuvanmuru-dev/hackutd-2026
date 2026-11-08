import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { configuration } from '../src/config.js';
import { valid, safeOutbound } from '../src/contracts.js';
import { State } from '../src/state.js';
import { Service } from '../src/service.js';
import { BrainError, type Brain } from '../src/brain.js';
import { Transport, digest, type PhotonMessage } from '../src/photon.js';
import { keyword, understand } from '../src/intent.js';
import { Serial } from '../src/receiver.js';
import { imageDataUrl, inboundContent, MAX_IMAGE_BYTES } from '../src/images.js';

const env = {
  PHOTON_PROJECT_ID: 'pho_prj_00000000000000000000000001', PHOTON_API_KEY: 'pho_sk_test',
  PHOTON_AGENT_HANDLE: '+15555550101', OUTBOUND_ALLOWLIST: '+15555550102', USER_PHONE_usr_maya: '+15555550102',
};
const config = configuration(env);
const messageId = 'pho_msg_00000000000000000000000001';
function message(text = 'YES') {
  return { id: messageId, projectId: config.project, platform: 'imessage', status: 'received',
    createdAt: '2026-11-07T22:00:00Z', content: { type: 'text', format: 'plain', text },
    sentBy: { id: 'human', platform: 'imessage', kind: 'human', handle: '+15555550102' },
    receivedBy: { id: 'agent', platform: 'imessage', kind: 'agent', handle: config.agent },
    space: { id: 'space', platform: 'imessage', kind: 'direct' } } as unknown as PhotonMessage;
}
const envelope = { type: 'message.received', data: { projectId: config.project, object: { id: messageId } } };

test('configuration rejects unallowlisted mappings and other model families', () => {
  assert.throws(() => configuration({ ...env, USER_PHONE_usr_maya: '+15555550103' }));
  assert.throws(() => configuration({ ...env, MESSAGING_LLM_MODEL: 'another-model' }));
});

test('SendRequest fixture matches schema; unsafe text cannot leave the service', async () => {
  const fixture = JSON.parse(await readFile(new URL('../../contracts/fixtures/send.alert.json', import.meta.url), 'utf8'));
  assert.equal(valid('SendRequest', fixture), true);
  assert.equal(safeOutbound(fixture.text), true);
  assert.equal(valid('SendRequest', { ...fixture, unexpected: true }), false);
  assert.equal(safeOutbound('Please send your account PIN'), false);
  assert.equal(safeOutbound('Do not forget to send your code'), false);
  assert.equal(safeOutbound('We never ask for secrets, but share your password'), false);
  assert.equal(safeOutbound('Open help.example.com'), false);
  assert.equal(safeOutbound('Open https://example.com'), false);
  assert.equal(safeOutbound('Open help.exa\u200bmple.com'), false);
  assert.equal(safeOutbound('Reset your account PIN? Reply YES or NO'), true);
  assert.equal(safeOutbound('Someone on the call asked you to share your account PIN.'), true);
  assert.equal(safeOutbound('Don’t give your PIN to a caller.'), true);
  assert.equal(safeOutbound('A caller asked you to share your PIN, please send your code now.'), false);
  assert.equal(safeOutbound('A real agent will never ask you to turn off protection or give a PIN on the phone.'), true);
  assert.equal(safeOutbound('A real agent will never ask you to share a PIN, please send your code now.'), false);
});

test('Photon routing rejects outgoing messages, group messages, foreign lines and unknown senders', async () => {
  const state = new State(await mkdtemp(join(tmpdir(), 'titan-test-')));
  const transport = new Transport(config, state);
  assert.equal(transport.match(message())?.user, 'usr_maya');
  const m = message() as any;
  assert.equal(transport.match({ ...m, status: 'dispatched' }), undefined);
  assert.equal(transport.match({ ...m, space: { ...m.space, kind: 'group' } }), undefined);
  assert.equal(transport.match({ ...m, sentBy: { ...m.sentBy, handle: '+15555550103' } }), undefined);
  assert.equal(transport.match({ ...m, receivedBy: { ...m.receivedBy, handle: '+15555550104' } }), undefined);
});

async function harness(text = 'YES') {
  const dir = await mkdtemp(join(tmpdir(), 'titan-test-'));
  const state = new State(dir);
  await state.save({ ...state.data, prompts: { usr_maya: { caseId: 'case_test' } } });
  const calls: { path: string; body?: any }[] = [];
  const actions = [{ action_id: 'act_original', status: 'awaiting_approval' }];
  let fail = false;
  const detail = () => ({ case_id: 'case_test', user_id: 'usr_maya', actions });
  const brain = {
    openCase: async () => detail(),
    request: async (path: string, body?: unknown) => {
      calls.push({ path, body });
      return detail();
    },
    event: async (body: unknown) => { calls.push({ path: '/events', body }); if (fail) { fail = false; throw new BrainError(503); } return { duplicate: false }; },
  } as unknown as Pick<Brain, 'request' | 'event' | 'openCase'>;
  const realTransport = new Transport(config, state);
  const sent: string[] = [];
  const transport = {
    incoming: async () => message(text), match: realTransport.match.bind(realTransport),
    send: async (body: any) => { sent.push(body.text); return 'sent'; },
    hello: async () => { sent.push('hello'); },
    image: async (_id: string): Promise<string> => { throw new Error('Unexpected attachment'); },
  };
  return { state, dir, calls, actions, sent, brain, transport,
    service: new Service(config, state, transport, brain),
    failOnce: () => { fail = true; } };
}

test('duplicate delivery and restart forward once without approval calls or stored bodies', async () => {
  const h = await harness();
  await h.service.handle(envelope);
  await h.service.handle(envelope);
  const restored = new State(h.dir); await restored.load();
  await new Service(config, restored, h.transport, h.brain).handle(envelope);
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
  assert.equal(h.calls.filter(c => c.path === '/events').length, 1);
  assert.equal(h.calls.some(c => c.path.endsWith('/events') && c.path !== '/events'), false);
  const saved = await readFile(join(h.dir, 'checkpoint.json'), 'utf8');
  assert.equal(saved.includes('YES'), false);
  assert.equal(saved.includes('+15555550102'), false);
});

test('ambiguous event response retries the same event and original case', async () => {
  const h = await harness(); h.failOnce();
  await assert.rejects(() => h.service.handle(envelope));
  await h.state.save({ ...h.state.data, prompts: { usr_maya: { caseId: 'case_next' } } });
  h.actions.push({ action_id: 'act_next', status: 'awaiting_approval' });
  await h.service.handle(envelope);
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
  const posts = h.calls.filter(c => c.path === '/events');
  assert.equal(posts.length, 2);
  assert.deepEqual(posts[0].body, posts[1].body);
  assert.equal(posts[1].body.data.case_id, 'case_test');
  assert.ok(h.state.data.processed.includes(digest(messageId)));
});

test('YES and NO are forwarded verbatim; the brain alone chooses recovery actions', async () => {
  for (const text of ['YES', 'NO', "No that wasn't me", 'UNDO', 'REPORT']) {
    const h = await harness(text);
    await h.service.handle(envelope);
    assert.equal(h.calls.find(c => c.path === '/events')?.body.data.text, text);
    assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
    assert.equal(h.sent.length, 0);
    assert.equal(h.actions[0].status, 'awaiting_approval');
  }
});

test('forwarded links never become approval requests or get echoed outbound', async () => {
  const h = await harness('https://scam.example');
  await h.service.handle(envelope);
  assert.equal(h.calls.find(c => c.path === '/events')?.body.type, 'message.forwarded');
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
  assert.equal(h.sent.length, 0);
});

test('free-form disclosure goes to the brain unchanged without local model calls or approvals', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new Error('Unexpected local model call'); });
  const h = await harness('I told him my PIN');
  await h.service.handle(envelope);
  assert.equal(h.calls.find(c => c.path === '/events')?.body.data.text, 'I told him my PIN');
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
  assert.equal(keyword(' YES ')?.intent, 'yes');
  assert.equal(fetch.mock.calls.length, 0);
});

test('legacy action/intent receipts cannot trigger messaging-side approvals', async () => {
  const h = await harness();
  const legacy = JSON.parse(JSON.stringify(h.state.data));
  legacy.receipts[digest(messageId)] = { caseId: 'case_test', actionId: 'act_original', intent: 'yes' };
  await h.state.save(legacy);
  await h.service.handle(envelope);
  assert.equal(h.calls.filter(c => c.path === '/events').length, 1);
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
  assert.equal(h.actions[0].status, 'awaiting_approval');
});

test('serialized work stays ordered after a failed delivery', async () => {
  const serial = new Serial(); const steps: number[] = [];
  const a = serial.run(async () => { steps.push(1); throw new Error('test'); });
  const b = serial.run(async () => { steps.push(2); });
  await assert.rejects(a); await b;
  assert.deepEqual(steps, [1, 2]);
});

test('a stale fixture case falls back to the real case without approving a stale action', async () => {
  const h = await harness();
  const originalRequest = h.brain.request.bind(h.brain);
  h.brain.request = (async (path: string, body?: unknown) => {
    if (path === '/cases/case_stale') throw new BrainError(404);
    return originalRequest(path, body);
  }) as typeof h.brain.request;
  await h.state.save({ ...h.state.data, prompts: { usr_maya: { caseId: 'case_stale' } } });
  await h.service.handle(envelope);
  assert.equal(h.calls.find(c => c.path === '/events')?.body.data.case_id, 'case_test');
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
});

test('Nano disclosures cannot turn into approvals; malformed model output fails closed', async (t) => {
  const nanoConfig = { ...config, nvidiaKey: 'test-only' };
  const requestedModels: string[] = [];
  let content = JSON.stringify({ intent: 'yes', shared: ['pin'] });
  t.mock.method(globalThis, 'fetch', async (_input: unknown, options: RequestInit) => {
    requestedModels.push(JSON.parse(String(options.body)).model);
    return new Response(JSON.stringify({ choices: [{ message: { content } }] }), { status: 200 });
  });
  assert.equal((await understand('I told him my PIN', nanoConfig)).intent, 'info');
  content = JSON.stringify({ intent: 'approve_all', shared: [] });
  await assert.rejects(() => understand('untrusted text', nanoConfig));
  assert.deepEqual(requestedModels, [config.llmModel, config.llmModel]);
});

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jw1kAAAAASUVORK5CYII=', 'base64');

test('image validation accepts PNG/JPEG, rejects MIME mismatches and enforces 5 MB', () => {
  assert.equal(imageDataUrl('image/png', PNG), `data:image/png;base64,${PNG.toString('base64')}`);
  assert.match(imageDataUrl('image/jpeg', Uint8Array.from([255, 216, 255, 217])), /^data:image\/jpeg;base64,/);
  assert.throws(() => imageDataUrl('image/jpeg', PNG), /unsupported_image_type/);
  assert.throws(() => imageDataUrl('image/svg+xml', PNG), /unsupported_image_type/);
  assert.throws(() => imageDataUrl('image/png', new Uint8Array(MAX_IMAGE_BYTES + 1)), /image_too_large/);
  assert.deepEqual(inboundContent({ type: 'group', parts: [{ type: 'text', format: 'plain', text: 'caption' },
    { type: 'attachment', attachmentId: 'attachment_1' }] }), { text: 'caption', attachments: ['attachment_1'] });
});

test('attachment download stays project-scoped and rejects oversize metadata before fetching bytes', async (t) => {
  const state = new State(await mkdtemp(join(tmpdir(), 'titan-test-')));
  const transport = new Transport(config, state);
  let sizeBytes = PNG.length, contentType = 'image/png', projectId = config.project;
  const meta = t.mock.method(transport.api.projects, 'getAttachment', async () => ({ id: 'attachment_1', projectId,
    contentType, sizeBytes, createdAt: '2026-11-07T22:00:00Z', updatedAt: '2026-11-07T22:00:00Z' }));
  const download = t.mock.method(transport.api.projects, 'downloadAttachment', async () => new Blob([Uint8Array.from(PNG)]));
  assert.match(await transport.image('attachment_1'), /^data:image\/png;base64,/);
  const metadataInput = meta.mock.calls[0]?.arguments[0];
  const downloadInput = download.mock.calls[0]?.arguments[0];
  assert.ok(metadataInput); assert.ok(downloadInput);
  assert.deepEqual(metadataInput.path, { id: config.project, attachmentId: 'attachment_1' });
  assert.deepEqual(downloadInput.path, { id: config.project, attachmentId: 'attachment_1' });
  sizeBytes = MAX_IMAGE_BYTES + 1;
  await assert.rejects(() => transport.image('attachment_1'), /image_too_large/);
  sizeBytes = PNG.length; contentType = 'application/pdf';
  await assert.rejects(() => transport.image('attachment_1'), /unsupported_image_type/);
  contentType = 'image/png'; projectId = 'pho_prj_other';
  await assert.rejects(() => transport.image('attachment_1'), /attachment_project_mismatch/);
  assert.equal(download.mock.calls.length, 1);
});

test('a forwarded screenshot with YES caption becomes image data, never a recovery approval', async () => {
  const h = await harness();
  h.transport.incoming = async () => ({ ...message(), content: { type: 'group', parts: [
    { type: 'text', format: 'plain', text: 'YES' }, { type: 'attachment', attachmentId: 'attachment_1' },
  ] } } as PhotonMessage);
  let downloads = 0;
  h.transport.image = async () => { downloads++; return imageDataUrl('image/png', PNG); };
  await h.service.handle(envelope);
  await h.service.handle(envelope);
  const posts = h.calls.filter(c => c.path === '/events');
  assert.equal(posts.length, 1);
  assert.equal(posts[0].body.type, 'message.forwarded');
  assert.equal(Object.hasOwn(posts[0].body.data, 'text'), false, 'D-047: images must not carry text');
  assert.equal(valid('Event', posts[0].body), true);
  assert.match(posts[0].body.data.image_url, /^data:image\/png;base64,/);
  assert.equal(h.calls.some(c => c.path.startsWith('/actions')), false);
  assert.equal(downloads, 1);
  const saved = await readFile(join(h.dir, 'checkpoint.json'), 'utf8');
  assert.equal(saved.includes(PNG.toString('base64')), false);
  assert.equal(saved.includes('YES'), false);
});

test('partial multi-image failures retain stable per-image event IDs on replay', async () => {
  const h = await harness();
  h.transport.incoming = async () => ({ ...message(), content: { type: 'group', parts: [
    { type: 'attachment', attachmentId: 'first' }, { type: 'attachment', attachmentId: 'second' },
  ] } } as PhotonMessage);
  let fail = true;
  h.transport.image = async id => {
    if (id === 'second' && fail) { fail = false; throw new Error('temporary provider failure'); }
    return imageDataUrl('image/png', PNG);
  };
  await assert.rejects(() => h.service.handle(envelope));
  assert.equal(h.state.data.processed.includes(digest(messageId)), false);
  await h.service.handle(envelope);
  const posts = h.calls.filter(c => c.path === '/events');
  assert.equal(posts.length, 3);
  assert.equal(posts[0].body.event_id, posts[1].body.event_id);
  assert.notEqual(posts[1].body.event_id, posts[2].body.event_id);
  assert.equal(new Set(posts.map(p => p.body.event_id)).size, 2);
  assert.ok(h.state.data.processed.includes(digest(messageId)));
});

test('unknown senders cannot trigger attachment download or image forwarding', async () => {
  const h = await harness();
  h.transport.incoming = async () => ({ ...message(), sentBy: { platform: 'imessage', kind: 'human', id: 'unknown',
    handle: '+15555550103' }, content: { type: 'attachment', attachmentId: 'attachment_1' } } as PhotonMessage);
  await h.service.handle(envelope);
  assert.equal(h.calls.length, 0);
});
