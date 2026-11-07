# Titan web (Lanes 3a + 3b)

Next.js App Router + TypeScript + Tailwind v4. Talks only to the brain's HTTP API (`NEXT_PUBLIC_BRAIN_URL`, default `http://localhost:8000`).

- `bash scripts/dev.sh` from the repo root (Git Bash on Windows) starts the brain in MOCK mode and this app on :3000.
- `npm run build` is the only build gate (CI has no web job).
- `lib/api/client.ts` is the typed client; `lib/api/contract-types.ts` is a copy of `contracts/generated/types.ts`. Re-copy it after a contract change; don't run `scripts/gen_types.sh` on a web branch.
- Screens: `/portal` (Maya's account + pause screen), `/case/[id]`, `/console`, `/guardian` (projector, Lane 3a).
