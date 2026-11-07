import { Photon } from '@photon-ai/api';
import { createHash } from 'node:crypto';
import type { Config } from './config.js';
import type { State, Route } from './state.js';
import { safeOutbound } from './contracts.js';
import type { SendRequest } from './contract-types.js';

export type PhotonMessage = Awaited<ReturnType<Photon['projects']['getMessage']>>;
export const digest = (value: string) => createHash('sha256').update(value).digest('hex');

export class DeliveryError extends Error {
  constructor(public code: string, public status = 502) { super(code); }
}

export class Transport {
  readonly api: Photon;
  constructor(readonly config: Config, readonly state: State) {
    this.api = new Photon({ headers: { Authorization: `Bearer ${config.key}` } });
  }
  match(message: PhotonMessage): { user: string; route: Route } | undefined {
    if (!message || (message.platform !== 'imessage' && message.platform !== 'sms') || message.status !== 'received') return;
    if ((message.space.platform !== 'imessage' && message.space.platform !== 'sms')
        || (message.sentBy.platform !== 'imessage' && message.sentBy.platform !== 'sms')
        || !message.receivedBy || (message.receivedBy.platform !== 'imessage' && message.receivedBy.platform !== 'sms')) return;
    if (message.space.platform !== message.platform || message.sentBy.platform !== message.platform
        || message.receivedBy.platform !== message.platform) return;
    if (message.projectId !== this.config.project || message.space.kind !== 'direct'
        || message.sentBy.kind !== 'human' || message.receivedBy?.kind !== 'agent'
        || message.receivedBy.handle !== this.config.agent
        || message.sentBy.id === message.receivedBy.id) return;
    const number = message.sentBy.handle;
    if (!this.config.allowlist.has(number)) return;
    const user = [...this.config.users].find(([, phone]) => phone === number)?.[0];
    if (!user) return;
    return { user, route: { spaceId: message.space.id, senderId: message.receivedBy.id } };
  }
  async incoming(id: string) {
    return this.api.projects.getMessage({ path: { id: this.config.project, messageId: id } });
  }
  async findRoute(user: string, channel: 'imessage' | 'sms'): Promise<Route> {
    const phone = this.config.users.get(user);
    if (!phone || !this.config.allowlist.has(phone)) throw new DeliveryError('recipient_not_allowlisted', 403);
    // Resolve only from real incoming conversations; never create a line or buy a number.
    let pageToken: string | undefined;
    do {
      const page = await this.api.projects.listMessages({ path: { id: this.config.project },
        query: { direction: 'received', platform: channel, order: 'desc', pageSize: 100, ...(pageToken ? { pageToken } : {}) } });
      if (!page) throw new DeliveryError('photon_empty_response');
      for (const message of page.items) {
        const match = this.match(message);
        if (match?.user === user) return match.route;
      }
      pageToken = page.nextPageToken;
    } while (pageToken);
    throw new DeliveryError('teammate_must_message_line_first', 409);
  }
  async send(request: SendRequest, idempotencyKey?: string) {
    if (!safeOutbound(request.text)) throw new DeliveryError('unsafe_outbound_text', 422);
    const route = await this.findRoute(request.user_id, request.channel);
    const result = await this.api.projects.sendMessage({ path: { id: this.config.project },
      headers: { 'idempotency-key': idempotencyKey ?? `titan:${digest(JSON.stringify(request))}` },
      body: { ...route, content: { type: 'text', format: 'plain', text: request.text } } });
    if (!result) throw new DeliveryError('photon_empty_response');
    return result.id;
  }
  async hello(message: PhotonMessage, route: Route) {
    if (!message || typeof message.id !== 'string') return;
    await this.api.projects.sendMessage({ path: { id: this.config.project },
      headers: { 'idempotency-key': `titan:hello:${digest(message.id)}` },
      body: { ...route, parentMessageId: message.id,
        content: { type: 'text', format: 'plain', text: 'Hello from Titan! Your messaging connection is working.' } } });
  }
}
