# OpenBidIO changelog

All notable changes to the OpenBidIO (formerly bidIO) format, schema, verifier, and fixtures.
Pre-1.0 rule: readers match major.minor exactly; minors MAY break.

## Unreleased

- **Renamed: bidIO -> OpenBidIO.** Publishing under the Open* convention of
  the VFX standards the format aims to sit beside (OpenEXR, OpenColorIO,
  OpenTimelineIO). Schema moves to `openbidio.schema.json` with `$id`
  namespace `https://openbidio.dev/...`; the v0.1-v0.3 tags keep their
  original bidIO identity as honest history. Known neighbor: OpenBID, a
  commercial VFX bidding tool - the name is retained knowingly; a future
  ratification body is free to rename. Scope note: the format is written
  for VFX bids today but is intended to grow into a post-production-wide
  bidding standard.

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
