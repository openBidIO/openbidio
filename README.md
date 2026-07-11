# bidIO v0.2 - draft bid document format

Second draft of the shared bid format, integrating the group's feedback
on v0.1 (per-shot site + rebate, scenarios, episodic structure) plus the
identity and conformance machinery a long-lived standard needs.
**Everything here is up for debate**; SPEC.md section 9 lists the open
questions, and section 8 is the full v0.1 -> v0.2 changelog with
rationale.

## What's in the folder

| File | What it is |
|---|---|
| `SPEC.md` | The human spec: every field, the normative item-level math, conformance profiles, the extension federation path, governance, changelog, open questions |
| `bidio.schema.json` | Machine validation (JSON Schema 2020-12) - strict on core fields, open at `extensions` |
| `fixtures/fixture-001.bid.json` | Single-site feature bid (`M1`) - the v0.1 fixture carried forward |
| `fixtures/fixture-002-multisite.bid.json` | Two-site bid (`M1-Multisite`): per-site rate cards, site-scoped incentives, site-neutral line item, `by_site` rollups |
| `fixtures/fixture-003-series.bid.json` | Episodic bid (`M1-Series`): episode tags, season-overhead line item, `by_episode` rollups |
| `fixtures/fixture-004a/b-scenario-*.bid.json` | A scenario PAIR: two standalone documents sharing one `bid_id` at the same revision, `variant` "hero" / "lite" |
| `tools/verify.py` | Reference verifier - schema + profile + referential integrity (incl. handle uniqueness) + totals + extensions. Pure Python, one optional dependency |
| `LICENSE` | CC BY 4.0 for the spec text, MIT for schema/tools/fixtures - open format, closed tooling |

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

## What changed since v0.1 (headlines)

1. **Sites are pricing contexts.** Shots carry `execution_site`; sites
   carry their own `rate_card`; incentives scope to sites. The v0.1
   document-level incentive math gave a wrong `net` the moment a bid
   spanned jurisdictions - and rates vary by site for the same reason
   rebates do, so both moved together.
2. **Scenarios without a container.** One new identity field (`bid_id`,
   stable across the whole bid family) plus `revision.variant`. Three
   client options = three standalone conformant documents sharing
   `bid_id` + revision number. No delta encoding, no container format.
3. **Episodic primitives.** `episodes` declaration, `episode` tags,
   `by_episode` rollups, and a clean overhead rule. The format supports
   one-file-per-season AND one-file-per-episode; it dictates neither.
4. **Conformance profiles.** Every file declares `M1`, `M1-Multisite`,
   `M1-Series`, or `M1-Full`, and the verifier cross-checks the
   declaration against the features actually used. Simple tools stay
   first-class citizens forever - they just say what they speak.
5. **Item-level normative math.** Every rollup is a sum over items,
   which is what makes per-site and per-episode totals deterministic.
6. **Resourcing routed to extensions, with a federation path.** Blended
   rates preserve totals, so crew-mix planning is vendor-internal by the
   core test ("does a second tool need it to recompute totals?"). The
   spec now defines how a converging extension gets promoted into an
   optional standard schema - extensions are the R&D pipeline, not a
   dumping ground.

## Governance

bidIO is developed by an open working group (Narro, Entropy, Nano
Visuals, and independent contributors). Intended v1.0 path: publication
under the Visual Effects Society (Technology Committee), SMPTE
standardization track afterwards, PGA endorsement for the producer-side
workflow. Open format, closed tooling - the PDF / USD model.

## Next steps for the group

1. Everyone: does your bidding life fit in this file? Answer with edits,
   or with one of your real bids attempted in it.
2. Contribute 2-3 anonymized past bids as new fixtures - especially a
   real multi-site bid and a real episodic bid.
3. Lock v0.2 at the presentation; the fixtures repo becomes the referee.
