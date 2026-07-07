#!/usr/bin/env python3
"""bidIO v0.1 reference verifier.

Usage:  python3 verify.py <file.bid.json> [more files...]

Checks the three conformance conditions from SPEC.md section 3:
  1. schema validity        (needs `pip install jsonschema`; skipped with a
                             warning if the library is absent)
  2. totals recomputation   (pure stdlib - the normative math)
  3. extensions hygiene     (unknown namespaces are fine; non-namespaced
                             extension keys are flagged)

Exit code 0 = conformant, 1 = not, 2 = usage/read error.
This file is deliberately dependency-light so any implementer can run it
on day one.
"""
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

TOLERANCE = Decimal("0.005")
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "bidio.schema.json"


def d(x):
    return Decimal(str(x))


def round2(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def check_schema(doc, problems):
    try:
        import jsonschema
    except ImportError:
        print("  [warn] jsonschema not installed - schema check skipped "
              "(pip install jsonschema)")
        return
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    for e in errs:
        loc = "/".join(str(p) for p in e.path) or "<root>"
        problems.append(f"schema: {loc}: {e.message}")
    if not errs:
        print("  schema: OK")


def compute_totals(doc, problems):
    rate_card = {k: d(v) for k, v in (doc.get("rate_card") or {}).items()}
    shots_subtotal = Decimal(0)
    for shot in doc.get("shots", []):
        qty = d(shot.get("quantity", 1))
        if shot.get("unit_price") is not None:
            cost = qty * d(shot["unit_price"])
        else:
            efforts = shot.get("efforts") or {}
            cost = Decimal(0)
            for dept, days in efforts.items():
                if dept not in rate_card:
                    problems.append(
                        f"shot {shot.get('code', shot.get('id'))}: department "
                        f"'{dept}' priced via efforts but missing from rate_card")
                    continue
                cost += d(days) * rate_card[dept]
            cost *= qty
        shots_subtotal += cost

    line_subtotal = sum(
        (d(li["quantity"]) * d(li["unit_cost"]) for li in doc.get("line_items", [])),
        Decimal(0))

    gross = shots_subtotal + line_subtotal

    credit = Decimal(0)
    for inc in doc.get("incentives", []):
        ls = d(inc["labour_share"])
        credit += gross * ls * d(inc["labour_rate"])
        credit += gross * (1 - ls) * d(inc["nonlabour_rate"])

    net = gross - credit
    return {
        "shots_subtotal": round2(shots_subtotal),
        "line_items_subtotal": round2(line_subtotal),
        "gross": round2(gross),
        "incentive_credit": round2(credit),
        "net": round2(net),
    }


def check_totals(doc, problems):
    declared = doc.get("totals") or {}
    computed = compute_totals(doc, problems)
    ok = True
    for key, cval in computed.items():
        if key not in declared:
            if key in ("gross", "incentive_credit", "net"):
                problems.append(f"totals: required field '{key}' missing")
                ok = False
            continue
        dval = d(declared[key])
        if abs(dval - cval) > TOLERANCE:
            problems.append(
                f"totals: {key} declared {dval} but recomputes to {cval}")
            ok = False
    if ok:
        print("  totals: OK "
              f"(gross {computed['gross']}, credit {computed['incentive_credit']}, "
              f"net {computed['net']} {doc.get('currency', '')})")


def check_extensions(node, path, problems):
    if isinstance(node, dict):
        ext = node.get("extensions")
        if isinstance(ext, dict):
            for ns in ext:
                if "." not in ns:
                    problems.append(
                        f"extensions at {path or '<root>'}: namespace '{ns}' "
                        "is not dotted (expected e.g. 'com.yourco')")
        for k, v in node.items():
            if k != "extensions":
                check_extensions(v, f"{path}/{k}" if path else k, problems)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_extensions(v, f"{path}[{i}]", problems)


def verify(path):
    print(f"{path}:")
    try:
        doc = json.loads(Path(path).read_text())
    except Exception as e:
        print(f"  [fail] cannot read/parse: {e}")
        return False
    problems = []
    check_schema(doc, problems)
    check_totals(doc, problems)
    check_extensions(doc, "", problems)
    if problems:
        for p in problems:
            print(f"  [fail] {p}")
        return False
    print("  CONFORMANT (bidIO v0.1)")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    results = [verify(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
