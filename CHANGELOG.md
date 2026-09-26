# OpenBidIO changelog

All notable changes to the OpenBidIO (formerly bidIO) format, schema, verifier, and fixtures.
Pre-1.0 rule: readers match major.minor exactly; minors MAY break.

## 0.4 - 2026-09-25 (draft)

The "who does the work" release. Every real bid larger than one shop has
subcontractors, and 0.3 could only name one vendor, so the prime's file
either lied about who does what or hid it in extensions. 0.4 makes the
vendors, their share of the money and their own bids first-class - and
closes four things the 0.3 review measured as missing: money as floats, a
document with no seal, an incentive with no cap, and a verifier that
certified without its schema.

### Name
- **Renamed: bidIO -> OpenBidIO.** Publishing under the Open* convention of
  the VFX standards the format aims to sit beside (OpenEXR, OpenColorIO,
  OpenTimelineIO). Schema moves to `openbidio.schema.json` with `$id`
  namespace `https://openbidio.dev/...`; the v0.1-v0.3 tags keep their
  original bidIO identity as honest history. Known neighbor: OpenBID, a
  commercial VFX bidding tool - the name is retained knowingly; a future
  ratification body is free to rename. Scope note: the format is written
  for VFX bids today but is intended to grow into a post-production-wide
  bidding standard.

### Format
- **`parties.vendors[]`** `{key, name, role: prime|sub, country?,
  rate_card?}` - unique handles, EXACTLY ONE prime. `parties.vendor` (the
  0.3 party) stays and IS the prime (same name, verifier-enforced), so a
  0.3-shaped reader still finds one vendor. Declaring only the prime is
  not a computational feature and needs no new profile.
- **`vendor` tag** on shots and line items: a declared vendor key; an
  untagged item belongs to the prime. **Rate resolution** for an
  efforts-priced shot is now vendor card -> site card -> document card.
  Vendor cards are in the document currency.
- **`totals.by_vendor`**: the third partition, same block shape and the
  same full-precision reconciliation invariant as `by_site` /
  `by_episode`. Overheads belong to no vendor block.
- **`subbids[]`**: a sub's own standalone 0.4 document nested whole -
  `{vendor, bid_id, revision, digest, document}`. The nested document is
  verified on its own; its identity and digest must match the wrapper;
  and the master's items tagged to that vendor MUST price, before the
  master's own discounts, to the sub-bid's `gross` (SPEC 2.10, math rule
  10). A prime carries the sub's price; a markup is the prime's business
  and lives in the prime's own lines or extensions, never in a silently
  repriced item.
- **Profile `M1-Vendors`** (vendors, no sites, no episodes); `M1-Full`
  now covers vendors too.
- **Money is a decimal STRING** (`"800"`, `"8623.5"`): rate cards,
  `unit_price`, `unit_cost`, `cap`, every totals field. A JSON number is
  a binary float in most readers and 0.1 + 0.2 is the bug the format
  exists to prevent. Rates, shares, discounts (0..1), quantities, days and
  `fx_rates.rate` stay numbers - they are not money. (Alternative
  considered: integer minor units; rejected because a rate card in whole
  currency units is what people read and write.)
- **`digest`** (required): `{algorithm: "sha256", value}` over the
  canonical form of the document without its `digest` member (keys
  sorted, no whitespace, UTF-8). A document that was edited after it was
  written fails its own seal. **`provenance`** (optional):
  `{generated_at, generated_by, source: {system, ref, uri}}`.
- **Incentive `cap`** (money) and **`basis`** (`cost` | `labour`,
  default `cost`): the incentive's credit over the whole document is at
  most `cap`, and when it exceeds, every contribution of THAT incentive
  scales by the same factor so partition blocks still reconcile; `basis:
  labour` drops the non-labour term (credit = labour share x cost x
  labour_rate). Real programs cap; 0.3 could not say so.
- **`jurisdiction` is ISO 3166**: alpha-2 country with an optional 3166-2
  subdivision (`CA-QC`, `GB-ENG`, `US-NY`, `NZ`) on sites and
  incentives - the schema refuses "Quebec".
- **`sites[].currency`** (ISO 4217): a site's rate card and the
  `unit_price` / `unit_cost` of items tagged to it are in that currency
  and convert to the document currency through `fx_rates` (document
  units per one site unit); a site currency with no rate is an integrity
  failure. Resolves 0.3 open question 3.
- **File extension `.bidio`**, media type `application/vnd.bidio+json`.
  The 0.3 `<CODE>_v<NN>.bid.json` spelling retires.

### Schema
- `$id` is a URL that RESOLVES: `https://openbidio.github.io/openbidio/schema/0.4/openbidio.schema.json` (GitHub Pages serves the repo; `openbidio.dev` was never registered, and an id nobody can fetch is a promise nobody can check). The root `openbidio.schema.json` is the source; `schema/0.4/` is the hosted copy, pinned equal by the tests. `bidio` pattern accepts `0.4(.x)`;
  `digest` required; `money` / `jurisdiction` / `vendorKey` / `digest` /
  `provenance` / `subbid` (recursive `$ref: "#"`) definitions;
  `conformance` gains `M1-Vendors`.

### Verifier
- **Refuses to certify without the schema check**: a missing
  `jsonschema` is a problem, not a warning. 0.3 skipped the check and a
  file with floats where money strings belong read CONFORMANT.
- Six conditions: schema, profile (now vendors), integrity (vendor keys,
  one prime, site currencies), totals (vendor rate resolution, currency,
  caps, `by_vendor`), digest + sub-bids, extensions. The math is a library
  (`item_costs`, `rollup`, `compute_digest`); only `verify()` prints.
- `tools/upgrade.py` rewrites a conformant 0.3 file as a certified 0.4
  file (money strings, the prime, provenance, digest, `.bidio`).
- `tools/test_verify.py` pins all of the above (pytest).

### Fixtures
- The six 0.3 fixtures upgraded in place (same numbers, now `.bidio`).
- NEW `fixture-006-vendors.bidio` (`M1-Vendors`): a prime and a sub,
  vendor tags, a discounted sub item, `by_vendor`, the sub's own document
  nested as a sub-bid.
- NEW `fixture-007-currency-cap.bidio` (`M1-Full`): London pricing in GBP
  through `fx_rates`, a labour-basis UK credit capped at 3000 CAD beside
  an uncapped Quebec credit, `by_site` and `by_vendor` together.

## 0.3 - 2026-07-23 (draft)

The "real bids have discounts" release. Three things production bids
kept needing were promoted from workarounds into core, and the format
now states its rates convention normatively.

### Format
- **Per-item `discount`** (0..1) on shots and line items:
  `cost = base x (1 - discount)`. New optional `totals.discount_total`.
  No document-level discount field - "8% across the bid" is written by
  stamping items, keeping every rollup a plain sum (SPEC 2.9).
- **`overheads` document-level percentage lines** (`{key, label?,
  rate}`): amount = `rate x` post-discount item base; `gross` now
  includes `totals.overhead_total`. Overheads are site-neutral and
  episode-untagged by definition: document-wide incentives apply to
  them in single-site files, site-scoped incentives never do, and they
  never appear inside partition blocks (SPEC 2.9, math steps 4-8).
- **Per-item `labour_share`** (0..1) on shots and line items, overriding
  the incentive's document-default share for that item. Per-item
  credits now track where the labour actually is instead of smearing
  one blended share across purchases and artist work (SPEC 2.6).
- **Rates convention normative**: every rate, share, and discount in
  the format is a 0..1 decimal. Nothing uses 0..100.

### Schema
- `$id` bumped to `/schema/0.3/`; `bidio` pattern accepts `0.3(.x)`.
- New: `overheads[]`; `discount` + `labour_share` on shot and lineItem;
  `discount_total` + `overhead_total` on totals.

### Verifier
- Normative math extended: discounts (step 3), overhead lines
  (step 4), per-item labour_share (step 5). Overhead amounts join the
  computation pool as untagged entries, so the full-precision partition
  invariant covers them unchanged.
- Overhead `key` joins the handle-uniqueness set.
- Rejects non-0.3 files (exact minor match).

### Fixtures
- New `fixture-005-discount-overhead.bid.json`: discounts, overheads,
  per-item labour_share, hand-verified totals
  (gross 30,590.00 / credit 6,447.70 / net 24,142.30 USD).
- Fixtures 001-004 carried forward unchanged except the version bump
  (they use no 0.3 feature; totals identical).

## 0.2.1 - 2026-07-23 (fixes within the 0.2 draft)

- **Verifier: handle uniqueness enforced.** A document with two sites
  both keyed `mtl` passed CONFORMANT and silently priced every shot off
  the LAST declaration (proven with a test document: 15,000 instead of
  12,000). Site keys, episode codes, shot ids, line-item ids, declared
  department and shot-type keys, and fx_rates currencies must now be
  unique; the spec documents uniqueness as normative.
- **LICENSE added**: CC BY 4.0 for the specification text, MIT for
  schema/tools/fixtures. Open format, closed tooling (PDF/USD model).
- Verifier: `profile: OK` line no longer suppressed by unrelated
  problems from other checks.
- SPEC: `frames` documented on shots (`{count, in, out}`) and episodes
  (`{count}`) - the schema always allowed them.

## 0.2 - 2026-07-11 (draft)

Integrated the group's feedback on 0.1 (Marie-Eve's four points):

- `bid_id` + `revision.variant`: scenarios as sibling standalone
  documents sharing a bid-family anchor; no container format.
- `sites` as pricing contexts: per-site rate cards, `execution_site`
  tags, MANDATORY site scoping of incentives in multi-site files
  (a Quebec credit silently applying to London work became
  structurally impossible).
- Episodic primitives: `episodes[]`, `episode` tags, `by_episode`
  rollups, untagged = series overhead. Format supports one-file-per-
  season AND per-episode; dictates neither.
- Conformance profiles (`M1`, `M1-Multisite`, `M1-Series`, `M1-Full`)
  declared in every file, verifier cross-checks declaration vs use.
- Item-level normative math: every rollup a deterministic sum over
  items; full-precision partition invariant.
- `references[]` (URI + sha256, never embedded); `project.kind`
  advisory; 0.x exact-minor version rule; resourcing routed to
  extensions with the federation path (ship namespaced, converge,
  promote - the USD pattern).

## 0.1 - 2026-07-07 (draft)

First assembly pass, drafted from the group's combined inputs after the
Jul 6 shared-bidding-tool meeting: single JSON document = one bid
(shots, efforts, rates, one incentive, totals, award state), JSON
Schema validation, reference verifier, first fixture. Established the
core tests that still govern the format: "a format, not a template",
"does a second tool need this field to recompute the same totals?",
and writers-populate / readers-recompute totals as the conformance
handshake.
