export interface Config {
  project: string; key: string; agent: string; brain: string; port: number;
  allowlist: Set<string>; users: Map<string, string>; stateDir: string;
  nvidiaKey?: string; llmBase: string; llmModel: string;
}

export function configuration(env: NodeJS.ProcessEnv = process.env): Config {
  const required = (name: string) => {
    if (!env[name]) throw new Error(`Missing ${name}`);
    return env[name]!;
  };
  const project = required('PHOTON_PROJECT_ID');
  if (!/^pho_prj_[0-7][0-9a-hjkmnp-tv-z]{25}$/.test(project)) throw new Error('Expected a Photon 2.0 project ID');
  const key = required('PHOTON_API_KEY');
  if (!key.startsWith('pho_sk_')) throw new Error('Expected a Photon 2.0 project API key');
  const phone = /^\+[1-9]\d{7,14}$/;
  const allowlist = new Set(required('OUTBOUND_ALLOWLIST').split(',').map(s => s.trim()));
  if ([...allowlist].some(n => !phone.test(n))) throw new Error('Allowlist must use E.164 numbers');
  const users = new Map<string, string>();
  for (const [name, value] of Object.entries(env)) {
    if (!name.startsWith('USER_PHONE_') || !value) continue;
    if (!phone.test(value) || !allowlist.has(value)) throw new Error('User number is not allowlisted');
    if ([...users.values()].includes(value)) throw new Error('A number must map to only one demo user');
    users.set(name.slice('USER_PHONE_'.length), value);
  }
  if (!users.size) throw new Error('Configure USER_PHONE_usr_maya');
  const port = Number(env.PORT ?? 8200);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid PORT');
  const llmBase = env.MESSAGING_LLM_BASE_URL ?? 'https://integrate.api.nvidia.com/v1';
  const llmModel = env.MESSAGING_LLM_MODEL ?? 'nvidia/nemotron-3.5-lightning-30b-a3b';
  // A local Brev-hosted Nano is allowed, but never silently use another provider.
  const llmHost = new URL(llmBase).hostname;
  if (!(llmHost === 'integrate.api.nvidia.com' || llmHost === 'localhost' || /^\d{1,3}(\.\d{1,3}){3}$/.test(llmHost))
      || !(/nemotron.*nano/i.test(llmModel) || llmModel === 'nvidia/nemotron-3.5-lightning-30b-a3b')) throw new Error('Reply understanding requires an approved Nemotron model');
  return { project, key, agent: required('PHOTON_AGENT_HANDLE'),
    brain: env.BRAIN_URL ?? 'http://localhost:8000', port, allowlist, users,
    stateDir: env.MESSAGING_STATE_DIR ?? `.state/${project}`,
    nvidiaKey: env.NVIDIA_API_KEY, llmBase, llmModel };
}
