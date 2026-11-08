# D-053 independent sealed synthetic cohort

This design is fixed before generation. A previous coordinator was exposed
before any design or sealed data existed. A fresh independently blinded author
made all choices here without inheriting that material. Authoring is blinded: the author has not
read model code, rules, predictions, evaluation output, failure reports, model
audits, previous chats, or GitHub material and will not call a scorer. No network
is used. This cohort is local and is not published or inserted into a split.

## Fixed counts

| Component | Families | Per family | Records |
| --- | ---: | ---: | ---: |
| Fresh independent scenarios for every current family | 38 | 3 | 114 |
| New attack family: `ended_call_then_port_out` | 1 | 9 | 9 |
| New legitimate hard negative: `verified_care_device_replacement` | 1 | 9 | 9 |
| New benign forwarded family: `customer_forwarded_service_notice` | 1 | 6 | 6 |
| Total | 41 | | 138 |

Expected labels: takeover 24, coached 24, scam_text 24, bot 12,
recovery_scam 12, legit 42. Expected hard negatives: 33. Exactly six
scenarios are benign customer-forwarded texts, all in the new notice family.
Attack forwarded texts are retained for coverage of the existing text families.

## Independent novelty rationale

- `ended_call_then_port_out`: an unsolicited unverified call has ended before a
  customer disables port protection and requests a transfer PIN. The completed
  call followed by a sensitive action is a new temporal sequence; existing
  call-based attack families use an active call. Grounding: carrier call metadata
  and protection/PIN event logs at the trigger. No dialogue or caller claim is
  encoded. The synthetic scenario's assigned story is coaching that continues
  after hangup; the observable records alone do not establish intent.
- `verified_care_device_replacement`: the customer initiates a new outbound,
  attested care call, passes an account PIN check, receives/enters an account
  change OTP, and requests a replacement through care. This differs from store
  upgrades, repeat family calls, travel logins, and routine visits. Grounding:
  Elena's care habit and the permitted care/device/protection records. Other
  personas also receive this plausible care-assisted replacement. A new device
  and first-seen caller hash make these legitimate hard negatives.
- `customer_forwarded_service_notice`: a customer deliberately forwards an
  ordinary billing, roaming, upgrade, or protection notice with no request to
  disclose a secret or follow a link. Existing forwarded families are attacks;
  these six legitimate examples introduce the benign branch of this input type.
  The notices are newly authored synthetic text, not messages read from a line.

## Frozen randomness and allocation

- Design seed: `7284883994134891592`.
- Base seed: `2269334185941103781`.
- Both seeds were sampled independently with Python `secrets.randbits(63)` before
  generation; each scenario receives a distinct SHA-256-derived 63-bit seed.
- Existing-family count, label, hard-negative membership, event-type patterns,
  persona habits, known device identifiers, and coarse line regions were
  inventoried only from the permitted domain records. No existing text was read
  or copied. Existing scenario values are not reused as random templates.
- Family order is lexical. Generic families rotate across all five existing
  personas. Persona-named and strongly persona-specific legacy families retain
  the applicable persona: Maya repeat calls, Dev store replacements, Priya night
  shifts, Marcus travel. New family allocation rotates across all five.
- New session, event, call, sender, and device identifiers derive from the frozen
  seeds with a sealed-only namespace. Known device hashes may match the existing
  synthetic baseline for a legitimate established session.
- The maximum permitted baseline history timestamp is
  `2026-11-06T22:02:00Z`. Scenario windows begin on `2026-11-08T00:00:00Z`
  or later. Every event and trigger follows all baseline histories.

## Event and privacy constraints

Each JSONL record is exactly `DatasetScenario`. All scenarios have chronological
events, one valid trigger reference, fresh scenario/event IDs, globally distinct
call IDs across scenarios, and internally consistent call references. There is
exactly one `line.region` snapshot, immediately before the trigger, only when the
scenario has a requesting session/action. No forwarded-text scenario has a
location event. Snapshot precision is a coarse service region, never a trail.

Only customer-forwarded events contain free text. Call records contain metadata
only and omit caller names. PIN and OTP events record purpose/success only, never
values. No real data, phone numbers, contacts, call dialogue, voiceprints, raw
keystrokes, motion, or unrelated browsing is generated. Scam links use reserved
`.example` hosts; benign notices contain no links. Portal paths are confined to
the carrier account flow. Call histories and location trails are never created.

## Verification fixed before evaluation

Generation and integrity checks use Python standard library. Every record is
validated with `core.contracts.errors('DatasetScenario', record)` using
`PYTHONDONTWRITEBYTECODE=1`. Separate integrity/privacy checks verify the fixed
counts, all 38 legacy families plus exactly three new ones, fresh ID/seed
namespaces, call pairing, chronology, baseline ordering, trigger snapshots,
label and hard-negative consistency, text placement, benign count, and reserved
hosts. Regeneration must be byte-identical and manifest SHA-256 covers the raw
`scenarios.jsonl` bytes. No scorer, model evaluation, broad test suite, network,
split update, external registry, or publication is part of this work. The parent
stores model freeze/provenance separately. No outcomes will be used to revise
this cohort.
