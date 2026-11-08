import type { CaseDetail, Event } from './contract-types.js';
import { valid } from './contracts.js';
export class BrainError extends Error {
  constructor(readonly status: number) { super('brain_request_failed'); }
}
export class Brain {
  constructor(private base: string) {}
  async request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${this.base.replace(/\/$/, '')}${path}`, {
      method: body === undefined ? 'GET' : 'POST', signal: AbortSignal.timeout(10_000),
      headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok) throw new BrainError(response.status);
    return response.json() as Promise<T>;
  }
  async openCase(user: string): Promise<CaseDetail | undefined> {
    const cases = await this.request<{ case_id: string; status: string; updated_at: string }[]>(`/cases?user_id=${encodeURIComponent(user)}`);
    const open = cases.filter(c => c.status !== 'closed').sort((a,b) => b.updated_at.localeCompare(a.updated_at));
    if (!open.length) return;
    return this.request(`/cases/${encodeURIComponent(open[0].case_id)}`);
  }
  async event(event: Event) {
    if (!valid('Event', event)) throw new Error('invalid_brain_event');
    return this.request<{ duplicate: boolean }>('/events', event);
  }
}
