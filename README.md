# bidIO v0.1 - draft bid document format

The "first assembly pass" of the shared bid format, as owed from the
July 6 call - a starting point for the group to cut down and lock
together at the two-week presentation. **Everything here is up for
debate**; SPEC.md section 5 lists the open questions.

## What's in the folder

| File | What it is |
|---|---|
| `SPEC.md` | The human spec: every field, what it means, the normative math, what "conformant" means, and the open questions for the group |
| `bidio.schema.json` | Machine validation (JSON Schema 2020-12) - strict on core fields, open at `extensions` |
| `fixtures/fixture-001.bid.json` | A complete example bid: 5 shots (types + difficulty + per-department days), 2 line items, one incentive - with hand-verified totals. The first conformance fixture |
| `tools/verify.py` | Reference verifier - run it on any file: schema check + recomputes the totals + extensions hygiene. Pure Python, one optional dependency |

## Try it (30 seconds)

```bash
pip install jsonschema        # optional - totals check works without it
python3 tools/verify.py fixtures/fixture-001.bid.json
# -> schema: OK / totals: OK / CONFORMANT (bidIO v0.1)
```

Change any number in the fixture and run it again - the verifier tells
you exactly what stopped adding up. That loop IS the standard: any tool
that writes files this verifier accepts, and reads files like the
fixture, is compatible. No one ever needs to read anyone's source code.

## Design in one paragraph

A format, not a template: one JSON file fully describes a bid (shots
with types/difficulty/tags, person-days per department, rate card,
line items, incentive, totals, revision + award state), every tool and
spreadsheet is just a view over it, and company-specific data travels in
namespaced `extensions` that others safely ignore. Milestone-1 keeps the
core small (single currency, one jurisdiction, manual days); richer
things (multi-currency FX, award allocation) have reserved optional
homes so nothing breaks later. Totals are mandatory and recomputable -
that redundancy is the conformance handshake.

## Next steps for the group

1. Everyone: does your bidding life fit in this file? What's missing?
   (Answer with edits, or with one of your real bids attempted in it.)
2. Contribute 2-3 anonymized past bids as new fixtures.
3. Lock v0.1 at the presentation; the fixtures repo becomes the referee.
