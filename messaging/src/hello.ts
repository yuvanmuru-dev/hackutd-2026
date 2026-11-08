import { configuration } from './config.js';
import { State } from './state.js';
import { Transport } from './photon.js';
import { errorFields } from './logging.js';

// Run independently of the brain: answer only a recent allowlisted ping.
async function hello() {
  const config = configuration();
  const transport = new Transport(config, new State(config.stateDir));
  const page = await transport.api.projects.listMessages({ path: { id: config.project },
    query: { platform: 'imessage', direction: 'received', order: 'desc', pageSize: 100,
      createdSince: new Date(Date.now() - 15 * 60_000).toISOString() } });
  for (const message of page?.items ?? []) {
    const match = transport.match(message);
    if (!match || message.platform !== 'imessage' || message.status !== 'received') continue;
    const content = message.content;
    if (content.type === 'text' && content.format === 'plain' && content.text.trim().toLowerCase() === 'ping') {
      await transport.hello(message, match.route);
      console.log(JSON.stringify({ event: 'hello_dispatch_accepted' })); return;
    }
  }
  console.log(JSON.stringify({ event: 'no_recent_allowlisted_ping' }));
}
hello().catch(error => { console.error(JSON.stringify({ event: 'hello_failed', ...errorFields(error) })); process.exitCode = 1; });
