#!/usr/bin/env python3
"""bidIO v0.2 reference verifier.

Usage:  python3 verify.py <file.bid.json> [more files...]

Checks the five conformance conditions from SPEC.md section 3:
  1. schema validity          (needs `pip install jsonschema`; skipped with
                               a warning if the library is absent)
  2. profile coverage         (declared `conformance` covers features used)
  3. referential integrity    (handle uniqueness, site/episode keys,
                               incentive scoping, variant -> bid_id)
  4. totals recomputation     (pure stdlib - the normative item-level math,
                               including by_site / by_episode blocks)
  5. extensions hygiene       (unknown namespaces are fine; non-namespaced
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
PROFILES = ("M1", "M1-Multisite", "M1-Series", "M1-Full")


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


def features_used(doc):
    """Which computational feature axes does this document actually use?"""
    multisite = bool(doc.get("sites")) or any(
        it.get("execution_site")
        for it in doc.get("shots", []) + doc.get("line_items", []))
    series = bool(doc.get("episodes")) or any(
        it.get("episode")
        for it in doc.get("shots", []) + doc.get("line_items", []))
    return multisite, series


def check_profile(doc, problems):
    profile = doc.get("conformance")
    if profile not in PROFILES:
        problems.append(f"profile: conformance '{profile}' unknown "
                        f"(expected one of {', '.join(PROFILES)})")
        return
    before = len(problems)
    multisite, series = features_used(doc)
    n_inc = len(doc.get("incentives", []))
    if multisite and profile in ("M1", "M1-Series"):
        problems.append(
            f"profile: file uses sites/execution_site but declares '{profile}' "
            "(needs M1-Multisite or M1-Full)")
    if series and profile in ("M1", "M1-Multisite"):
        problems.append(
            f"profile: file uses episodes but declares '{profile}' "
            "(needs M1-Series or M1-Full)")
    if not multisite and n_inc > 1:
        problems.append(
            f"profile: {n_inc} incentives in a single-site file "
            "(M1/M1-Series allow at most one, document-wide)")
    if len(problems) == before:
        print(f"  profile: OK ({profile})")


def _check_unique(values, what, problems):
    """Duplicate handles are silent-wrong-answer generators: a duplicated
    site key means rate resolution and incentive scoping silently pick one
    of the two declarations. Reject them all."""
    seen, dups = set(), set()
    for v in values:
        if v in seen:
            dups.add(v)
        seen.add(v)
    for v in sorted(dups):
        problems.append(f"integrity: duplicate {what} '{v}' - handles must "
                        "be unique within the document")


def check_integrity(doc, problems):
    _check_unique([s["key"] for s in doc.get("sites", [])],
                  "site key", problems)
    _check_unique([e["code"] for e in doc.get("episodes", [])],
                  "episode code", problems)
    _check_unique([s.get("id") for s in doc.get("shots", []) if s.get("id")],
                  "shot id", problems)
    _check_unique([li.get("id") for li in doc.get("line_items", [])
                   if li.get("id")], "line item id", problems)
    _check_unique([d["key"] for d in doc.get("departments", [])],
                  "department key", problems)
    _check_unique([t["key"] for t in doc.get("shot_types", [])],
                  "shot type key", problems)
    _check_unique([f["currency"] for f in doc.get("fx_rates", [])],
                  "fx_rates currency", problems)

    site_keys = {s["key"] for s in doc.get("sites", [])}
    episode_codes = {e["code"] for e in doc.get("episodes", [])}
    has_sites = bool(doc.get("sites"))

    for coll, label in (("shots", "shot"), ("line_items", "line item")):
        for it in doc.get(coll, []):
            ident = it.get("code") or it.get("id")
            es = it.get("execution_site")
            if es is not None and es not in site_keys:
                problems.append(
                    f"integrity: {label} {ident}: execution_site '{es}' "
                    "is not a declared site")
            ep = it.get("episode")
            if ep is not None and ep not in episode_codes:
                problems.append(
                    f"integrity: {label} {ident}: episode '{ep}' "
                    "is not a declared episode")

    for i, inc in enumerate(doc.get("incentives", [])):
        scope = inc.get("sites")
        if has_sites:
            if not scope:
                problems.append(
                    f"integrity: incentive[{i}] ({inc.get('jurisdiction')}): "
                    "multi-site files require every incentive to declare "
                    "a non-empty 'sites' scope")
            else:
                for k in scope:
                    if k not in site_keys:
                        problems.append(
                            f"integrity: incentive[{i}]: scoped site '{k}' "
                            "is not a declared site")
        elif scope:
            problems.append(
                f"integrity: incentive[{i}]: carries a 'sites' scope but the "
                "file declares no sites")

    totals = doc.get("totals") or {}
    for key in (totals.get("by_site") or {}):
        if key not in site_keys:
            problems.append(f"integrity: totals.by_site key '{key}' "
                            "is not a declared site")
    for key in (totals.get("by_episode") or {}):
        if key not in episode_codes:
            problems.append(f"integrity: totals.by_episode key '{key}' "
                            "is not a declared episode")

    if (doc.get("revision") or {}).get("variant") and not doc.get("bid_id"):
        problems.append("integrity: revision.variant requires bid_id "
                        "(scenarios need their bid-family anchor)")


def item_costs(doc, problems):
    """Compute every item's (cost, credit_rate, site, episode, is_shot).

    This is the normative item-level math from SPEC section 3.
    """
    doc_card = {k: d(v) for k, v in (doc.get("rate_card") or {}).items()}
    site_cards = {
        s["key"]: {k: d(v) for k, v in s["rate_card"].items()}
        for s in doc.get("sites", []) if s.get("rate_card")}
    has_sites = bool(doc.get("sites"))
    incentives = doc.get("incentives", [])

    def incentive_rate(site):
        rate = Decimal(0)
        for inc in incentives:
            scope = inc.get("sites")
            applies = (not has_sites and not scope) or \
                      (site is not None and scope and site in scope)
            if applies:
                ls = d(inc["labour_share"])
                rate += ls * d(inc["labour_rate"])
                rate += (1 - ls) * d(inc["nonlabour_rate"])
        return rate

    items = []
    for shot in doc.get("shots", []):
        qty = d(shot.get("quantity", 1))
        site = shot.get("execution_site")
        if shot.get("unit_price") is not None:
            cost = qty * d(shot["unit_price"])
        else:
            card = site_cards.get(site, doc_card) if site else doc_card
            cost = Decimal(0)
            for dept, days in (shot.get("efforts") or {}).items():
                if dept not in card:
                    problems.append(
                        f"math: shot {shot.get('code', shot.get('id'))}: "
                        f"department '{dept}' priced via efforts but missing "
                        "from the resolved rate card "
                        f"({'site ' + site if site and site in site_cards else 'document'})")
                    continue
                cost += d(days) * card[dept]
            cost *= qty
        items.append((cost, incentive_rate(site), site,
                      shot.get("episode"), True))

    for li in doc.get("line_items", []):
        cost = d(li["quantity"]) * d(li["unit_cost"])
        site = li.get("execution_site")
        items.append((cost, incentive_rate(site), site,
                      li.get("episode"), False))
    return items


def rollup(items):
    shots = sum((c for c, _, _, _, is_shot in items if is_shot), Decimal(0))
    lines = sum((c for c, _, _, _, is_shot in items if not is_shot), Decimal(0))
    gross = shots + lines
    credit = sum((c * r for c, r, _, _, _ in items), Decimal(0))
    return {
        "shots_subtotal": shots,
        "line_items_subtotal": lines,
        "gross": gross,
        "incentive_credit": credit,
        "net": gross - credit,
    }


def compare_block(declared, computed, ctx, problems):
    ok = True
    for key, cval in computed.items():
        if key not in declared:
            if key in ("gross", "incentive_credit", "net"):
                problems.append(f"totals: {ctx}: required field '{key}' missing")
                ok = False
            continue
        if abs(d(declared[key]) - round2(cval)) > TOLERANCE:
            problems.append(
                f"totals: {ctx}: {key} declared {declared[key]} "
                f"but recomputes to {round2(cval)}")
            ok = False
    return ok


def check_totals(doc, problems):
    declared = doc.get("totals") or {}
    items = item_costs(doc, problems)
    doc_totals = rollup(items)
    ok = compare_block(declared, doc_totals, "document", problems)

    for site_key, block in (declared.get("by_site") or {}).items():
        subset = [it for it in items if it[2] == site_key]
        ok &= compare_block(block, rollup(subset), f"by_site.{site_key}", problems)

    for ep_code, block in (declared.get("by_episode") or {}).items():
        subset = [it for it in items if it[3] == ep_code]
        ok &= compare_block(block, rollup(subset), f"by_episode.{ep_code}", problems)

    # Partition invariant at full precision: tagged blocks + untagged = doc.
    if declared.get("by_site") is not None:
        tagged = [it for it in items if it[2] is not None]
        untagged = [it for it in items if it[2] is None]
        if rollup(tagged)["gross"] + rollup(untagged)["gross"] != doc_totals["gross"]:
            problems.append("totals: by_site partition does not reconcile "
                            "to document gross at full precision")
    if declared.get("by_episode") is not None:
        tagged = [it for it in items if it[3] is not None]
        untagged = [it for it in items if it[3] is None]
        if rollup(tagged)["gross"] + rollup(untagged)["gross"] != doc_totals["gross"]:
            problems.append("totals: by_episode partition does not reconcile "
                            "to document gross at full precision")

    if ok:
        print("  totals: OK "
              f"(gross {round2(doc_totals['gross'])}, "
              f"credit {round2(doc_totals['incentive_credit'])}, "
              f"net {round2(doc_totals['net'])} {doc.get('currency', '')})")


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
    version = str(doc.get("bidio", ""))
    if not (version == "0.2" or version.startswith("0.2.")):
        print(f"  [fail] version: file declares bidio '{version}' - this is a "
              "0.2 verifier and 0.x readers match major.minor exactly")
        return False
    problems = []
    check_schema(doc, problems)
    check_profile(doc, problems)
    check_integrity(doc, problems)
    check_totals(doc, problems)
    check_extensions(doc, "", problems)
    if problems:
        for p in problems:
            print(f"  [fail] {p}")
        return False
    print(f"  CONFORMANT (bidIO v0.2, profile {doc.get('conformance')})")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    results = [verify(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
