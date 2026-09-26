# OpenBidIO v0.4 - the bid document format (DRAFT for the group)

Status: **draft 0.4, for discussion.** Supersedes draft 0.3 (2026-07-23).
This revision says **who does the work**: a bid larger than one shop has
a prime and its subcontractors, and 0.3 could only name one vendor, so a
prime's file either lied about who does what or hid it in extensions.
0.4 makes vendors, their share of the money (`totals.by_vendor`) and
their own bids (`subbids`, nested whole) first-class. It also closes four
things the 0.3 review measured as missing: money written as binary
floats, a document with no seal, an incentive with no cap, and a verifier
that certified without its schema. Section 8 lists exactly what changed
and why; section 9 lists the open questions. CHANGELOG.md carries the
full version history.

**Convention: every rate, share, and discount in OpenBidIO is a 0..1
decimal** (0.10 = 10%). No field anywhere in the format uses 0..100.

**Convention (NEW in 0.4): every amount of money is a decimal STRING**
(`"800"`, `"8623.5"`, `"0.25"` is a rate and stays a number). A JSON
number is a binary float in most readers, and `0.1 + 0.2` is the bug a
bid format exists to prevent. Rate cards, `unit_price`, `unit_cost`,
incentive `cap` and every field of `totals` are money; quantities, days,
rates, shares, discounts and `fx_rates.rate` are not.

**A document is a `.bidio` file** (media type `application/vnd.bidio+json`),
JSON inside. Section 2.11.

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
  "bidio": "0.4",
  "id": "b7d9c2e4-1f3a-4c8b-9e2d-5a6f7c8d9e0f",
  "bid_id": "0f4e2d9a-8c1b-4a7e-b3d5-6c9f8e7a2b1c",
  "conformance": "M1",
  "generator": { "name": "tally", "version": "..." },
  "created_at": "2026-09-25T18:00:00Z",
  "updated_at": "2026-09-25T18:00:00Z",
  "provenance": { ... see 2.11 ... },
  "digest":    { "algorithm": "sha256", "value": "...64 hex..." },

  "project":   { "title": "...", "code": "...", "client": "...", "kind": "feature" },
  "parties":   { "vendor": { "name": "..." },
                 "vendors": [ ... see 2.10 ... ],
                 "client": { "name": "..." } },

  "currency":  "CAD",
  "fx_rates":  [ { "currency": "GBP", "rate": 1.72 } ],

  "sites":     [ ... see 2.2 ... ],
  "episodes":  [ ... see 2.3 ... ],

  "departments": [ { "key": "comp", "label": "Compositing" } ],
  "shot_types":  [ { "key": "environment", "label": "Environment" } ],

  "rate_card": { "comp": "800", "fx": "950" },
  "overheads":  [ ... see 2.9 ... ],

  "shots":      [ ... see 2.4 ... ],
  "line_items": [ ... see 2.5 ... ],
  "incentives": [ ... see 2.6 ... ],
  "subbids":    [ ... see 2.10 ... ],
  "references": [ ... see 2.8 ... ],
  "totals":     { ... see 2.7 ... },

  "revision":  { "number": 1, "variant": "hero", "locked": false, "supersedes": null },
  "award":     { "status": "draft" },

  "extensions": {}
}
```

Required in every document: `bidio`, `id`, `conformance`, `project`,
`currency`, `shots`, `totals`, `digest`. Everything else is optional
(with one conditional: `revision.variant` requires `bid_id`).

| Field | Meaning |
|---|---|
| `bidio` | Format version this file conforms to. 0.x rule: readers match major.minor exactly (section 1). |
| `id` | UUID identifying THIS document. Every revision and every scenario is a distinct document with a distinct `id`. |
| `bid_id` | UUID identifying THE BID - stable across all revisions and all scenarios of one bid. RECOMMENDED on every document; REQUIRED when `revision.variant` is used. See 2.1. |
| `conformance` | Which profile this file uses: `M1`, `M1-Multisite`, `M1-Series`, `M1-Vendors`, `M1-Full`. Declared profile MUST cover the features actually used (section 5). |
| `generator` | Which tool wrote the file (optional). |
| `provenance` | Where the document came from: `generated_at`, `generated_by`, `source {system, ref, uri}` (optional). See 2.11. |
| `digest` | REQUIRED. `{algorithm: "sha256", value}` over the canonical form of the document without this member. A document edited after it was written fails its own seal. See 2.11. |
| `project` | `title` required; `code`, `client` optional; `kind` optional advisory metadata (recommended vocabulary: `feature`, `series`, `commercial`, `short`, `other`). Nothing normative reads `kind`. |
| `parties` | Who is bidding and for whom. `vendor` is the 0.3 party and IS the prime; `vendors[]` declares every vendor doing work - the prime and its subs - by handle (2.10). No contact info is core. |
| `currency` | ISO 4217 code. Every amount in the document is in this currency, EXCEPT a site that declares its own `currency` (2.2): that site's rate card and the amounts of items tagged to it are in the site's currency and convert through `fx_rates`. Vendor cards are always in the document currency. |
| `fx_rates` | Frozen conversion rates, one per foreign currency: `rate` is document-currency units per ONE unit of that currency (1 GBP = 1.72 CAD). Required for every site currency that differs from the document's. A file with no site currencies needs none (a vendor may still freeze converted rates into a card, as before). |
| `sites` | Execution sites (pricing contexts). See 2.2. |
| `episodes` | Declared episodes for series bids. See 2.3. |
| `departments` | Optional declarations of department keys used in `efforts` and rate cards. Open vocabulary; recommended canonical keys: `comp, roto, paint, matchmove, anim, fx, lighting, lookdev, model, texture, groom, cloth, crowd, dmp, edit`. |
| `shot_types` | Optional declaration of the shot-type taxonomy used by `shots[].type`. |
| `rate_card` | Document-level day rates per department, money strings in `currency`. The LAST card in rate resolution (vendor -> site -> document) - see 2.2. |
| `overheads` | Document-level percentage lines (production overhead, contingency) computed on the post-discount item base. See 2.9. |
| `references` | Links to external documents by URI + hash. See 2.8. Nothing is ever embedded. |
| `revision` | `number` (1..n), `variant` (scenario name, see 2.1), `locked` (a sent bid is locked = byte-frozen by convention), `supersedes` (document `id` of the prior revision). |
| `subbids` | A sub vendor's own OpenBidIO document, nested whole with its identity and digest. See 2.10. |
| `award` | Lifecycle: `draft`, `submitted`, `awarded`, `declined`, `withdrawn` (+ optional timestamps, `client_reference`). Who does which item is the `vendor` tag (2.10); a per-vendor award STATUS remains M2 - reserved, not specified here. |
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
    "rate_card": { "comp": "800", "fx": "950" } },
  { "key": "lon", "label": "London", "jurisdiction": "GB-ENG", "currency": "GBP",
    "rate_card": { "comp": "1000", "anim": "1100" } }
]
```

- `key` is the handle shots and incentives reference. `jurisdiction`
  is required - a site exists precisely because location matters - and
  since 0.4 it is **ISO 3166**: the alpha-2 country, optionally with its
  3166-2 subdivision (`CA-QC`, `GB-ENG`, `US-NY`, `NZ`). The schema
  refuses "Quebec". (Resolves 0.3 open question 3.)
- `currency` (NEW in 0.4, ISO 4217, optional): the site prices in its
  own currency. Its `rate_card` and the `unit_price` / `unit_cost` of
  items tagged to it are in that currency and convert to the document
  currency through the matching `fx_rates` entry (rule 1b in section 3).
  A site currency with no rate is an integrity failure. A site without
  `currency` prices in the document currency, as in 0.3.
- `rate_card` per site is optional. **Rate resolution rule (0.4):** an
  efforts-priced shot prices from its VENDOR's `rate_card` when the item's
  vendor declares one (2.10); else from its site's `rate_card` when
  `execution_site` is set and that site declares one; else from the
  document-level `rate_card`. No per-department merging between cards -
  the card that resolves must contain every department the shot's
  `efforts` reference.
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
  "vendor": "prime",
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
- `unit_price`: optional override (a money string) - if present, the
  shot prices as `quantity x unit_price` and `efforts` become
  informational. This is how a prime carries a sub's flat price (2.10).
- `vendor` (NEW in 0.4): which declared vendor does this shot (2.10). An
  untagged shot belongs to the prime.
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
  "quantity": 10, "unit": "day", "unit_cost": "1200",
  "execution_site": "mtl", "episode": null, "vendor": "prime", "extensions": {} }
```

`kind` recommended vocabulary: `supervision | onset | editorial |
management | data | other`. `unit_cost` is a money string. Line items
take the same optional `execution_site`, `episode` and `vendor` tags as
shots, with the same semantics - and the same optional `discount` and
`labour_share` fields (2.4, 2.9).

### 2.6 Incentives (v0.2 model)

```json
{ "jurisdiction": "CA-QC", "program": "QPSTC",
  "sites": ["mtl"],
  "labour_share": 0.65, "labour_rate": 0.25, "nonlabour_rate": 0.20,
  "basis": "cost", "cap": "250000" }
```

- `jurisdiction` is ISO 3166 (2.2). `basis` and `cap` are NEW in 0.4:
  - `basis` (`cost`, the default, or `labour`): with `cost` the entry's
    rate is `ls x labour_rate + (1 - ls) x nonlabour_rate` as in 0.3;
    with `labour` the non-labour term is dropped and the credit is
    `ls x cost x labour_rate` - a program that pays on qualifying labour
    only says so instead of pretending its non-labour rate is 0.
  - `cap` (a money string): this incentive's credit over the WHOLE
    document is at most `cap`. When the uncapped sum exceeds it, every
    contribution of THIS incentive is scaled by the same factor
    (rule 6b, section 3), so per-item credits and every partition block
    still reconcile. Other incentives are untouched. A cap per site or
    per vendor is expressed by scoping the incentive (its `sites`), not
    by a second cap field.

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
  "shots_subtotal": "32250", "line_items_subtotal": "9200",
  "gross": "41450", "incentive_credit": "8623.50", "net": "32826.50",
  "by_site": {
    "mtl": { "shots_subtotal": "14850", "line_items_subtotal": "6000",
             "gross": "20850", "incentive_credit": "4795.50", "net": "16054.50" },
    "lon": { "shots_subtotal": "17400", "line_items_subtotal": "0",
             "gross": "17400", "incentive_credit": "3828", "net": "13572" }
  },
  "by_vendor": {
    "prime":      { "shots_subtotal": "27250", "line_items_subtotal": "9200",
                    "gross": "36450", "incentive_credit": "7583.50", "net": "28866.50" },
    "roto-house": { "shots_subtotal": "5000", "line_items_subtotal": "0",
                    "gross": "5000", "incentive_credit": "1040", "net": "3960" }
  }
}
```

Every field is a money string (2 decimals when reported, rule 9).

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
- `by_vendor` (NEW in 0.4): RECOMMENDED in `M1-Vendors`/`M1-Full`
  files. Keys are declared vendor keys; every item belongs to exactly
  one vendor (untagged = the prime), so the blocks sum to the item base
  and overheads belong to no vendor block. Same reconciliation invariant
  as the other two partitions (rule 8).

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

### 2.10 Vendors and sub-bids (NEW in 0.4)

A bid larger than one shop has a **prime** (the party the client
contracts) and **subs** (the shops the prime contracts). 0.3 named one
vendor; 0.4 names them all and says which item is whose.

```json
"parties": {
  "vendor":  { "name": "Example VFX Co", "country": "CA" },
  "vendors": [
    { "key": "prime",      "name": "Example VFX Co", "role": "prime", "country": "CA" },
    { "key": "roto-house", "name": "Roto House",     "role": "sub",   "country": "IN",
      "rate_card": { "roto": "300", "paint": "350" } }
  ]
},
"shots": [
  { "id": "sh-030", "code": "030", "quantity": 1, "unit_price": "4200", "vendor": "roto-house" }
],
"subbids": [
  { "vendor": "roto-house",
    "bid_id": "0a9b8c7d-6e5f-4a4b-8c3d-2e1f0a9b8c7d",
    "revision": { "number": 1 },
    "digest": { "algorithm": "sha256", "value": "...the nested document's digest..." },
    "document": { "bidio": "0.4", "id": "...", "conformance": "M1", ... } }
]
```

- `vendors[]`: `key` (a handle, unique; `[a-z][a-z0-9_-]*`), `name`,
  `role` (`prime` | `sub`), optional `country` and `rate_card` (in the
  DOCUMENT currency). **Exactly one prime.** `parties.vendor` - the 0.3
  party - stays and IS the prime: same name, verifier-enforced. A file
  that declares only the prime uses no vendors feature and needs no
  vendors profile; a second vendor, an item tag, a `by_vendor` block or
  a sub-bid does.
- `vendor` on a shot or line item: which declared vendor does it. An
  untagged item is the prime's. A vendor's `rate_card` is the FIRST card
  in rate resolution for its efforts-priced items (2.2); a sub whose
  offer is a flat price per shot is carried as `unit_price`, which is
  what most sub-bids are.
- `totals.by_vendor`: the money by vendor (2.7).
- `subbids[]`: the sub's OWN OpenBidIO document, nested whole, with the
  three fields that identify it outside (`bid_id`, `revision`) and seal
  it (`digest`, equal to the nested document's own). Every nested
  document is a standalone, conformant 0.4 file: a reader that ignores
  `subbids` loses nothing it needs to recompute the master; a reader
  that opens one gets the sub's bid exactly as the sub sent it.
  **The prime carries the sub's price**: the master's items tagged to
  that vendor MUST price, before the master's own discounts, to the
  sub-bid's `gross` (rule 10). A prime's markup is the prime's business
  - a line item or an extension, never a silently repriced sub item.
  A master may name a vendor with no sub-bid (the sub did not send a
  file); it may not nest a sub-bid for the prime or for a vendor it
  does not declare.

Why nested and not linked: a `references` entry (2.8) links a document
somebody else hosts; a sub-bid is EVIDENCE the prime's number rests on,
and evidence travels with the claim. Why whole and not a delta: the same
reason scenarios are whole documents (2.1) - a file a dumb tool cannot
open by itself is a file that cannot be trusted by itself.

### 2.11 Digest, provenance, file (NEW in 0.4)

```json
"provenance": { "generated_at": "2026-09-25T18:00:00Z", "generated_by": "tally 3.1",
                "source": { "system": "tally", "ref": "MYH v2", "uri": "https://..." } },
"digest":     { "algorithm": "sha256", "value": "6cb5bf65...64 hex..." }
```

- `digest` (REQUIRED): SHA-256 over the **canonical form** of the
  document: the top-level object WITHOUT its `digest` member, serialized
  as JSON with keys sorted, no whitespace (`,` and `:` separators),
  UTF-8, non-ASCII characters unescaped. Any two writers produce the
  same bytes for the same document, so the seal is portable. A document
  whose recomputed digest differs from its declared one has been edited
  after it was written - or written by hand - and is not conformant.
  Locked revisions (2.1) are thereby verifiable, not merely conventional.
- `provenance` (optional): when it was generated, by what (a person or a
  tool, free text) and from what (`source.system`, `source.ref`,
  `source.uri`). `generator` remains the tool's name and version.
- **File**: extension `.bidio`, media type `application/vnd.bidio+json`.
  The 0.3 `<CODE>_v<NN>.bid.json` spelling retires; a writer that keeps
  the `<CODE>_v<NN>` stem names the file `<CODE>_v<NN>.bidio`.

## 3. Normative computation (what "conformant" means)

The unit of computation is the **item** (a shot or a line item). All
rollups - document totals, per-site, per-episode - are sums over items.
This item-level formulation is what makes every partition deterministic.

1. **Rate resolution** (shots priced via efforts): the shot's card is
   its vendor's `rate_card` if the item's vendor (tagged, else the prime)
   declares one; else its site's `rate_card` if `execution_site` is set
   and that site declares one; else the document `rate_card`. Every
   department in the shot's `efforts` MUST exist in the resolved card.
   1b. **Currency.** When the resolved card is a site's and that site
   declares a `currency` other than the document's, the card is in the
   site currency; likewise the `unit_price` / `unit_cost` of any item
   tagged to such a site. The item's base cost is multiplied by the
   `fx_rates` rate for that currency (document units per one site
   unit). Vendor cards and the document card are in the document
   currency. A site currency with no rate is an integrity failure.
2. **Item base cost.**
   Shot: `quantity x unit_price` if `unit_price` is set, else
   `quantity x SUM over departments( efforts[dept] x resolved_rate[dept] )`,
   then x the currency factor of 1b.
   Line item: `quantity x unit_cost` x the currency factor of 1b.
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
   incentives of `ls x labour_rate + (1 - ls) x nonlabour_rate` when the
   incentive's `basis` is `cost` (the default), or `ls x labour_rate`
   when it is `labour`, where `ls` is the ITEM's own `labour_share` if
   declared, else the incentive's `labour_share`. Overhead amounts
   always use the incentive's default share. Site-neutral entries in a
   multi-site file (including all overheads) have rate 0.
6. **Entry credit** = entry cost x entry incentive rate - computed per
   applying incentive, so each incentive's contribution to each entry is
   known.
   6b. **Caps.** For each incentive with a `cap`: sum its contributions
   over every entry; if the sum exceeds `cap`, multiply every one of ITS
   contributions by `cap / sum`. The entry credit is the sum of its
   (scaled) contributions. Because the factor is uniform within the
   incentive, `incentive_credit` in every partition block still equals
   the sum over that block's entries.
7. **Document totals**: `shots_subtotal` = sum of shot costs;
   `line_items_subtotal` = sum of line-item costs; `overhead_total` =
   sum of overhead amounts; `discount_total` = sum of item discount
   amounts; `gross` = shots_subtotal + line_items_subtotal +
   overhead_total; `incentive_credit` = sum of ALL entry credits;
   `net` = gross - incentive_credit.
8. **Partition totals**: a `by_site` block sums exactly the items
   tagged to that site; a `by_episode` block sums exactly the items
   tagged to that episode; a `by_vendor` block sums exactly the items
   whose vendor (tagged, else the prime) is that key. Untagged items and
   ALL overhead amounts appear only in document totals. Invariant
   (checked at full precision): partition blocks plus untagged entries
   reconcile exactly to document totals.
9. **Rounding**: compute at full precision; round each REPORTED field
   to 2 decimals, half-up, and write it as a money string; verifiers
   compare with tolerance 0.005 per field. Because each reported field
   rounds independently, the sum of rounded partition blocks MAY differ
   from the rounded document total by cents - that is arithmetic, not
   nonconformance. The invariant in rule 8 binds at full precision only.
10. **Sub-bids**: for each `subbids` entry, the nested document is
    verified as a document of its own (every rule here, recursively);
    its `bid_id`, `revision` and `digest` equal the wrapper's; and the
    sum of the BASE costs (rule 2, before rule 3's discounts) of the
    master's items tagged to that vendor equals the nested document's
    `totals.gross` within the rule-9 tolerance.
11. **Digest**: the declared `digest.value` equals SHA-256 over the
    canonical form defined in 2.11.

A file is **conformant** when it (a) validates against
`openbidio.schema.json` - a verifier that cannot run the schema check
does not certify, it says so, (b) declares a profile that covers the
features it uses (section 5), (c) passes referential integrity (every
`execution_site`, `episode`, `vendor`, incentive `sites` entry, `by_site`
/ `by_episode` / `by_vendor` key refers to a declared site / episode /
vendor; exactly one prime; every site currency has an `fx_rates` entry;
`variant` implies `bid_id`; **every handle is unique within the
document** - site keys, episode codes, vendor keys, shot ids, line-item
ids, declared department and shot-type keys, `fx_rates` currencies. A
duplicated handle is a silent-wrong-answer generator: two sites keyed
`mtl` would let rate resolution and incentive scoping silently pick one
of them), (d) recomputes to its own `totals`, (e) carries its own digest
and every sub-bid it nests is conformant and priced as the master says
(rules 10-11), and (f) is readable with all unknown `extensions`
ignored. `tools/verify.py` checks all six.

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

| Profile | sites / execution_site | episodes / episode | vendors / vendor / subbids | incentives |
|---|---|---|---|---|
| `M1` | no | no | no | at most 1, document-wide |
| `M1-Multisite` | yes | no | no | any number, each site-scoped |
| `M1-Series` | no | yes | no | at most 1, document-wide |
| `M1-Vendors` | no | no | yes | at most 1, document-wide |
| `M1-Full` | yes | yes | yes | any number, each site-scoped |

"Vendors" as a feature means a second declared vendor, an item `vendor`
tag, a `by_vendor` block or a `subbids` entry; declaring only the prime
in `parties.vendors` is allowed in every profile. Sites plus vendors
without episodes declares `M1-Full`.

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

## 8. Changes since v0.3 (and why)

| Change | Why |
|---|---|
| `parties.vendors[]` (one prime, subs), `vendor` tag on items, `totals.by_vendor` | A bid larger than one shop has a prime and subs. 0.3 named one vendor, so the prime's file either lied about who does what or hid it in extensions. Handles, not names, so a sub's later document can be matched. |
| `subbids[]` - the sub's own document nested whole, with identity and digest, priced as the master says | A sub-bid is the evidence the prime's number rests on; evidence travels with the claim, and a file a dumb tool cannot open by itself cannot be trusted by itself (the scenarios rule). The prime carries the sub's price; a markup is a line, never a silently repriced item. |
| Vendor rate cards first in rate resolution | A sub that bids day rates prices its items from its own card; the site card and the document card follow, unchanged from 0.3. |
| Money is a decimal string | A JSON number is a binary float in most readers; a bid must not depend on which language opened it. Rates and quantities stay numbers - they are not money. |
| `digest` required; `provenance` optional | 0.3 had no way to know a document was the one that was sent. The seal is over a canonical form, so it is portable across writers; locked revisions become verifiable. |
| Incentive `cap` and `basis` | Real programs cap and pay on qualifying labour; 0.3 could say neither. The cap scales one incentive's contributions uniformly, so partition blocks keep reconciling. |
| ISO 3166 jurisdictions; site `currency` + `fx_rates` promoted from M2 | Open question 3 of 0.3 answered; a site that prices in its own currency converts at a frozen rate the file states, instead of a rate somebody applied off-file. |
| `.bidio` extension, `application/vnd.bidio+json` | A file has a name that says what it is. |
| Verifier certifies only with the schema check | 0.3 skipped it with a warning and a file with floats where money strings belong read CONFORMANT. |
| `M1-Vendors` profile; `M1-Full` covers vendors | The profile table stays the contract: a tool that does not do vendors says so. |
| `tools/upgrade.py` | A 0.3 file becomes a certified 0.4 file without anyone retyping money. |

The full history lives in CHANGELOG.md.

## 9. Open questions for the group

1. Department vocabulary - adopt the 15 recommended keys, or trim?
2. Difficulty scale - three levels enough? Per-type or global?
3. Incentive model - is the per-item formula with `basis` and `cap`
   acceptable for M1-class profiles, with the tax service handling the
   rest of real program complexity (top-offs, eligible-cost lists)?
4. Scenario vocabulary - free `variant` strings, or a recommended set?
5. Series workflow - should the group RECOMMEND one-document-per-episode
   or one-document-with-tags as the default convention (both stay legal)?
6. Line-item `kind` list - what is missing for how you bid?
7. Profile names - happy with `M1 / M1-Multisite / M1-Series /
   M1-Vendors / M1-Full`?
8. Sub-bid markups - the prime's markup on a sub is a line item or an
   extension today. Should 0.5 give it a field (`markup` on a vendor,
   0..1), so a client-facing file can state it without exposing the
   sub's document?
9. Money precision - decimal strings carry any precision; should the
   format REQUIRE at most 2 decimals on reported money (totals) and
   leave rate cards free?
10. Digest scope - the seal covers the whole document including
    `extensions`. Should a company be able to add its private block
    after signing (a seal over core fields only)?

---
Files in this folder: `SPEC.md` (this document), `openbidio.schema.json`
(machine validation), `CHANGELOG.md` (version history), `LICENSE`
(CC BY 4.0 spec text, MIT machine artifacts), `fixtures/` (eight
`.bidio` conformance fixtures covering all five profiles: the six 0.3
fixtures upgraded, plus the 0.4 vendors/sub-bid and currency/cap worked
examples), `tools/verify.py` (reference verifier: schema + profile +
referential integrity + totals + digest and sub-bids + extensions),
`tools/upgrade.py` (0.3 -> 0.4), `tools/test_verify.py` (the verifier
pinned).
