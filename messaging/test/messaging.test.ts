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
