import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
export interface Route { spaceId: string; senderId: string; }
export interface Prompt { caseId: string; actionId?: string; }
export interface Receipt extends Prompt { intent: string; }
export interface Checkpoint {
  cursor: number; processed: string[];
  prompts: Record<string, Prompt>; receipts: Record<string, Receipt>;
}

export class State {
  data: Checkpoint = { cursor: 0, processed: [], prompts: {}, receipts: {} };
  constructor(private dir: string) {}
  async load() {
    try {
      const saved = JSON.parse(await readFile(join(this.dir, 'checkpoint.json'), 'utf8'));
      if (!Number.isSafeInteger(saved.cursor) || saved.cursor < 0 || !Array.isArray(saved.processed)
          || !saved.prompts || !saved.receipts) throw new Error('Invalid checkpoint');
      this.data = saved;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
  async save(next: Checkpoint) {
    await mkdir(this.dir, { recursive: true, mode: 0o700 });
    const file = join(this.dir, 'checkpoint.json');
    await writeFile(`${file}.tmp`, JSON.stringify(next), { mode: 0o600 });
    await rename(`${file}.tmp`, file);
    this.data = next;
  }
}
