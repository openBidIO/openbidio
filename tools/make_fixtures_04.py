#!/usr/bin/env python3
"""Write the two fixtures that are NEW in 0.4, with their totals computed
by plain arithmetic here (independently of verify.py's math) and then
certified by the verifier before they are written. Re-runnable.

  fixture-006-vendors.bidio       M1-Vendors: a prime and a sub, vendor
                                  tags, by_vendor, the sub's own document
                                  nested as a sub-bid
  fixture-007-currency-cap.bidio  M1-Full: a site pricing in its own
                                  currency through fx_rates, an incentive
                                  with a cap and a labour basis, by_site
                                  and by_vendor together
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify as V  # noqa: E402

FIX = HERE.parent / "fixtures"
STAMP = "2026-09-25T20:00:00Z"


def m(x):
    return format(V.round2(Decimal(str(x))), "f")


def block(shots, lines, credit):
    gross = shots + lines
    return {"shots_subtotal": m(shots), "line_items_subtotal": m(lines), "gross": m(gross),
            "incentive_credit": m(credit), "net": m(gross - credit)}


def finish(doc):
    problems, notes = [], []
    if not V.verify_document(doc, problems, notes):
        raise SystemExit("fixture not conformant:\n  " + "\n  ".join(problems))
    return doc


# ── 006: the sub's own bid, then the master that nests it ──────────────────

def sub_document():
    # Roto House bids two shots to the prime, flat prices, one credit.
    shots = [
        {"id": "sh-030", "code": "030", "description": "Roto: hero over crowd", "type": "cleanup",
         "quantity": 1, "unit_price": "4200"},
        {"id": "sh-040", "code": "040", "description": "Roto + paint: wire removal", "type": "cleanup",
         "quantity": 2, "unit_price": "1550"},
    ]
    # base = 4200 + 2*1550 = 7300; incentive: ls 0.9 * 0.20 + 0.1 * 0 = 0.18
    shots_subtotal = Decimal("7300")
    credit = shots_subtotal * Decimal("0.18")
    doc = {
        "bidio": "0.4",
        "id": "6f1a2d3c-4b5e-4f60-8a7b-9c0d1e2f3a4b",
        "bid_id": "0a9b8c7d-6e5f-4a4b-8c3d-2e1f0a9b8c7d",
        "conformance": "M1",
        "generator": {"name": "openbidio-fixtures", "version": "0.4"},
        "created_at": STAMP, "updated_at": STAMP,
        "project": {"title": "Fixture Show 006", "code": "FIX006", "kind": "feature"},
        "parties": {"vendor": {"name": "Roto House", "country": "IN"},
                    "vendors": [{"key": "prime", "name": "Roto House", "role": "prime", "country": "IN"}],
                    "client": {"name": "Example VFX Co", "country": "CA"}},
        "currency": "CAD",
        "shots": shots,
        "incentives": [{"jurisdiction": "IN-MH", "program": "Example state credit",
                        "labour_share": 0.9, "labour_rate": 0.20, "nonlabour_rate": 0.0}],
        "revision": {"number": 1, "locked": True, "supersedes": None},
        "award": {"status": "submitted", "submitted_at": STAMP},
        "totals": block(shots_subtotal, Decimal(0), credit),
    }
    doc["digest"] = V.compute_digest(doc)
    return finish(doc)


def master_006(sub):
    # The prime prices its own shots off its card and carries the sub's
    # two shots at the sub's prices (unit_price), tagged to the sub.
    card = {"comp": "800", "paint": "550", "matchmove": "600"}
    shots = [
        {"id": "sh-010", "code": "010", "description": "City extension", "type": "environment",
         "quantity": 1, "efforts": {"comp": 4, "matchmove": 2}},
        {"id": "sh-020", "code": "020", "description": "Screen inserts", "type": "cleanup",
         "quantity": 3, "efforts": {"comp": 1.5, "paint": 0.5}},
        {"id": "sh-030", "code": "030", "description": "Roto: hero over crowd", "type": "cleanup",
         "quantity": 1, "unit_price": "4200", "vendor": "roto-house"},
        {"id": "sh-040", "code": "040", "description": "Roto + paint: wire removal", "type": "cleanup",
         "quantity": 2, "unit_price": "1550", "vendor": "roto-house", "discount": 0.05},
    ]
    lines = [
        {"id": "li-1", "label": "VFX supervision", "kind": "supervision", "quantity": 4,
         "unit": "day", "unit_cost": "1200"},
    ]
    # prime shots: 010 = 4*800 + 2*600 = 4400; 020 = 3 * (1.5*800 + 0.5*550) = 3*1475 = 4425
    prime_shots = Decimal("4400") + Decimal("4425")
    # sub shots at the master: 030 = 4200; 040 = 2*1550 = 3100, discounted 5% -> 2945
    sub_base = Decimal("4200") + Decimal("3100")
    sub_cost = Decimal("4200") + Decimal("2945")
    prime_lines = Decimal("4800")
    # one document-wide incentive on the prime's Quebec work: ls 0.65, 0.25 / 0.20
    rate = Decimal("0.65") * Decimal("0.25") + Decimal("0.35") * Decimal("0.20")  # 0.2325
    credit_prime = (prime_shots + prime_lines) * rate
    credit_sub = sub_cost * rate
    totals = block(prime_shots + sub_cost, prime_lines, credit_prime + credit_sub)
    totals["discount_total"] = m(sub_base - sub_cost)
    totals["by_vendor"] = {
        "prime": block(prime_shots, prime_lines, credit_prime),
        "roto-house": block(sub_cost, Decimal(0), credit_sub),
    }
    doc = {
        "bidio": "0.4",
        "id": "1b2c3d4e-5f60-4a7b-8c9d-0e1f2a3b4c5d",
        "bid_id": "2c3d4e5f-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
        "conformance": "M1-Vendors",
        "generator": {"name": "openbidio-fixtures", "version": "0.4"},
        "created_at": STAMP, "updated_at": STAMP,
        "provenance": {"generated_at": STAMP, "generated_by": "tools/make_fixtures_04.py",
                       "source": {"system": "openbidio-fixtures", "ref": "006"}},
        "project": {"title": "Fixture Show 006", "code": "FIX006", "client": "Example Pictures",
                    "kind": "feature"},
        "parties": {
            "vendor": {"name": "Example VFX Co", "country": "CA"},
            "client": {"name": "Example Pictures"},
            "vendors": [
                {"key": "prime", "name": "Example VFX Co", "role": "prime", "country": "CA"},
                {"key": "roto-house", "name": "Roto House", "role": "sub", "country": "IN"},
            ],
        },
        "currency": "CAD",
        "departments": [{"key": "comp", "label": "Compositing"}, {"key": "paint", "label": "Paint"},
                        {"key": "matchmove", "label": "Matchmove"}],
        "rate_card": card,
        "shots": shots,
        "line_items": lines,
        "incentives": [{"jurisdiction": "CA-QC", "program": "QPSTC",
                        "labour_share": 0.65, "labour_rate": 0.25, "nonlabour_rate": 0.20}],
        "subbids": [{"vendor": "roto-house", "bid_id": sub["bid_id"], "revision": {"number": 1},
                     "digest": sub["digest"], "document": sub}],
        "revision": {"number": 2, "locked": False, "supersedes": None},
        "award": {"status": "draft"},
        "totals": totals,
    }
    doc["digest"] = V.compute_digest(doc)
    return finish(doc)


# ── 007: a site in its own currency, a capped labour-basis incentive ───────

def master_007():
    # Montreal prices in CAD (the document currency); London prices in GBP
    # off its own card, converted at 1.72 CAD per GBP. The UK credit is on
    # labour only and capped at 3000 CAD. The prime does both sites; a sub
    # takes one London shot.
    shots = [
        {"id": "sh-010", "code": "010", "description": "Set extension", "type": "environment",
         "quantity": 1, "execution_site": "mtl", "efforts": {"comp": 5, "dmp": 4}},
        {"id": "sh-020", "code": "020", "description": "Creature reveal", "type": "creature",
         "quantity": 1, "execution_site": "lon", "efforts": {"anim": 10, "comp": 6}},
        {"id": "sh-030", "code": "030", "description": "Crowd tiles", "type": "creature",
         "quantity": 2, "execution_site": "lon", "unit_price": "2500", "vendor": "crowd-co",
         "labour_share": 1.0},
    ]
    lines = [
        {"id": "li-1", "label": "Data wrangling", "kind": "data", "quantity": 10, "unit": "day",
         "unit_cost": "400", "execution_site": "mtl", "labour_share": 1.0},
    ]
    fx = Decimal("1.72")
    # mtl: 010 = 5*900 + 4*850 = 7900 CAD; li-1 = 4000 CAD
    mtl_shots, mtl_lines = Decimal("7900"), Decimal("4000")
    # lon: 020 = (10*1100 + 6*1000) GBP = 17000 GBP = 29240 CAD; 030 = 2*2500 GBP = 5000 GBP = 8600 CAD
    lon_prime = Decimal("17000") * fx
    lon_sub = Decimal("5000") * fx
    # QC credit on mtl entries: basis cost, ls 0.65 (li-1 overrides to 1.0), 0.25 / 0.20
    qc_010 = mtl_shots * (Decimal("0.65") * Decimal("0.25") + Decimal("0.35") * Decimal("0.20"))
    qc_li = mtl_lines * (Decimal("1.0") * Decimal("0.25"))
    # UK credit on lon entries: basis labour, ls 0.80 (030 overrides to 1.0), labour_rate 0.25,
    # uncapped = 29240*0.8*0.25 + 8600*1.0*0.25 = 5848 + 2150 = 7998 > cap 3000 -> scale 3000/7998
    uk_020_raw = lon_prime * Decimal("0.80") * Decimal("0.25")
    uk_030_raw = lon_sub * Decimal("1.0") * Decimal("0.25")
    cap = Decimal("3000")
    factor = cap / (uk_020_raw + uk_030_raw)
    uk_020, uk_030 = uk_020_raw * factor, uk_030_raw * factor
    shots_subtotal = mtl_shots + lon_prime + lon_sub
    credit = qc_010 + qc_li + uk_020 + uk_030
    totals = block(shots_subtotal, mtl_lines, credit)
    totals["by_site"] = {
        "mtl": block(mtl_shots, mtl_lines, qc_010 + qc_li),
        "lon": block(lon_prime + lon_sub, Decimal(0), uk_020 + uk_030),
    }
    totals["by_vendor"] = {
        "prime": block(mtl_shots + lon_prime, mtl_lines, qc_010 + qc_li + uk_020),
        "crowd-co": block(lon_sub, Decimal(0), uk_030),
    }
    doc = {
        "bidio": "0.4",
        "id": "3d4e5f60-7a8b-4c9d-8e0f-1a2b3c4d5e6f",
        "bid_id": "4e5f6a7b-8c9d-4e0f-9a1b-2c3d4e5f6a7b",
        "conformance": "M1-Full",
        "generator": {"name": "openbidio-fixtures", "version": "0.4"},
        "created_at": STAMP, "updated_at": STAMP,
        "provenance": {"generated_at": STAMP, "generated_by": "tools/make_fixtures_04.py",
                       "source": {"system": "openbidio-fixtures", "ref": "007"}},
        "project": {"title": "Fixture Show 007", "code": "FIX007", "kind": "feature"},
        "parties": {
            "vendor": {"name": "Example VFX Co", "country": "CA"},
            "vendors": [
                {"key": "prime", "name": "Example VFX Co", "role": "prime", "country": "CA"},
                {"key": "crowd-co", "name": "Crowd Co", "role": "sub", "country": "GB"},
            ],
        },
        "currency": "CAD",
        "fx_rates": [{"currency": "GBP", "rate": 1.72}],
        "sites": [
            {"key": "mtl", "label": "Montreal", "jurisdiction": "CA-QC",
             "rate_card": {"comp": "900", "dmp": "850"}},
            {"key": "lon", "label": "London", "jurisdiction": "GB-ENG", "currency": "GBP",
             "rate_card": {"comp": "1000", "anim": "1100"}},
        ],
        "departments": [{"key": "comp", "label": "Compositing"}, {"key": "dmp", "label": "Matte painting"},
                        {"key": "anim", "label": "Animation"}],
        "shots": shots,
        "line_items": lines,
        "incentives": [
            {"jurisdiction": "CA-QC", "program": "QPSTC", "sites": ["mtl"],
             "labour_share": 0.65, "labour_rate": 0.25, "nonlabour_rate": 0.20},
            {"jurisdiction": "GB-ENG", "program": "Example UK relief", "sites": ["lon"],
             "labour_share": 0.80, "labour_rate": 0.25, "nonlabour_rate": 0.0,
             "basis": "labour", "cap": "3000"},
        ],
        "revision": {"number": 1, "locked": False, "supersedes": None},
        "award": {"status": "draft"},
        "totals": totals,
    }
    doc["digest"] = V.compute_digest(doc)
    return finish(doc)


def main():
    sub = sub_document()
    for name, doc in (("fixture-006-vendors.bidio", master_006(sub)),
                      ("fixture-007-currency-cap.bidio", master_007())):
        (FIX / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {name}: gross {doc['totals']['gross']} credit {doc['totals']['incentive_credit']} "
              f"net {doc['totals']['net']} {doc['currency']}")


if __name__ == "__main__":
    main()
