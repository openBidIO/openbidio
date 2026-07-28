# OpenBidIO v0.3 - the bid document format (DRAFT for the group)

Status: **draft 0.3, for discussion.** Supersedes draft 0.2 (2026-07-11).
This revision promotes three things real bids kept needing into core:
per-item **discounts**, document-level **overhead lines**, and per-item
**labour_share** for incentive fidelity. All were previously only
expressible by baking numbers into prices or hiding them in extensions -
both of which lose information a second tool needs. Section 8 lists
exactly what changed and why; section 9 lists the open questions.
CHANGELOG.md carries the full version history.

**Convention: every rate, share, and discount in OpenBidIO is a 0..1
decimal** (0.10 = 10%). No field anywhere in the format uses 0..100.

## 1. What this is (and is not)

A OpenBidIO document is a single JSON file that fully describes one bid:
shots, efforts, rates, sites, incentives, totals, and award state.

- **A format, not a template.** The web tool, a spreadsheet, or any
  company's internal system are all just views over this file. Nobody's
  UI or database is the standard - the file is.
- **Optional-forward.** The core stays small. Everything richer
  (multi-site, episodic, scenarios) has an OPTIONAL, fully specified
  place, and every file declares which conformance profile it uses
  (section 5) so readers know exactly what they are holding.
- **Extensions, not forks.** Anything company-specific travels in
  namespaced `extensions` blocks that other tools may ignore.
  Compatibility on the core, freedom at the edges. Section 6 defines the
  federation path by which a widely-used extension is promoted into an
  optional standard schema.
- **Data custody by design.** The file contains what a bid needs and
  nothing else. Internal margins, burn rates, resourcing plans, and
  vendor economics are deliberately NOT core fields. The test for core
  inclusion is simple: *does a second tool need this field to recompute
  the same totals?* If not, it is an extension.

### Versioning rule (0.x)

While OpenBidIO is pre-1.0, **readers MUST match major.minor exactly**
(a 0.2 reader rejects a 0.3 file, cleanly, with a version message).
Minor versions MAY break during 0.x - that is what 0.x is for. The 1.0
release will define the long-term compatibility and deprecation policy
as a group decision.

## 2. Document anatomy

```json
{
  "bidio": "0.3",
  "id": "b7d9c2e4-1f3a-4c8b-9e2d-5a6f7c8d9e0f",
  "bid_id": "0f4e2d9a-8c1b-4a7e-b3d5-6c9f8e7a2b1c",
  "conformance": "M1",
  "generator": { "name": "tally", "version": "..." },
  "created_at": "2026-07-11T18:00:00Z",
  "updated_at": "2026-07-11T18:00:00Z",

  "project":   { "title": "...", "code": "...", "client": "...", "kind": "feature" },
  "parties":   { "vendor": { "name": "..." } },

  "currency":  "CAD",
  "fx_rates":  [],

  "sites":     [ ... see 2.2 ... ],
  "episodes":  [ ... see 2.3 ... ],

  "departments": [ { "key": "comp", "label": "Compositing" } ],
  "shot_types":  [ { "key": "environment", "label": "Environment" } ],

  "rate_card": { "comp": 800, "fx": 950 },
  "overheads":  [ ... see 2.9 ... ],

  "shots":      [ ... see 2.4 ... ],
  "line_items": [ ... see 2.5 ... ],
  "incentives": [ ... see 2.6 ... ],
  "references": [ ... see 2.8 ... ],
  "totals":     { ... see 2.7 ... },

  "revision":  { "number": 1, "variant": "hero", "locked": false, "supersedes": null },
  "award":     { "status": "draft" },

  "extensions": {}
}
```

Required in every document: `bidio`, `id`, `conformance`, `project`,
`currency`, `shots`, `totals`. Everything else is optional (with one
conditional: `revision.variant` requires `bid_id`).

| Field | Meaning |
|---|---|
| `bidio` | Format version this file conforms to. 0.x rule: readers match major.minor exactly (section 1). |
| `id` | UUID identifying THIS document. Every revision and every scenario is a distinct document with a distinct `id`. |
| `bid_id` | UUID identifying THE BID - stable across all revisions and all scenarios of one bid. RECOMMENDED on every document; REQUIRED when `revision.variant` is used. See 2.1. |
| `conformance` | Which profile this file uses: `M1`, `M1-Multisite`, `M1-Series`, `M1-Full`. Declared profile MUST cover the features actually used (section 5). |
| `generator` | Which tool wrote the file (provenance, optional). |
| `project` | `title` required; `code`, `client` optional; `kind` optional advisory metadata (recommended vocabulary: `feature`, `series`, `commercial`, `short`, `other`). Nothing normative reads `kind`. |
| `parties` | Who is bidding (`vendor.name` recommended) and optionally for whom. No contact info is core. |
| `currency` | ISO 4217 code. All monetary values in the document, including per-site rate cards, are in this one currency. |
| `fx_rates` | RESERVED for M2. Frozen conversion rates. Multi-site does NOT require multi-currency: a vendor freezes converted rates into the site rate cards. |
| `sites` | Execution sites (pricing contexts). See 2.2. |
| `episodes` | Declared episodes for series bids. See 2.3. |
| `departments` | Optional declarations of department keys used in `efforts` and rate cards. Open vocabulary; recommended canonical keys: `comp, roto, paint, matchmove, anim, fx, lighting, lookdev, model, texture, groom, cloth, crowd, dmp, edit`. |
| `shot_types` | Optional declaration of the shot-type taxonomy used by `shots[].type`. |
| `rate_card` | Document-level day rates per department, in `currency`. The DEFAULT card - see rate resolution in 2.2. |
| `overheads` | Document-level percentage lines (production overhead, contingency) computed on the post-discount item base. See 2.9. |
| `references` | Links to external documents by URI + hash. See 2.8. Nothing is ever embedded. |
| `revision` | `number` (1..n), `variant` (scenario name, see 2.1), `locked` (a sent bid is locked = byte-frozen by convention), `supersedes` (document `id` of the prior revision). |
| `award` | Lifecycle: `draft`, `submitted`, `awarded`, `declined`, `withdrawn` (+ optional timestamps, `client_reference`). Multi-vendor award ALLOCATION remains M2 - reserved, not specified here. |
| `extensions` | Namespaced company blocks, e.g. `"com.narro": {...}`, `"com.entropy": {...}`. Readers MUST ignore namespaces they don't know. Allowed at document, shot, line-item, and incentive level. |

### 2.1 Identity: one bid, many documents

A **bid** is the commercial object. A **document** is one concrete
proposal for it. The relationship:

- All documents of one bid share the same `bid_id`.
- **Revisions** walk forward in time: `revision.number` increments,
  `revision.supersedes` points at the prior document's `id`.
- **Scenarios** sit side by side at the same revision: same `bid_id`,
  same `revision.number`, different `revision.variant`
  (e.g. `"hero"` / `"lite"`, `"A"` / `"B"`).

So "give the client three options" = three documents sharing
`bid_id` + `revision.number`, each with its own `variant`, each
independently conformant, each carrying its own totals. Award one,
the others die on the vine. No container format, no delta encoding -
every document stands alone. This is deliberate: a scenario you cannot
open by itself is a scenario a dumb tool cannot read.

`variant` is free-vocabulary. A document with no `variant` is the only
scenario of its revision.

### 2.2 Sites (pricing contexts)

Where work is executed drives two economic facts: the rates the work is
priced at and the incentives it is eligible for. v0.2 makes the site a
first-class declaration:

```json
"sites": [
  { "key": "mtl", "label": "Montreal", "jurisdiction": "CA-QC",
    "rate_card": { "comp": 800, "fx": 950 } },
  { "key": "lon", "label": "London", "jurisdiction": "GB-ENG",
    "rate_card": { "comp": 1000, "anim": 1100 } }
]
```

- `key` is the handle shots and incentives reference. `jurisdiction`
  is required - a site exists precisely because location matters.
- `rate_card` per site is optional. **Rate resolution rule:** a shot
  with `execution_site` prices from that site's `rate_card` if the site
  declares one, else from the document-level `rate_card`. No
  per-department merging between cards - the card that resolves must
  contain every department the shot's `efforts` reference.
- Shots and line items carry an optional `execution_site` (a declared
  site key). An item with no `execution_site` in a multi-site file is
  **site-neutral**: it prices from the document rate card and is
  eligible for NO site-scoped incentive.
- A file with no `sites` block is a single-site file and behaves
  exactly like v0.1.

### 2.3 Episodes

Series bids declare their episodes and tag items to them:

```json
"episodes": [
  { "code": "ep101", "title": "Pilot" },
  { "code": "ep102" }
]
```

- Shots and line items carry an optional `episode` (a declared code).
- An episode MAY declare informational `frames.count`; nothing normative
  reads it.
- An item with no `episode` tag in a series file is **series-level
  overhead** (a supervisor across the season): it appears in document
  totals but in no episode's rollup.
- Whether a series is bid as ONE document with episode tags or as N
  documents (one per episode, related by `references` or by the
  client's tool) is a workflow choice. The format supports both;
  it dictates neither.
- A feature bid simply has no `episodes` block. `project.kind` is
  advisory; the presence of `episodes` is what changes computation.

### 2.4 Shots

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
  "execution_site": "mtl",
  "episode": "ep101",
  "frames": { "count": 240 },
  "efforts": { "model": 10, "texture": 8, "anim": 15, "lighting": 12, "comp": 10 },
  "unit_price": null,
  "discount": 0.10,
  "labour_share": 0.8,
  "notes": "",
  "extensions": {}
}
```

- `id` unique within the document; `code` is the human/pipeline shot code.
- `frames`: optional `{count, in, out}` - frame count and cut range.
  Informational; nothing normative reads it.
- `type` + `difficulty`: type-based bidding is first-class. Recommended
  difficulty vocabulary: `low | medium | high` (open string).
- `quantity`: "8 shots just like this one" - the whole shot line
  multiplies by it.
- `efforts`: person-DAYS per department key. Decimals allowed
  (recommend quarter-day increments).
- `unit_price`: optional override - if present, the shot prices as
  `quantity x unit_price` and `efforts` become informational.
- `discount` (0..1, NEW in 0.3): applied to the item's base cost -
  `cost = base x (1 - discount)`. See 2.9.
- `labour_share` (0..1, NEW in 0.3): the labour fraction of THIS item's
  cost, overriding the incentive's document default for this item. A
  stock-footage purchase carries `labour_share: 0`, a pure-artist shot
  `1`. See 2.6.
- `execution_site` / `episode`: optional membership tags (2.2, 2.3).

### 2.5 Line items (non-shot costs)

```json
{ "id": "li-1", "label": "VFX supervision", "kind": "supervision",
  "quantity": 10, "unit": "day", "unit_cost": 1200,
  "execution_site": "mtl", "episode": null, "extensions": {} }
```

`kind` recommended vocabulary: `supervision | onset | editorial |
management | data | other`. Line items take the same optional
`execution_site` and `episode` tags as shots, with the same semantics -
and the same optional `discount` and `labour_share` fields (2.4, 2.9).

### 2.6 Incentives (v0.2 model)

```json
{ "jurisdiction": "CA-QC", "program": "QPSTC",
  "sites": ["mtl"],
  "labour_share": 0.65, "labour_rate": 0.25, "nonlabour_rate": 0.20 }
```

- `sites`: which declared site keys this incentive applies to.
  **In a file that declares `sites`, every incentive MUST carry a
  non-empty `sites` list** - there is no "applies to everything"
  default in a multi-site file, because a Quebec credit silently
  applying to London work is exactly the failure a format must make
  impossible. In a single-site file (no `sites` block), `sites` is
  omitted and the incentive applies to the whole document (v0.1
  behavior).
- The rate model is deliberately simple and computable (section 3).
  Real programs are more intricate (caps, eligible-cost definitions,
  top-offs) - that intelligence lives in the shared tax-incentive
  service, which fills these fields and/or attaches full detail under
  `extensions`.
- `labour_share` here is the DOCUMENT DEFAULT: the labour fraction
  assumed for items that do not declare their own. An item's own
  `labour_share` (2.4, NEW in 0.3) overrides it for that item, so a
  bid mixing artist work with purchases computes per-item credits that
  actually track where the labour is, instead of smearing one blended
  share across everything.

### 2.7 Totals

```json
{
  "shots_subtotal": 32250, "line_items_subtotal": 9200,
  "gross": 41450, "incentive_credit": 8623.50, "net": 32826.50,
  "by_site": {
    "mtl": { "shots_subtotal": 14850, "line_items_subtotal": 6000,
             "gross": 20850, "incentive_credit": 4795.50, "net": 16054.50 },
    "lon": { "shots_subtotal": 17400, "line_items_subtotal": 0,
             "gross": 17400, "incentive_credit": 3828, "net": 13572 }
  }
}
```

Writers MUST populate `totals`. Readers MUST be able to recompute them
from the document and match (section 3). That redundancy is deliberate -
it is the conformance handshake, and it lets dumb consumers trust the
file without implementing the math.

- `by_site`: RECOMMENDED in `M1-Multisite`/`M1-Full` files. Keys are
  declared site keys. Site-neutral items belong to no site block, so
  block sums plus neutral items reconcile to the document totals.
- `by_episode`: RECOMMENDED in `M1-Series`/`M1-Full` files. Keys are
  declared episode codes. Untagged (overhead) items belong to no
  episode block.

- `discount_total` (optional, NEW in 0.3): sum of per-item discount
  amounts (base minus discounted cost). Declare it when any item
  carries a `discount` - clients want to see what they saved.
- `overhead_total` (optional, NEW in 0.3): sum of the `overheads`
  amounts. `gross` INCLUDES it: subtotals + overheads = gross.
  Overheads never appear inside `by_site` / `by_episode` blocks (2.9).

Note what is absent: margin, internal cost, burn, resourcing. Those are
vendor-private by design.

### 2.8 References (external documents, never attachments)

```json
"references": [
  { "name": "Client breakdown v3", "kind": "client_breakdown",
    "uri": "https://.../breakdown_v3.xlsx",
    "sha256": "9f2c...64 hex chars...a1" }
]
```

The client breakdown that seeded the bid, the storyboard PDF, the
published rate card - linked by URI, pinned by optional SHA-256, never
embedded. OpenBidIO files stay small, human-readable, and diffable.
`kind` recommended vocabulary: `client_breakdown | storyboard | script |
rate_card | contract | other`. (This resolves v0.1 open question #6:
`client_bid_ref` generalized.)

### 2.9 Discounts and overheads (NEW in 0.3)

Both existed in real bids long before this format did; v0.2 could only
bake them into prices, which destroys exactly the information a second
tool needs to renegotiate or rescale a bid. v0.3 makes both first-class
and computable.

**Discounts** are per-item: an optional `discount` (0..1) on any shot
or line item. The item's cost is `base x (1 - discount)` where `base`
is the undiscounted computation (efforts x rates, or quantity x
unit_price / unit_cost). There is no document-level discount field: "8%
across the bid" is written by stamping each item, which keeps every
rollup a plain sum over items and makes mixed discounting (hero shots
full price, volume shots discounted) representable for free. Subtotals
and `gross` are post-discount; the optional `totals.discount_total`
carries the total amount conceded.

**Overheads** are document-level percentage lines:

```json
"overheads": [
  { "key": "production", "label": "Production overhead", "rate": 0.10 },
  { "key": "buffer", "label": "Contingency buffer", "rate": 0.05 }
]
```

- Each line's amount = `rate x (shots_subtotal + line_items_subtotal)`
  - the post-discount item base. Change a shot's efforts and the
  overhead rescales; that recompute-on-change is why overheads pass
  the core-inclusion test ("does a second tool need this field to
  recompute the same totals?") and a fixed line item does not.
- `gross` = item base + overhead amounts.
- Overheads are **site-neutral and episode-untagged by definition**:
  in a multi-site file no site-scoped incentive applies to them (the
  same rule as any site-neutral item), in a single-site file the
  document-wide incentive does (at its default `labour_share`), and
  they appear in document totals only - never inside a `by_site` or
  `by_episode` block.
- `key` is a unique handle (verifier-enforced); the recommended
  vocabulary is `production | buffer | other`.

## 3. Normative computation (what "conformant" means)

The unit of computation is the **item** (a shot or a line item). All
rollups - document totals, per-site, per-episode - are sums over items.
This item-level formulation is what makes every partition deterministic.

1. **Rate resolution** (shots priced via efforts): the shot's card is
   its site's `rate_card` if `execution_site` is set and that site
   declares one; else the document `rate_card`. Every department in the
   shot's `efforts` MUST exist in the resolved card.
2. **Item base cost.**
   Shot: `quantity x unit_price` if `unit_price` is set, else
   `quantity x SUM over departments( efforts[dept] x resolved_rate[dept] )`.
   Line item: `quantity x unit_cost`.
3. **Item cost** = base cost x `(1 - discount)`, where `discount`
   defaults to 0. The item's discount amount is base minus cost.
4. **Overhead lines** (document-level): each overhead's amount =
   `rate x (sum of ALL item costs)` - the post-discount item base.
   Overhead amounts are site-neutral, episode-untagged entries in the
   computation pool.
5. **Entry incentive rate.** An incentive **applies** to an entry
   (item or overhead amount) when: the file has no `sites` block and
   the incentive has no `sites` list (single-site: applies to every
   entry); or the entry's `execution_site` is in the incentive's
   `sites` list. The entry's incentive rate is the sum over applying
   incentives of `ls x labour_rate + (1 - ls) x nonlabour_rate`, where
   `ls` is the ITEM's own `labour_share` if declared, else the
   incentive's `labour_share`. Overhead amounts always use the
   incentive's default share. Site-neutral entries in a multi-site
   file (including all overheads) have rate 0.
6. **Entry credit** = entry cost x entry incentive rate.
7. **Document totals**: `shots_subtotal` = sum of shot costs;
   `line_items_subtotal` = sum of line-item costs; `overhead_total` =
   sum of overhead amounts; `discount_total` = sum of item discount
   amounts; `gross` = shots_subtotal + line_items_subtotal +
   overhead_total; `incentive_credit` = sum of ALL entry credits;
   `net` = gross - incentive_credit.
8. **Partition totals**: a `by_site` block sums exactly the items
   tagged to that site; a `by_episode` block sums exactly the items
   tagged to that episode. Untagged items and ALL overhead amounts
   appear only in document totals. Invariant (checked at full
   precision): partition blocks plus untagged entries reconcile
   exactly to document totals.
9. **Rounding**: compute at full precision; round each REPORTED field
   to 2 decimals, half-up; verifiers compare with tolerance 0.005 per
   field. Because each reported field rounds independently, the sum of
   rounded partition blocks MAY differ from the rounded document total
   by cents - that is arithmetic, not nonconformance. The invariant in
   rule 8 binds at full precision only.

A file is **conformant** when it (a) validates against
`openbidio.schema.json`, (b) declares a profile that covers the features it
uses (section 5), (c) passes referential integrity (every
`execution_site`, `episode`, incentive `sites` entry, `by_site` key and
`by_episode` key refers to a declared site/episode; `variant` implies
`bid_id`; **every handle is unique within the document** - site keys,
episode codes, shot ids, line-item ids, declared department and
shot-type keys, `fx_rates` currencies. A duplicated handle is a
silent-wrong-answer generator: two sites keyed `mtl` would let rate
resolution and incentive scoping silently pick one of them), (d)
recomputes to its own `totals`, and (e) is readable with all unknown
`extensions` ignored. `tools/verify.py` checks all five.

## 4. Scenarios and revisions in practice

```
bid_id: 0668...            (one bid)
  rev 1                    id: aaaa...   (first pass, no variant)
  rev 2  variant "hero"    id: bbbb...   supersedes aaaa
  rev 2  variant "lite"    id: cccc...   supersedes aaaa
  rev 3  variant "hero"    id: dddd...   supersedes bbbb   <- awarded
```

Tools reconstruct the whole tree from three fields (`bid_id`,
`revision.number`, `revision.variant`) plus the `supersedes` chain.
A locked document is byte-frozen by convention; corrections happen in
the next revision.

## 5. Conformance profiles

Every document declares `conformance`. The profile gates the
COMPUTATIONAL features used - identity fields (`bid_id`, `variant`),
`references`, and `extensions` are allowed in every profile.

| Profile | sites / execution_site | episodes / episode | incentives |
|---|---|---|---|
| `M1` | no | no | at most 1, document-wide |
| `M1-Multisite` | yes | no | any number, each site-scoped |
| `M1-Series` | no | yes | at most 1, document-wide |
| `M1-Full` | yes | yes | any number, each site-scoped |

A file MUST NOT use a feature its declared profile excludes (verified).
A file MAY declare a larger profile than it uses. Readers reject files
whose profile they do not implement - with a clear message, never a
silent misread. An `M1`-only tool therefore remains a first-class
citizen of the ecosystem forever: it just says so.

## 6. Extensions and the federation path

`extensions` is not a dumping ground; it is the standard's R&D pipeline
(the same dynamic that turned per-vendor USD attributes into shared
schemas):

1. A company ships real data in its own namespace
   (`extensions."com.narro".resourcing = {...}`).
2. When two or more companies converge on similar shapes, the group
   drafts an OPTIONAL standard schema from the working examples and
   publishes it in the next minor version.
3. Vendors migrate at their own pace; the namespaced form remains valid.

**Worked example - resourcing.** Crew mix (senior/mid/junior bands,
staff vs freelance, allocation over time) is how a vendor ARRIVES at a
number, not the number: a comp department bid at a 60/40 senior/junior
mix of 950/650 rates round-trips identically as a blended 830. Totals
are unchanged, so resourcing fails the core-inclusion test in section 1
- but it passes the extension test perfectly: a vendor whose engine
plans resourcing SHOULD persist it in its namespace so its own
round-trip is lossless, and if the shapes converge across vendors,
resourcing graduates to an optional schema by the path above.

## 7. Governance

OpenBidIO is developed by an open working group (Narro, Entropy, Nano
Visuals, and independent contributors). The intended path for v1.0:
publication under the **Visual Effects Society** (Technology Committee),
with a subsequent **SMPTE** standardization track for formal industry
ratification, and **PGA** endorsement sought for the producer-side
workflow. The format specification is and will remain openly published;
engines, services, and models built on it remain their authors'
property. (Precedent: ACES - academy-published first, SMPTE-ratified
second. Precedent for the open-format/closed-tooling split: PDF, USD.)

## 8. Changes since v0.2 (and why)

| Change | Why |
|---|---|
| Per-item `discount` (0..1) + `totals.discount_total` | Real bids ship with discounts - per line and across the bid. v0.2 could only bake the net into prices, destroying the gross/discount story a client statement and a renegotiation both need. Item-level keeps every rollup a plain sum and makes mixed discounting free. |
| `overheads` percentage lines + `totals.overhead_total` | Production overhead and contingency are percentages OF the work, not fixed lines: change a shot's efforts and the overhead must rescale. That recompute-on-change is precisely the core-inclusion test. Site-neutral and partition-excluded by definition. |
| Per-item `labour_share` override | The v0.2 incentive model smeared one blended labour share across every item, so per-item credits were fiction the moment a bid mixed artist work with purchases. The item override keeps the simple linear model AND makes per-item credits track reality. Program intricacies (caps, top-offs) stay in the tax service / extensions. |
| Rates convention stated normatively | Every rate, share, and discount in the format is a 0..1 decimal. Mixed 0..100 / 0..1 conventions are a classic silent-wrong-answer generator. |
| `CHANGELOG.md` | The version history moved out of this section into a proper changelog; this section now only diffs against the immediately-prior draft. |
| Verifier: handle uniqueness enforced (0.2.x fix, carried) | A duplicated site key silently double-priced a test document (last declaration won). Uniqueness of every handle - site keys, episode codes, shot/line-item ids, dept and shot-type keys, overhead keys - is now normative (section 3) and verifier-enforced. |

The full v0.1 -> v0.2 changelog lives in CHANGELOG.md.

## 9. Open questions for the group

1. Department vocabulary - adopt the 15 recommended keys, or trim?
2. Difficulty scale - three levels enough? Per-type or global?
3. Jurisdiction codes in `sites` - free string today; adopt ISO 3166-2?
4. Incentive model - is the per-item formula acceptable for M1-class
   profiles, with the tax service handling real program complexity?
5. Scenario vocabulary - free `variant` strings, or a recommended set?
6. Series workflow - should the group RECOMMEND one-document-per-episode
   or one-document-with-tags as the default convention (both stay legal)?
7. Line-item `kind` list - what is missing for how you bid?
8. Profile names - happy with `M1 / M1-Multisite / M1-Series / M1-Full`?

---
Files in this folder: `SPEC.md` (this document), `openbidio.schema.json`
(machine validation), `CHANGELOG.md` (version history), `LICENSE`
(CC BY 4.0 spec text, MIT machine artifacts), `fixtures/` (six
conformance fixtures covering all four profiles plus the v0.3
discount/overhead/labour_share worked example, totals hand-verified),
`tools/verify.py` (reference verifier: schema + profile + referential
integrity + totals + extensions).
