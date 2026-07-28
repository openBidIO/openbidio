# OpenBidIO v0.3 - draft bid document format (formerly bidIO)

Third draft of the shared bid format. v0.2 integrated the group's
structural feedback (sites, scenarios, episodes, profiles); v0.3
promotes the three things real bids kept needing into core: **per-item
discounts**, **overhead percentage lines**, and **per-item labour
share** for honest incentive math. **Everything here is up for
debate**; SPEC.md section 9 lists the open questions, section 8 diffs
against v0.2, and CHANGELOG.md carries the full version history.

## What's in the folder

| File | What it is |
|---|---|
| `SPEC.md` | The human spec: every field, the normative item-level math, conformance profiles, the extension federation path, governance, changelog, open questions |
| `openbidio.schema.json` | Machine validation (JSON Schema 2020-12) - strict on core fields, open at `extensions` |
| `CHANGELOG.md` | Version history: 0.1 -> 0.2 -> 0.2.1 fixes -> 0.3, with the why behind each change |
| `LICENSE` | CC BY 4.0 for the spec text, MIT for schema/tools/fixtures - open format, closed tooling |
| `fixtures/fixture-001.bid.json` | Single-site feature bid (`M1`) - carried forward since v0.1 |
| `fixtures/fixture-002-multisite.bid.json` | Two-site bid (`M1-Multisite`): per-site rate cards, site-scoped incentives, site-neutral line item, `by_site` rollups |
| `fixtures/fixture-003-series.bid.json` | Episodic bid (`M1-Series`): episode tags, season-overhead line item, `by_episode` rollups |
| `fixtures/fixture-004a/b-scenario-*.bid.json` | A scenario PAIR: two standalone documents sharing one `bid_id` at the same revision, `variant` "hero" / "lite" |
| `fixtures/fixture-005-discount-overhead.bid.json` | NEW: the v0.3 worked example - per-item discounts, production + buffer overhead lines, per-item labour_share driving the incentive, totals hand-verified |
| `tools/verify.py` | Reference verifier - schema + profile + referential integrity (incl. handle uniqueness) + totals + extensions. Pure Python, one optional dependency |

## Try it (30 seconds)

```bash
pip install jsonschema        # optional - all other checks work without it
python3 tools/verify.py fixtures/*.bid.json
# -> each file: schema OK / profile OK / totals OK / CONFORMANT
```

Change any number in any fixture and run it again - the verifier tells
you exactly what stopped adding up. That loop IS the standard: any tool
that writes files this verifier accepts, and reads files like the
fixtures, is compatible. No one ever needs to read anyone's source code.

## What changed in v0.3 (headlines)

1. **Discounts are core.** Optional `discount` (0..1) on every shot and
   line item; `cost = base x (1 - discount)`. v0.2 could only bake the
   net into prices, which destroys the gross/discount story a client
   statement and a renegotiation both need. `totals.discount_total`
   shows what was conceded.
2. **Overheads are core.** Document-level percentage lines
   (`production`, `buffer`, ...) computed on the post-discount item
   base. Change a shot's efforts and the overhead rescales - that
   recompute-on-change is exactly the core-inclusion test. Site-neutral
   by definition; never inside partition blocks.
3. **Per-item labour share.** An item may declare its own
   `labour_share` (a stock purchase is 0, a pure-artist shot is 1),
   overriding the incentive's blended default. Per-item credits now
   track where the labour actually is. Program intricacies (caps,
   top-offs) stay in the tax service and extensions.
4. **One rates convention, stated normatively.** Every rate, share, and
   discount in the format is a 0..1 decimal. Nothing uses 0..100.
5. **Carried from the 0.2.1 fixes:** handle uniqueness is normative and
   verifier-enforced (a duplicated site key used to silently re-price a
   document), and the package ships a LICENSE.

## Reference implementation

Tally (Entropy's bidding engine) reads and writes this format natively:
export produces a self-verified conformant document per bid revision,
import verifies-then-materializes with a preview step. The round-trip
(export -> independent reimport -> re-export) reproduces totals to the
cent - the "same file, two engines, identical totals" proof the M1
milestone asks every engine to pass.

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
