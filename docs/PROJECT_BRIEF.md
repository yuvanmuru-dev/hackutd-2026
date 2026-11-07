# Project brief

> **Superseded: we chose Tell (NVIDIA + T-Mobile + Photon). See docs/PACK_SPEC.md.** The text below is the old example.
>
> **Status: example only.** This is idea A (Groundtruth) from docs/GAMEPLAN.md. At kickoff, rewrite it for the idea we choose.
> Then Lane 1 turns it into docs/PACK_SPEC.md. Don't build against this until it's confirmed.

Everything marked PROPOSAL is a starting point, not a decision. Change it with your team.

App name: Groundtruth (working name, PROPOSAL)

Problem and desired outcome:
Real-estate listings and broker flyers make claims ("not in a flood zone", "walkable",
"priced below the neighborhood") that buyers, renters and tenants mostly have to take on trust.
Checking them means digging through FEMA maps, Census data and maps by hand.
Outcome: paste a listing, get a trust report in under a minute where every claim is marked
supported / contradicted / unverifiable, with a link to the public source.

Target users: home buyers and renters first; commercial tenants and brokers as the CBRE angle. [TEAM: pick one for the demo]

MVP features (PROPOSAL):
1. Paste address + listing text (or pick a demo listing)
2. Agent runs live and the UI shows each step (plan, tool call, result) as it happens
3. Trust report: claim cards with verdict, evidence and source link, plus a trust score
4. Save reports and share a link

Main user journey: user opens app -> pastes listing -> watches agent check claims -> reads report -> shares link.

Excluded for now: scraping listing sites, user accounts beyond simple auth, mobile app, paid data sources.

Platform: web

Approved stack (PROPOSAL): Next.js + Tailwind frontend, Python FastAPI agent service using Nemotron via build.nvidia.com,
Supabase (Postgres + auth + storage). Deploy web on Vercel, agent on Render or Railway.

Design references: one DESIGN.md from awesome-design-md as a starting mood [TEAM: pick], plus the Figma file [TEAM: link].

Data and integrations: US Census geocoder, FEMA NFHL flood zones, Census ACS tract stats, OpenStreetMap Overpass. All free, no keys.

Roles and data ownership: anyone can run a check; saved reports belong to the user who made them; shared links are read-only.

Constraints: 24-hour build, team of [TEAM: number], free tiers only, demo must work on venue Wi-Fi (record a backup video).

---

## Prompt to paste into Claude Code

Read docs/PROJECT_BRIEF.md and the templates in docs/. Help me turn the brief into the eight project docs,
following docs/_CREATE_PROMPT_original.md. Ask me the blocking questions first, in one list.
Keep PROPOSAL items labeled until I approve them. Keep each doc under one page; this is a 24-hour hackathon.
Do not write application code yet.
