import type { Config } from './config.js';
import { Brain, BrainError } from './brain.js';
import { DeliveryError, digest, Transport } from './photon.js';
import type { State, Prompt } from './state.js';
import { valid } from './contracts.js';
import type { CaseDetail, SendRequest } from './contract-types.js';

export class Service {
  constructor(readonly config: Config, readonly state: State,
    readonly transport: Pick<Transport, 'send' | 'incoming' | 'match' | 'hello'>,
    readonly brain: Pick<Brain, 'request' | 'event' | 'openCase'>) {}

  async send(body: unknown) {
    if (!valid('SendRequest', body)) throw new DeliveryError('invalid_send_request', 422);
    const request = body as SendRequest;
    const id = await this.transport.send(request);
    if (request.expects_reply) {
      await this.state.save({ ...this.state.data, prompts: { ...this.state.data.prompts,
        [request.user_id]: { caseId: request.case_id } } });
    }
    return id;
  }

  async handle(event: unknown) {
    if (!event || typeof event !== 'object') throw new Error('invalid_photon_event');
    const envelope = event as { type?: string; data?: { projectId?: string; object?: { id?: string } } };
    if (envelope.type !== 'message.received') return;
    if (envelope.data?.projectId !== this.config.project) throw new Error('project_mismatch');
    const id = envelope.data.object?.id;
    if (typeof id !== 'string' || !/^pho_msg_[0-7][0-9a-hjkmnp-tv-z]{25}$/.test(id)) throw new Error('invalid_message_id');
    const hash = digest(id);
    if (this.state.data.processed.includes(hash)) return;
    // Use the API's validated authoritative message, not arbitrary event payload fields.
    const message = await this.transport.incoming(id);
    const match = this.transport.match(message);
    if (!match || !message || (message.platform !== 'imessage' && message.platform !== 'sms')) return;
    const content = message.content;
    if (content.type !== 'text' || content.format !== 'plain') {
      // Do not acknowledge unsupported images as processed; attachment support is a later milestone.
      throw new Error('unsupported_inbound_content');
    }
    const text = content.text;
    if (typeof text !== 'string' || Buffer.byteLength(text, 'utf8') > 4096) throw new Error('inbound_text_too_large');
    if (text.trim().toLowerCase() === 'ping') {
      await this.transport.hello(message, match.route);
    } else {
      let receipt = this.state.data.receipts[hash];
      let caseDetail: CaseDetail | undefined;
      if (!receipt) {
        let prompt: Prompt | undefined = this.state.data.prompts[match.user];
        if (prompt) {
          try { caseDetail = await this.brain.request<CaseDetail>(`/cases/${encodeURIComponent(prompt.caseId)}`); }
          catch (error) {
            if (!(error instanceof BrainError) || error.status !== 404) throw error;
            // Fixture sends and demo resets can invalidate a prior conversation binding.
            delete this.state.data.prompts[match.user];
            prompt = undefined;
          }
          if (caseDetail?.status === 'closed') { caseDetail = undefined; prompt = undefined; }
        }
        if (!caseDetail) caseDetail = await this.brain.openCase(match.user);
        if (caseDetail && caseDetail.user_id !== match.user) throw new Error('case_owner_mismatch');
        // Forwarded scam content is data for the brain; never classify it into consent.
        const forwarded = !caseDetail || /^\s*(?:https?:\/\/|www\.)/i.test(text);
        receipt = { caseId: forwarded ? '' : caseDetail!.case_id };
        // Bind a replay to the original case before any side effects. The brain
        // interprets replies and approves recovery actions (D-039).
        await this.state.save({ ...this.state.data, receipts: { ...this.state.data.receipts, [hash]: receipt } });
      }
      const eventId = `evt_photon_${hash}`;
      await this.brain.event({ event_id: eventId, user_id: match.user,
        type: receipt.caseId ? 'customer.reply' : 'message.forwarded',
        ts: typeof message.createdAt === 'string' ? message.createdAt : new Date().toISOString(),
        source: 'messaging', data: { channel: message.platform, text, ...(receipt.caseId ? { case_id: receipt.caseId } : {}) } });
    }
    const receipts = { ...this.state.data.receipts };
    delete receipts[hash];
    await this.state.save({ ...this.state.data, receipts, processed: [...this.state.data.processed, hash] });
  }
}
