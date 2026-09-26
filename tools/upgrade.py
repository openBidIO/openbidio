#!/usr/bin/env python3
"""Upgrade an OpenBidIO 0.3 document to 0.4.

Usage:  python3 upgrade.py <file.bid.json> [more files...] [--out DIR]

What 0.4 changed that a 0.3 file must be rewritten for (CHANGELOG 0.4):
  * money is a decimal STRING (rate cards, unit_price, unit_cost, totals),
    never a binary float - "800" and "8623.5", written from the exact
    decimal the 0.3 number denotes (Decimal(str(x))), never re-rounded;
  * parties.vendors[] declares the vendors: the 0.3 parties.vendor becomes
    the one prime ({key: "prime", name, role: "prime"}) and stays in place;
  * every document carries a digest (sha256 over its canonical form) and
    may carry provenance - the upgrade writes both and names itself;
  * the file is <name>.bidio (the 0.3 <name>.bid.json is not overwritten).

Nothing else moves: 0.3 discounts, overheads, labour_share, sites and
episodes are unchanged in 0.4. The upgraded file is verified with the 0.4
verifier before it is written; a 0.3 file that was not conformant stays a
0.3 file, with the problems printed.
"""
import argparse
import datetime as _dt
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify as V  # noqa: E402

MONEY_TOTAL_KEYS = ("shots_subtotal", "line_items_subtotal", "discount_total",
                    "overhead_total", "gross", "incentive_credit", "net")


def money(x):
    """The decimal the 0.3 number denotes, as a string. 800 -> "800",
    8623.5 -> "8623.5", 0.1 -> "0.1" (never 0.1000000000000000055...)."""
    if x is None:
        return None
    return format(Decimal(str(x)).normalize(), "f")


def _card(card):
    return {k: money(v) for k, v in (card or {}).items()} if card is not None else None


def upgrade(doc: dict, *, generated_by: str = "openbidio tools/upgrade.py 0.3->0.4") -> dict:
    v = str(doc.get("bidio", ""))
    if not (v == "0.3" or v.startswith("0.3.")):
        raise ValueError(f"upgrade.py takes a 0.3 document; this one declares '{v}'")
    out = json.loads(json.dumps(doc))  # a copy; the caller's object is untouched
    out["bidio"] = "0.4"
    if out.get("rate_card") is not None:
        out["rate_card"] = _card(out["rate_card"])
    for s in out.get("sites", []):
        if s.get("rate_card") is not None:
            s["rate_card"] = _card(s["rate_card"])
    for sh in out.get("shots", []):
        if "unit_price" in sh:
            sh["unit_price"] = money(sh["unit_price"])
    for li in out.get("line_items", []):
        li["unit_cost"] = money(li["unit_cost"])
    totals = out.get("totals") or {}
    for k in MONEY_TOTAL_KEYS:
        if k in totals:
            totals[k] = money(totals[k])
    for block_name in ("by_site", "by_episode"):
        for block in (totals.get(block_name) or {}).values():
            for k in MONEY_TOTAL_KEYS:
                if k in block:
                    block[k] = money(block[k])
    parties = out.setdefault("parties", {})
    if "vendors" not in parties:
        legacy = parties.get("vendor") or {}
        prime = {"key": "prime", "name": legacy.get("name") or "Vendor", "role": "prime"}
        if legacy.get("country"):
            prime["country"] = legacy["country"]
        parties["vendors"] = [prime]
        if not legacy.get("name"):
            parties["vendor"] = {"name": prime["name"]}
    out["provenance"] = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
        .isoformat().replace("+00:00", "Z"),
        "generated_by": generated_by,
        "source": {"system": "openbidio", "ref": f"0.3 document {doc.get('id')}"},
    }
    out.pop("digest", None)
    out["digest"] = V.compute_digest(out)
    return out


def out_path(src: Path, out_dir: Path | None) -> Path:
    name = src.name
    for suffix in (".bid.json", ".json"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return (out_dir or src.parent) / f"{name}{V.FILE_EXTENSION}"


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", help="directory for the .bidio files (default: beside the source)")
    args = ap.parse_args(argv)
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    ok_all = True
    for f in args.files:
        src = Path(f)
        try:
            doc = json.loads(src.read_text())
            new = upgrade(doc)
        except Exception as e:
            print(f"{src}: [fail] {e}")
            ok_all = False
            continue
        problems, notes = [], []
        if not V.verify_document(new, problems, notes):
            print(f"{src}: [fail] the upgraded document is not conformant:")
            for p in problems:
                print(f"  {p}")
            ok_all = False
            continue
        dst = out_path(src, out_dir)
        dst.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
        print(f"{src} -> {dst}: OK (digest {new['digest']['value'][:16]}...)")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
