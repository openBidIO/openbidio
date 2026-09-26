#!/usr/bin/env python3
"""OpenBidIO v0.4 reference verifier.

Usage:  python3 verify.py <file.bidio> [more files...]

Checks the six conformance conditions from SPEC.md section 3:
  1. schema validity          (needs `pip install jsonschema`; WITHOUT it a
                               document is never certified - the schema is
                               where money strings, keys and enums are held)
  2. profile coverage         (declared `conformance` covers features used:
                               sites, episodes, vendors)
  3. referential integrity    (handle uniqueness; site / episode / vendor
                               keys; incentive scoping; variant -> bid_id;
                               site currencies have an fx rate; one prime)
  4. totals recomputation     (pure stdlib - the normative item-level math:
                               vendor / site / document rate resolution,
                               site currencies, discounts, overheads,
                               per-item labour_share, incentive basis and
                               cap, by_site / by_episode / by_vendor blocks)
  5. digest + sub-bids        (the document's sha256 over its canonical
                               form; each nested sub-bid document is itself
                               conformant, its digest matches, and the
                               master's items for that vendor recompute to
                               the sub-bid's gross)
  6. extensions hygiene       (unknown namespaces are fine; non-namespaced
                               extension keys are flagged)

Exit code 0 = conformant, 1 = not, 2 = usage/read error.
The math and the checks are plain functions that RETURN problems, so an
implementer can import this file as a library; only verify() prints.
"""
import hashlib
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

FORMAT_VERSION = "0.4"
TOLERANCE = Decimal("0.005")
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "openbidio.schema.json"
PROFILES = ("M1", "M1-Multisite", "M1-Series", "M1-Vendors", "M1-Full")
DIGEST_ALGORITHM = "sha256"
FILE_EXTENSION = ".bidio"
MEDIA_TYPE = "application/vnd.bidio+json"


def d(x):
    return Decimal(str(x))


def round2(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def version_ok(version) -> bool:
    v = str(version or "")
    return v == FORMAT_VERSION or v.startswith(FORMAT_VERSION + ".")


# ---------------------------------------------------------------------------
# 1. schema
# ---------------------------------------------------------------------------

def check_schema(doc, problems, notes=None):
    """A document is CERTIFIED only through the schema: without jsonschema
    the check is not skipped, it is a problem (0.3 skipped with a warning
    and a file with numbers where money strings belong read CONFORMANT)."""
    try:
        import jsonschema
    except ImportError:
        problems.append("schema: jsonschema is not installed - a document "
                        "cannot be certified without the schema check "
                        "(pip install jsonschema)")
        return
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    for e in errs:
        loc = "/".join(str(p) for p in e.path) or "<root>"
        problems.append(f"schema: {loc}: {e.message}")
    if not errs and notes is not None:
        notes.append("schema: OK")


# ---------------------------------------------------------------------------
# 2. profile
# ---------------------------------------------------------------------------

def _items(doc):
    return list(doc.get("shots", [])) + list(doc.get("line_items", []))


def features_used(doc):
    """Which computational feature axes does this document actually use?
    (multisite, series, vendors)"""
    items = _items(doc)
    multisite = bool(doc.get("sites")) or any(it.get("execution_site") for it in items)
    series = bool(doc.get("episodes")) or any(it.get("episode") for it in items)
    # Declaring the one prime in parties.vendors is not a computational
    # feature (it is the 0.3 parties.vendor with a key); a SECOND vendor,
    # an item tag, a by_vendor block or a sub-bid is.
    vendors = (len((doc.get("parties") or {}).get("vendors") or []) > 1
               or any(it.get("vendor") for it in items)
               or bool((doc.get("totals") or {}).get("by_vendor"))
               or bool(doc.get("subbids")))
    return multisite, series, vendors


def check_profile(doc, problems, notes=None):
    profile = doc.get("conformance")
    if profile not in PROFILES:
        problems.append(f"profile: conformance '{profile}' unknown "
                        f"(expected one of {', '.join(PROFILES)})")
        return
    before = len(problems)
    multisite, series, vendors = features_used(doc)
    n_inc = len(doc.get("incentives", []))
    if multisite and profile not in ("M1-Multisite", "M1-Full"):
        problems.append(
            f"profile: file uses sites/execution_site but declares '{profile}' "
            "(needs M1-Multisite or M1-Full)")
    if series and profile not in ("M1-Series", "M1-Full"):
        problems.append(
            f"profile: file uses episodes but declares '{profile}' "
            "(needs M1-Series or M1-Full)")
    if vendors and profile not in ("M1-Vendors", "M1-Full"):
        problems.append(
            f"profile: file uses vendors/sub-bids but declares '{profile}' "
            "(needs M1-Vendors or M1-Full)")
    if not multisite and n_inc > 1:
        problems.append(
            f"profile: {n_inc} incentives in a single-site file "
            "(single-site profiles allow at most one, document-wide)")
    if len(problems) == before and notes is not None:
        notes.append(f"profile: OK ({profile})")


# ---------------------------------------------------------------------------
# 3. referential integrity
# ---------------------------------------------------------------------------

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


def vendors_declared(doc):
    return list((doc.get("parties") or {}).get("vendors") or [])


def prime_key(doc):
    """The declared prime's key, or None in a file with no vendors block."""
    for v in vendors_declared(doc):
        if v.get("role") == "prime":
            return v.get("key")
    return None


def check_integrity(doc, problems):
    _check_unique([o["key"] for o in doc.get("overheads", [])], "overhead key", problems)
    _check_unique([s["key"] for s in doc.get("sites", [])], "site key", problems)
    _check_unique([e["code"] for e in doc.get("episodes", [])], "episode code", problems)
    _check_unique([s.get("id") for s in doc.get("shots", []) if s.get("id")], "shot id", problems)
    _check_unique([li.get("id") for li in doc.get("line_items", []) if li.get("id")],
                  "line item id", problems)
    _check_unique([dd["key"] for dd in doc.get("departments", [])], "department key", problems)
    _check_unique([t["key"] for t in doc.get("shot_types", [])], "shot type key", problems)
    _check_unique([f["currency"] for f in doc.get("fx_rates", [])], "fx_rates currency", problems)
    _check_unique([v.get("key") for v in vendors_declared(doc)], "vendor key", problems)
    _check_unique([sb.get("vendor") for sb in doc.get("subbids", [])], "sub-bid vendor", problems)

    site_keys = {s["key"] for s in doc.get("sites", [])}
    episode_codes = {e["code"] for e in doc.get("episodes", [])}
    has_sites = bool(doc.get("sites"))
    vendors = vendors_declared(doc)
    vendor_keys = {v.get("key") for v in vendors}
    has_vendors = bool(vendors)

    # vendors: exactly one prime; parties.vendor (the 0.3 party) IS the prime
    if has_vendors:
        primes = [v for v in vendors if v.get("role") == "prime"]
        if len(primes) != 1:
            problems.append(f"integrity: parties.vendors declares {len(primes)} prime "
                            "vendors - exactly one is required")
        legacy = (doc.get("parties") or {}).get("vendor") or {}
        if primes and legacy.get("name") and legacy["name"] != primes[0].get("name"):
            problems.append("integrity: parties.vendor.name "
                            f"'{legacy['name']}' is not the prime's name "
                            f"'{primes[0].get('name')}' - the two are one party")

    # site currencies need an fx rate to the document currency
    fx = {f["currency"] for f in doc.get("fx_rates", [])}
    for s in doc.get("sites", []):
        cur = s.get("currency")
        if cur and cur != doc.get("currency") and cur not in fx:
            problems.append(f"integrity: site '{s['key']}' prices in {cur} but "
                            "fx_rates carries no rate for it")

    for coll, label in (("shots", "shot"), ("line_items", "line item")):
        for it in doc.get(coll, []):
            ident = it.get("code") or it.get("id")
            es = it.get("execution_site")
            if es is not None and es not in site_keys:
                problems.append(f"integrity: {label} {ident}: execution_site '{es}' "
                                "is not a declared site")
            ep = it.get("episode")
            if ep is not None and ep not in episode_codes:
                problems.append(f"integrity: {label} {ident}: episode '{ep}' "
                                "is not a declared episode")
            vk = it.get("vendor")
            if vk is not None:
                if not has_vendors:
                    problems.append(f"integrity: {label} {ident}: carries vendor '{vk}' "
                                    "but the file declares no parties.vendors")
                elif vk not in vendor_keys:
                    problems.append(f"integrity: {label} {ident}: vendor '{vk}' "
                                    "is not a declared vendor")
            for field in ("unit_price", "unit_cost"):
                if it.get(field) is not None and d(it[field]) < 0:
                    problems.append(f"integrity: {label} {ident}: {field} is negative")

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
                        problems.append(f"integrity: incentive[{i}]: scoped site '{k}' "
                                        "is not a declared site")
        elif scope:
            problems.append(f"integrity: incentive[{i}]: carries a 'sites' scope but the "
                            "file declares no sites")
        if inc.get("cap") is not None and d(inc["cap"]) < 0:
            problems.append(f"integrity: incentive[{i}]: cap is negative")

    totals = doc.get("totals") or {}
    for key in (totals.get("by_site") or {}):
        if key not in site_keys:
            problems.append(f"integrity: totals.by_site key '{key}' is not a declared site")
    for key in (totals.get("by_episode") or {}):
        if key not in episode_codes:
            problems.append(f"integrity: totals.by_episode key '{key}' is not a declared episode")
    for key in (totals.get("by_vendor") or {}):
        if not has_vendors:
            problems.append("integrity: totals.by_vendor present but the file declares "
                            "no parties.vendors")
            break
        if key not in vendor_keys:
            problems.append(f"integrity: totals.by_vendor key '{key}' is not a declared vendor")

    for i, sb in enumerate(doc.get("subbids", [])):
        vk = sb.get("vendor")
        if vk not in vendor_keys:
            problems.append(f"integrity: subbids[{i}]: vendor '{vk}' is not a declared vendor")
            continue
        role = next((v.get("role") for v in vendors if v.get("key") == vk), None)
        if role != "sub":
            problems.append(f"integrity: subbids[{i}]: vendor '{vk}' is the {role}, "
                            "not a sub - a sub-bid belongs to a sub vendor")

    if (doc.get("revision") or {}).get("variant") and not doc.get("bid_id"):
        problems.append("integrity: revision.variant requires bid_id "
                        "(scenarios need their bid-family anchor)")


# ---------------------------------------------------------------------------
# 4. the normative math
# ---------------------------------------------------------------------------

def item_costs(doc, problems):
    """Every ENTRY of the computation pool as a dict:
        cost, base, discount_amount, site, episode, vendor, kind
        ('shot' | 'line' | 'overhead'), credit (Decimal)
    This is the normative item-level math from SPEC section 3: rate
    resolution vendor card -> site card -> document card; a site's
    currency converts through fx_rates; discounts per item; overheads as
    document-level percentage lines on the post-discount item base
    (site-neutral, untagged, prime-vendor); incentives by basis, with
    per-item labour_share overrides, then each incentive's cap scaling
    its own contributions pro rata."""
    doc_card = {k: d(v) for k, v in (doc.get("rate_card") or {}).items()}
    site_cards = {s["key"]: {k: d(v) for k, v in s["rate_card"].items()}
                  for s in doc.get("sites", []) if s.get("rate_card")}
    site_currency = {s["key"]: s.get("currency") for s in doc.get("sites", [])
                     if s.get("currency") and s.get("currency") != doc.get("currency")}
    fx = {f["currency"]: d(f["rate"]) for f in doc.get("fx_rates", [])}
    vendor_cards = {v["key"]: {k: d(x) for k, x in v["rate_card"].items()}
                    for v in vendors_declared(doc) if v.get("rate_card")}
    prime = prime_key(doc)
    has_sites = bool(doc.get("sites"))
    incentives = doc.get("incentives", [])

    def contributions(site, ls_override=None, cost=Decimal(0)):
        """[(incentive index, credit)] for one entry, before caps."""
        out = []
        for i, inc in enumerate(incentives):
            scope = inc.get("sites")
            applies = (not has_sites and not scope) or \
                      (site is not None and scope and site in scope)
            if not applies:
                continue
            ls = d(ls_override) if ls_override is not None else d(inc["labour_share"])
            rate = ls * d(inc["labour_rate"])
            if (inc.get("basis") or "cost") == "cost":
                rate += (1 - ls) * d(inc["nonlabour_rate"])
            out.append((i, cost * rate))
        return out

    def fx_factor(site, ident):
        cur = site_currency.get(site) if site else None
        if not cur:
            return Decimal(1)
        if cur not in fx:
            problems.append(f"math: {ident}: site '{site}' prices in {cur} with no fx rate")
            return Decimal(1)
        return fx[cur]

    entries = []
    for shot in doc.get("shots", []):
        ident = f"shot {shot.get('code', shot.get('id'))}"
        qty = d(shot.get("quantity", 1))
        site = shot.get("execution_site")
        vendor = shot.get("vendor") or prime
        if shot.get("unit_price") is not None:
            base = qty * d(shot["unit_price"]) * fx_factor(site, ident)
        else:
            if vendor in vendor_cards:
                card, where, factor = vendor_cards[vendor], f"vendor {vendor}", Decimal(1)
            elif site and site in site_cards:
                card, where, factor = site_cards[site], f"site {site}", fx_factor(site, ident)
            else:
                card, where, factor = doc_card, "document", Decimal(1)
            base = Decimal(0)
            for dept, days in (shot.get("efforts") or {}).items():
                if dept not in card:
                    problems.append(f"math: {ident}: department '{dept}' priced via efforts "
                                    f"but missing from the resolved rate card ({where})")
                    continue
                base += d(days) * card[dept]
            base = base * qty * factor
        disc = d(shot.get("discount", 0))
        cost = base * (1 - disc)
        entries.append({"cost": cost, "base": base, "discount_amount": base - cost,
                        "site": site, "episode": shot.get("episode"), "vendor": vendor,
                        "kind": "shot",
                        "contrib": contributions(site, shot.get("labour_share"), cost)})

    for li in doc.get("line_items", []):
        ident = f"line item {li.get('id')}"
        site = li.get("execution_site")
        base = d(li["quantity"]) * d(li["unit_cost"]) * fx_factor(site, ident)
        disc = d(li.get("discount", 0))
        cost = base * (1 - disc)
        entries.append({"cost": cost, "base": base, "discount_amount": base - cost,
                        "site": site, "episode": li.get("episode"),
                        "vendor": li.get("vendor") or prime, "kind": "line",
                        "contrib": contributions(site, li.get("labour_share"), cost)})

    # Overheads: document-level percentage lines on the post-discount item
    # base. Site-neutral, episode-untagged and vendor-untagged by definition:
    # in a multi-site file no site-scoped incentive touches them, and they
    # appear in document totals only, never in a partition block.
    item_base = sum((e["cost"] for e in entries), Decimal(0))
    for oh in doc.get("overheads", []):
        amount = d(oh["rate"]) * item_base
        entries.append({"cost": amount, "base": amount, "discount_amount": Decimal(0),
                        "site": None, "episode": None, "vendor": None, "kind": "overhead",
                        "contrib": contributions(None, None, amount)})

    # Caps: an incentive's credit over the whole document is at most its cap;
    # when it exceeds, every contribution of THAT incentive scales by the
    # same factor, so partition blocks still reconcile.
    for i, inc in enumerate(incentives):
        if inc.get("cap") is None:
            continue
        total = sum((c for e in entries for j, c in e["contrib"] if j == i), Decimal(0))
        cap = d(inc["cap"])
        if total > cap and total > 0:
            factor = cap / total
            for e in entries:
                e["contrib"] = [(j, c * factor if j == i else c) for j, c in e["contrib"]]
    for e in entries:
        e["credit"] = sum((c for _, c in e["contrib"]), Decimal(0))
    return entries


def rollup(entries):
    shots = sum((e["cost"] for e in entries if e["kind"] == "shot"), Decimal(0))
    lines = sum((e["cost"] for e in entries if e["kind"] == "line"), Decimal(0))
    overhead = sum((e["cost"] for e in entries if e["kind"] == "overhead"), Decimal(0))
    discount = sum((e["discount_amount"] for e in entries), Decimal(0))
    gross = shots + lines + overhead
    credit = sum((e["credit"] for e in entries), Decimal(0))
    out = {"shots_subtotal": shots, "line_items_subtotal": lines, "gross": gross,
           "incentive_credit": credit, "net": gross - credit}
    if overhead:
        out["overhead_total"] = overhead
    if discount:
        out["discount_total"] = discount
    return out


def money_str(x) -> str:
    """The reported form of an amount: rounded half-up to 2 decimals,
    written as a decimal string (SPEC 3, rule 9)."""
    return format(round2(d(x)), "f")


def compare_block(declared, computed, ctx, problems):
    ok = True
    for key, cval in computed.items():
        if key not in declared:
            if key in ("gross", "incentive_credit", "net"):
                problems.append(f"totals: {ctx}: required field '{key}' missing")
                ok = False
            continue
        if abs(d(declared[key]) - round2(cval)) > TOLERANCE:
            problems.append(f"totals: {ctx}: {key} declared {declared[key]} "
                            f"but recomputes to {round2(cval)}")
            ok = False
    return ok


def check_totals(doc, problems, notes=None):
    declared = doc.get("totals") or {}
    entries = item_costs(doc, problems)
    doc_totals = rollup(entries)
    ok = compare_block(declared, doc_totals, "document", problems)

    partitions = (("by_site", "site"), ("by_episode", "episode"), ("by_vendor", "vendor"))
    for block_name, field in partitions:
        for key, block in (declared.get(block_name) or {}).items():
            subset = [e for e in entries if e[field] == key]
            ok &= compare_block(block, rollup(subset), f"{block_name}.{key}", problems)
        # Partition invariant at full precision: tagged blocks + untagged = doc.
        if declared.get(block_name) is not None:
            tagged = [e for e in entries if e[field] is not None]
            untagged = [e for e in entries if e[field] is None]
            if rollup(tagged)["gross"] + rollup(untagged)["gross"] != doc_totals["gross"]:
                problems.append(f"totals: {block_name} partition does not reconcile "
                                "to document gross at full precision")
    if ok and notes is not None:
        notes.append("totals: OK "
                     f"(gross {round2(doc_totals['gross'])}, "
                     f"credit {round2(doc_totals['incentive_credit'])}, "
                     f"net {round2(doc_totals['net'])} {doc.get('currency', '')})")
    return entries


# ---------------------------------------------------------------------------
# 5. digest and sub-bids
# ---------------------------------------------------------------------------

def canonical_bytes(doc) -> bytes:
    """The one serialization the digest is taken over: the document
    WITHOUT its top-level `digest`, keys sorted, no whitespace, UTF-8."""
    body = {k: v for k, v in doc.items() if k != "digest"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def compute_digest(doc) -> dict:
    return {"algorithm": DIGEST_ALGORITHM,
            "value": hashlib.sha256(canonical_bytes(doc)).hexdigest()}


def check_digest(doc, problems, notes=None):
    declared = doc.get("digest")
    if not declared:
        problems.append("digest: missing - every 0.4 document carries its own sha256")
        return
    if declared.get("algorithm") != DIGEST_ALGORITHM:
        problems.append(f"digest: algorithm '{declared.get('algorithm')}' is not "
                        f"{DIGEST_ALGORITHM}")
        return
    expected = compute_digest(doc)["value"]
    if declared.get("value") != expected:
        problems.append(f"digest: declared {str(declared.get('value'))[:16]}... but the "
                        f"canonical form hashes to {expected[:16]}... - the document "
                        "was edited after it was signed, or written by hand")
    elif notes is not None:
        notes.append("digest: OK")


def check_subbids(doc, entries, problems, notes=None):
    """Each sub-bid is a whole document: conformant on its own, its digest
    and identity matching the wrapper, and the master's items tagged to
    that vendor pricing (before the master's own discounts) to the
    sub-document's gross - the prime carries the sub's price, never a
    silently different one."""
    vendors = {v["key"]: v for v in vendors_declared(doc)}
    for i, sb in enumerate(doc.get("subbids", [])):
        ctx = f"subbids[{i}] ({sb.get('vendor')})"
        sub = sb.get("document")
        if not isinstance(sub, dict):
            problems.append(f"{ctx}: no nested document")
            continue
        if not version_ok(sub.get("bidio")):
            problems.append(f"{ctx}: nested document declares bidio '{sub.get('bidio')}' "
                            f"- a {FORMAT_VERSION} master nests {FORMAT_VERSION} sub-bids")
            continue
        inner, inner_notes = [], []
        verify_document(sub, inner, inner_notes)
        for p in inner:
            problems.append(f"{ctx}: {p}")
        if sb.get("bid_id") != sub.get("bid_id"):
            problems.append(f"{ctx}: bid_id '{sb.get('bid_id')}' is not the nested "
                            f"document's '{sub.get('bid_id')}'")
        rev = sb.get("revision") or {}
        sub_rev = sub.get("revision") or {}
        if rev.get("number") != sub_rev.get("number") or rev.get("variant") != sub_rev.get("variant"):
            problems.append(f"{ctx}: revision {rev} is not the nested document's {sub_rev}")
        if (sb.get("digest") or {}).get("value") != (sub.get("digest") or {}).get("value"):
            problems.append(f"{ctx}: digest is not the nested document's digest")
        vendor = vendors.get(sb.get("vendor")) or {}
        sub_prime = next((v for v in vendors_declared(sub) if v.get("role") == "prime"), None)
        sub_name = (sub_prime or (sub.get("parties") or {}).get("vendor") or {}).get("name")
        if vendor.get("name") and sub_name and vendor["name"] != sub_name:
            problems.append(f"{ctx}: the master names the vendor '{vendor['name']}' but the "
                            f"nested document's prime is '{sub_name}'")
        mine = sum((e["base"] for e in entries if e["vendor"] == sb.get("vendor")
                    and e["kind"] != "overhead"), Decimal(0))
        sub_gross = d((sub.get("totals") or {}).get("gross", "0"))
        if abs(round2(mine) - round2(sub_gross)) > TOLERANCE:
            problems.append(f"{ctx}: the master's items for this vendor price to "
                            f"{round2(mine)} before discounts but the sub-bid's gross is "
                            f"{round2(sub_gross)}")
        if not inner and notes is not None:
            notes.append(f"{ctx}: OK (nested {sub.get('conformance')}, gross {round2(sub_gross)})")


# ---------------------------------------------------------------------------
# 6. extensions
# ---------------------------------------------------------------------------

def check_extensions(node, path, problems):
    if isinstance(node, dict):
        ext = node.get("extensions")
        if isinstance(ext, dict):
            for ns in ext:
                if "." not in ns:
                    problems.append(f"extensions at {path or '<root>'}: namespace '{ns}' "
                                    "is not dotted (expected e.g. 'com.yourco')")
        for k, v in node.items():
            if k not in ("extensions", "subbids"):
                check_extensions(v, f"{path}/{k}" if path else k, problems)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            check_extensions(v, f"{path}[{i}]", problems)


# ---------------------------------------------------------------------------
# the whole document
# ---------------------------------------------------------------------------

def verify_document(doc, problems, notes=None):
    """All six conditions on one parsed document; problems and notes are
    appended in place. Returns True when nothing was added to problems."""
    before = len(problems)
    if not version_ok(doc.get("bidio")):
        problems.append(f"version: file declares bidio '{doc.get('bidio')}' - this is a "
                        f"{FORMAT_VERSION} verifier and 0.x readers match major.minor exactly")
        return False
    check_schema(doc, problems, notes)
    check_profile(doc, problems, notes)
    check_integrity(doc, problems)
    entries = check_totals(doc, problems, notes)
    check_digest(doc, problems, notes)
    check_subbids(doc, entries, problems, notes)
    check_extensions(doc, "", problems)
    return len(problems) == before


def verify(path):
    print(f"{path}:")
    try:
        doc = json.loads(Path(path).read_text())
    except Exception as e:
        print(f"  [fail] cannot read/parse: {e}")
        return False
    if not str(path).endswith(FILE_EXTENSION):
        print(f"  [warn] the file is not named {FILE_EXTENSION} - the extension is "
              f"{FILE_EXTENSION}, media type {MEDIA_TYPE}")
    problems, notes = [], []
    ok = verify_document(doc, problems, notes)
    for n in notes:
        print(f"  {n}")
    for p in problems:
        print(f"  [fail] {p}")
    if ok:
        print(f"  CONFORMANT (OpenBidIO v{FORMAT_VERSION}, profile {doc.get('conformance')})")
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    results = [verify(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
