# OpenBidIO v0.5 - draft bid document format (formerly bidIO)

Canonical home: https://github.com/openBidIO/openbidio - rendered spec: https://openbidio.github.io/openbidio/

Fifth draft of the shared bid format. v0.2 integrated the group's
structural feedback (sites, scenarios, episodes, profiles); v0.3
promoted per-item discounts, overhead lines and per-item labour share
into core; v0.4 said who does the work (vendors, their money, their own
bids nested whole, money as decimal strings, a digest on every
document); **v0.5 says what a price rests on and what it answers**: a
shot's `assumptions`, and `in_response_to` so a vendor's bid names the
bid it answers. 0.5 only adds optional fields - no computation changes.
**Everything here is up for debate**; SPEC.md section 9 lists the open
questions, section 8 diffs against v0.4, and CHANGELOG.md carries the
full version history.

A document is a `.bidio` file (media type `application/vnd.bidio+json`),
JSON inside.

## What's in the folder

| File | What it is |
|---|---|
| `SPEC.md` | The human spec: every field, the normative item-level math, conformance profiles, the extension federation path, governance, changelog, open questions |
| `openbidio.schema.json` | Machine validation (JSON Schema 2020-12) - strict on core fields, open at `extensions`. Its `$id` resolves: https://openbidio.github.io/openbidio/schema/0.5/openbidio.schema.json (`schema/0.5/` is that hosted copy; `schema/0.4/` stays hosted, frozen) |
| `CHANGELOG.md` | Version history: 0.1 -> 0.2 -> 0.2.1 fixes -> 0.3 -> 0.4 -> 0.5, with the why behind each change |
| `LICENSE` | CC BY 4.0 for the spec text, MIT for schema/tools/fixtures - open format, closed tooling |
| `fixtures/fixture-001.bidio` | Single-site feature bid (`M1`) - carried forward since v0.1 |
| `fixtures/fixture-002-multisite.bidio` | Two-site bid (`M1-Multisite`): per-site rate cards, site-scoped incentives, site-neutral line item, `by_site` rollups |
| `fixtures/fixture-003-series.bidio` | Episodic bid (`M1-Series`): episode tags, season-overhead line item, `by_episode` rollups |
| `fixtures/fixture-004a/b-scenario-*.bidio` | A scenario PAIR: two standalone documents sharing one `bid_id` at the same revision, `variant` "hero" / "lite" |
| `fixtures/fixture-005-discount-overhead.bidio` | The v0.3 worked example - per-item discounts, production + buffer overhead lines, per-item labour_share driving the incentive |
| `fixtures/fixture-006-vendors.bidio` | NEW in 0.4 (`M1-Vendors`): a prime and a sub, vendor tags, a discounted sub item, `by_vendor`, and the sub's own document nested as a sub-bid |
| `fixtures/fixture-007-currency-cap.bidio` | NEW in 0.4 (`M1-Full`): London pricing in GBP through `fx_rates`, a labour-basis UK credit capped at 3000 CAD beside an uncapped Quebec credit, `by_site` and `by_vendor` together |
| `fixtures/fixture-008-vendor-response.bidio` | NEW in 0.5 (`M1`): the sub's bid standing alone - a response naming the prime's bid it answers (`in_response_to`), with the sub's own `assumptions` per shot; `fixture-006` nests it as its sub-bid |
| `tools/verify.py` | Reference verifier - schema + profile + referential integrity + totals (vendor / site / document rate resolution, site currencies, caps, three partitions) + digest and sub-bids + extensions. Pure Python; `jsonschema` is REQUIRED to certify (a file is never CONFORMANT without the schema check) |
| `tools/upgrade.py` | Rewrites a conformant 0.3 `.bid.json` or 0.4 `.bidio` as a certified 0.5 `.bidio` (0.3: money strings, the prime; every upgrade: provenance, a new digest, nested sub-bids upgraded with their master) |
| `tools/make_fixtures.py` | Writes the worked examples (006, 007, 008) with totals computed by plain arithmetic, independently of the verifier, then certified |
| `tools/test_verify.py` | The verifier pinned (pytest): every fixture certifies, every 0.4 and 0.5 rule refuses in words, the upgrade round-trips |

## Try it (30 seconds)

```bash
pip install jsonschema        # required to certify - the schema is where money strings, keys and enums are held
python3 tools/verify.py fixtures/*.bidio
# -> each file: schema OK / profile OK / totals OK / digest OK / CONFORMANT
python3 tools/upgrade.py my_bid_v03.bid.json   # -> my_bid_v03.bidio, certified
```

Change any number in any fixture and run it again - the verifier tells
you exactly what stopped adding up. That loop IS the standard: any tool
that writes files this verifier accepts, and reads files like the
fixtures, is compatible. No one ever needs to read anyone's source code.

## What changed in v0.5 (headlines)

1. **A shot carries its assumptions.** `assumptions` is the text the
   price holds under - clean plate supplied, one review round. Vendors
   are compared on their assumptions as much as on their numbers; 0.4
   could only hide them in `notes`. No total moves with them.
2. **A response names what it answers.** `in_response_to` {`bid_id`,
   `revision`, `id`?}: a vendor's bid is an ordinary document that says
   which bid it answers. Nested as a sub-bid, it must answer the master's
   bid. No new document type, no new profile.
3. **`tools/upgrade.py` takes 0.4 too** - the version, the nested
   sub-bids and a new seal; no money moves.

## What changed in v0.4 (headlines)

1. **Vendors are core.** `parties.vendors[]` names the prime and its
   subs by handle; every shot and line item says whose it is (`vendor`,
   untagged = the prime); `totals.by_vendor` says how the money splits.
   A sub's own document nests whole in `subbids[]`, sealed, and the
   master's items for that vendor must price to the sub-bid's gross.
2. **Money is a decimal string.** `"800"`, never `800`. A JSON number is
   a binary float in most readers and a bid must not depend on which
   language opened it. Rates, shares and quantities stay numbers.
3. **Every document carries its digest.** SHA-256 over a canonical form;
   an edited file fails its own seal. `provenance` says where it came from.
4. **Incentives can cap and pay on labour only** (`cap`, `basis`).
5. **Jurisdictions are ISO 3166; a site may price in its own currency**
   through `fx_rates` - 0.3's open question 3, answered.
6. **`.bidio` files**, media type `application/vnd.bidio+json`.
7. **The verifier never certifies without its schema** - 0.3 skipped
   the check with a warning; `tools/upgrade.py` moves a 0.3 file up.

## Governance

OpenBidIO is developed by an open working group (Narro, Entropy, Nano
Visuals, and independent contributors). Intended v1.0 path: publication
under the Visual Effects Society (Technology Committee), SMPTE
standardization track afterwards, PGA endorsement for the producer-side
workflow. Open format, closed tooling - the PDF / USD model.

## Next steps for the group

1. Everyone: does your bidding life fit in this file? Answer with edits,
   or with one of your real bids attempted in it.
2. Contribute 2-3 anonymized past bids as new fixtures - especially a
   real multi-site bid, a real episodic bid, and a real discounted bid.
3. Lock the draft at the presentation; the fixtures repo becomes the
   referee.
