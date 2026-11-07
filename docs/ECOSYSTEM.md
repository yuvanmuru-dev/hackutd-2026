# Ecosystem: one brain, many doors

```
 browser ──► web/ (Next.js) ───────────── /runs/stream (live steps), /actions, /watches
 caller  ──► Twilio ─► voice/ (Pipecat) ── /tools/*, /runs, /actions        ◄── /internal/call (outbound)
 inbox   ──► AgentMail ─► email/ ───────── /runs, PATCH /actions             ◄── /internal/send (outbound)
 timer   ──► watcher/ ──────────────────── /runs (channel "watch") ─► notify via email/voice
                                   │
                         agent/ (the brain, FastAPI)
                                   │
          Nemotron (plan + tool calls) ── active pack: agent/packs/<pack>/ tools + prompt
                                   │
                         Supabase (runs, steps, actions, watches, messages)
```

The doors give the same answer from the same sources because only the brain reasons and calls data APIs.
The brain calls doors only to **act** (send an email, place a call).
API shapes: docs/CONTRACTS.md. Owners: docs/LANES.md. Models: the NVIDIA stack table in docs/GAMEPLAN.md.

Earlier draft (real-estate "Groundtruth" version) is idea A in the GAMEPLAN idea bank.
