# bidIO v0.1 - the bid document format (DRAFT for the group)

Status: **draft 0.1, for discussion at the two-week presentation.**
This is the "first assembly pass" owed from the July 6 call - assembled from
Tally's production data model, Nico's type-based bidding, and the award-bid
MVP scope we agreed on. Cut it down, rename fields, challenge everything:
the group locks v0.1 together.

## 1. What this is (and is not)

A bidIO document is a single JSON file that fully describes one bid:
shots, efforts, rates, incentives, totals, and award state.

- **A format, not a template.** The web tool, a spreadsheet, or any
  company's internal system are all just views over this file. Nobody's
  UI or database is the standard - the file is.
- **Optional-forward.** Milestone 1 uses a small core (single currency,
  one incentive jurisdiction, manual efforts). Everything richer
  (multi-currency, awards allocation) already has a reserved, OPTIONAL
  place so v0 readers never break.
- **Extensions, not forks.** Anything company-specific travels in
  namespaced `extensions` blocks that other tools may ignore.
  Compatibility on the core, freedom at the edges.
- **Data custody by design.** The file contains what a bid needs and
  nothing else. Internal margins, burn rates, and vendor economics are
  deliberately NOT core fields - keep them in your own extensions or out
  of the file entirely.

## 2. Document anatomy

```json
{
  "bidio": "0.1",
  "id": "b7d9c2e4-1f3a-4c8b-9e2d-5a6f7c8d9e0f",
  "generator": { "name": "tally", "version": "..." },
  "created_at": "2026-07-07T18:00:00Z",
  "updated_at": "2026-07-07T18:00:00Z",

  "project":   { "title": "...", "code": "...", "client": "..." },
  "parties":   { "vendor": { "name": "..." } },

  "currency":  "CAD",
  "fx_rates":  [],

  "departments": [ { "key": "comp", "label": "Compositing" } ],
  "shot_types":  [ { "key": "environment", "label": "Environment" } ],

  "rate_card": { "comp": 800, "fx": 950 },

  "shots":      [ ... see 2.1 ... ],
  "line_items": [ ... see 2.2 ... ],
  "incentives": [ ... see 2.3 ... ],
  "totals":     { ... see 2.4 ... },

  "revision":  { "number": 1, "locked": false, "supersedes": null },
  "award":     { "status": "draft" },

  "extensions": {}
}
```

Required in every document: `bidio`, `id`, `project`, `currency`,
`shots`, `totals`. Everything else is optional.

| Field | Meaning |
|---|---|
| `bidio` | Format version this file conforms to (semver). Readers accept any file sharing their major version. |
| `id` | UUID identifying this document across round-trips between tools. |
| `generator` | Which tool wrote the file (provenance, optional). |
| `project` | `title` required; `code`, `client` optional. |
| `parties` | Who is bidding (`vendor.name` recommended) and optionally for whom. No contact info is core. |
| `currency` | ISO 4217 code. **M1 profile: all monetary values in this one currency.** |
| `fx_rates` | RESERVED for M2. Frozen conversion rates: `{"currency":"USD","rate":1.36}` means 1 USD = 1.36 document-currency. Frozen at bid time - a bid never drifts because the market moved. |
| `departments` | Optional declarations of the department keys used in `efforts` and `rate_card`. Open vocabulary; recommended canonical keys: `comp, roto, paint, matchmove, anim, fx, lighting, lookdev, model, texture, groom, cloth, crowd, dmp, edit`. |
| `shot_types` | Optional declaration of the shot-type taxonomy used by `shots[].type` (type-based bidding). |
| `rate_card` | Day rate per department key, in `currency`. Required in practice whenever any shot prices via `efforts`. |
| `revision` | `number` (1..n), `locked` (a sent bid is locked = byte-frozen by convention), `supersedes` (id of the prior revision's document). |
| `award` | Lifecycle: `draft`, `submitted`, `awarded`, `declined`, `withdrawn` (+ optional `submitted_at`, `awarded_at`, `client_reference`). Multi-vendor award ALLOCATION is M2 - reserved, not specified here. |
| `extensions` | Namespaced company blocks, e.g. `"com.naro": {...}`, `"com.entropy": {...}`. Readers MUST ignore namespaces they don't know. Allowed at document, shot, and line-item level. |

### 2.1 Shots

```json
{
  "id": "sh-020",
  "code": "020",
  "description": "Hero creature reveal",
  "sequence": "SEQ01",
  "type": "creature",
  "difficulty": "high",
  "tags": ["creature", "rain"],
  "quantity": 1,
  "frames": { "count": 240 },
  "efforts": { "model": 10, "texture": 8, "anim": 15, "lighting": 12, "comp": 10 },
  "unit_price": null,
  "notes": "",
  "extensions": {}
}
```

- `id` unique within the document; `code` is the human/pipeline shot code.
- `type` + `difficulty`: type-based bidding is first-class. Recommended
  difficulty vocabulary: `low | medium | high` (open string - a studio may
  use its own scale; declare it in `extensions` if non-standard).
- `quantity`: "8 shots just like this one" - the whole shot line
  multiplies by it.
- `efforts`: person-DAYS per department key. Decimals allowed
  (recommend quarter-day increments).
- `unit_price`: optional override - if present, the shot prices as
  `quantity x unit_price` and `efforts` become informational. This is how
  flat-priced shots and "my spreadsheet only has totals" imports work.

### 2.2 Line items (non-shot costs)

For everything a real bid has beyond shots - supervision, on-set days,
editorial, management:

```json
{ "id": "li-1", "label": "VFX supervision", "kind": "supervision",
  "quantity": 10, "unit": "day", "unit_cost": 1200, "extensions": {} }
```

`kind` recommended vocabulary: `supervision | onset | editorial |
management | data | other`.

### 2.3 Incentives (v0.1 model)

```json
{ "jurisdiction": "CA-QC", "program": "QPSTC",
  "labour_share": 0.65, "labour_rate": 0.25, "nonlabour_rate": 0.20 }
```

v0.1 deliberately uses ONE simple, computable model (section 3). Real
programs are more intricate (caps, eligible-cost definitions, top-offs) -
that intelligence lives in the shared tax-incentive service, which can
fill these fields and/or attach full detail under `extensions`. **M1
profile: at most one incentive per document.**

### 2.4 Totals

```json
{ "shots_subtotal": 112900, "line_items_subtotal": 15000,
  "gross": 127900, "incentive_credit": 29736.75, "net": 98163.25 }
```

Writers MUST populate `totals`. Readers MUST be able to recompute them
from the document and match (section 3). That redundancy is deliberate -
it is the conformance handshake, and it lets dumb consumers (a script, a
spreadsheet) trust the file without implementing the math.

Note what is absent: margin, internal cost, burn. Those are vendor-private
by design.

## 3. Normative computation (what "conformant" means)

1. **Shot cost** = `quantity x unit_price` if `unit_price` is set,
   else `quantity x SUM over departments( efforts[dept] x rate_card[dept] )`.
   Every department referenced in a priced shot's `efforts` MUST exist in
   `rate_card`.
2. **shots_subtotal** = sum of all shot costs.
3. **Line-item cost** = `quantity x unit_cost`.
   **line_items_subtotal** = sum of them.
4. **gross** = shots_subtotal + line_items_subtotal.
5. **incentive_credit** = for each incentive:
   `gross x labour_share x labour_rate + gross x (1 - labour_share) x nonlabour_rate`,
   summed.
6. **net** = gross - incentive_credit.
7. **Rounding**: compute at full precision; round each `totals` field to
   2 decimals, half-up. Verifiers compare with tolerance 0.005.

A file is **conformant** when it (a) validates against
`bidio.schema.json`, (b) recomputes to its own `totals`, and (c) is
readable with all unknown `extensions` ignored. `tools/verify.py` in this
folder checks all three.

## 4. M1 profile

The milestone-1 tool reads/writes the core: single `currency`, no
`fx_rates`, at most one incentive, manual `efforts`. A file using M2
fields is still VALID v0.1 - an M1 reader simply ignores what it does not
implement (except `totals`, which always bind).

## 5. Open questions for the group

1. Department vocabulary - adopt the 15 recommended keys, or trim?
2. Difficulty scale - three levels enough? Per-type or global?
3. `shot_types` - do we standardize a starter taxonomy or leave it fully
   per-studio (declared in the file)?
4. Incentive model - is the v0.1 formula acceptable for M1, with the
   service handling real program complexity?
5. Line-item `kind` list - what is missing for how you bid?
6. Do we want a `client_bid_ref` block for linking back to the incoming
   client breakdown that was imported?

---
Files in this folder: `SPEC.md` (this document), `bidio.schema.json`
(machine validation), `fixtures/fixture-001.bid.json` (a complete example
whose totals are hand-verified - the first conformance fixture),
`tools/verify.py` (reference verifier: schema + totals + extensions).
