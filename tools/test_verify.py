"""The 0.5 verifier, pinned: every fixture certifies; the things 0.4 and 0.5
added refuse in words when they are wrong; a 0.3 or 0.4 file upgrades to a
certified 0.5 file. Run: .venv/bin/python -m pytest tools/"""
import copy
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import upgrade as U  # noqa: E402
import verify as V  # noqa: E402

FIX = HERE.parent / "fixtures"
FIXTURES = sorted(FIX.glob("*.bidio"))


def _load(name):
    return json.loads((FIX / name).read_text())


def _problems(doc):
    problems, notes = [], []
    V.verify_document(doc, problems, notes)
    return problems


def _resign(doc):
    doc.pop("digest", None)
    doc["digest"] = V.compute_digest(doc)
    return doc


def test_there_are_nine_fixtures_and_all_are_bidio_files():
    assert len(FIXTURES) == 9
    assert not list(FIX.glob("*.bid.json")), "0.3 files retired; 0.4+ files are .bidio"
    assert all(_load(p.name)["bidio"] == V.FORMAT_VERSION for p in FIXTURES), "every fixture speaks 0.5"


@pytest.mark.parametrize("path", FIXTURES, ids=[p.name for p in FIXTURES])
def test_every_fixture_is_conformant(path):
    doc = json.loads(path.read_text())
    problems, notes = [], []
    assert V.verify_document(doc, problems, notes), problems
    assert any(n.startswith("schema: OK") for n in notes), "certified through the schema"
    assert any(n.startswith("digest: OK") for n in notes)


def test_without_jsonschema_a_document_is_not_certified(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_jsonschema(name, *a, **k):
        if name == "jsonschema":
            raise ImportError("gone")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_jsonschema)
    problems = _problems(_load("fixture-001.bidio"))
    assert any("cannot be certified" in p for p in problems)


def test_money_is_a_string_never_a_number():
    doc = _load("fixture-001.bidio")
    doc["rate_card"]["comp"] = 800
    _resign(doc)
    problems = _problems(doc)
    assert any(p.startswith("schema: rate_card/comp") for p in problems), problems


def test_a_tampered_document_fails_its_digest():
    doc = _load("fixture-005-discount-overhead.bidio")
    doc["shots"][0]["description"] = "edited after signing"
    problems = _problems(doc)
    assert any(p.startswith("digest: declared") for p in problems)
    assert not any(p.startswith("totals") for p in problems), "the numbers still add up; only the seal broke"


def test_the_canonical_form_ignores_key_order_and_whitespace():
    doc = _load("fixture-001.bidio")
    shuffled = json.loads(json.dumps(dict(reversed(list(doc.items())))))
    assert V.compute_digest(shuffled) == doc["digest"]


def test_vendors_exactly_one_prime_and_declared_tags():
    doc = _load("fixture-006-vendors.bidio")
    two = copy.deepcopy(doc)
    two["parties"]["vendors"][1]["role"] = "prime"
    assert any("exactly one is required" in p for p in _problems(_resign(two)))
    undeclared = copy.deepcopy(doc)
    undeclared["shots"][0]["vendor"] = "nobody"
    assert any("vendor 'nobody' is not a declared vendor" in p for p in _problems(_resign(undeclared)))
    legacy = copy.deepcopy(doc)
    legacy["parties"]["vendor"]["name"] = "Someone Else"
    assert any("the two are one party" in p for p in _problems(_resign(legacy)))


def test_a_prime_only_declaration_needs_no_vendors_profile():
    doc = _load("fixture-001.bidio")
    assert doc["conformance"] == "M1" and len(doc["parties"]["vendors"]) == 1
    assert _problems(doc) == []
    tagged = copy.deepcopy(doc)
    tagged["shots"][0]["vendor"] = "prime"
    problems = _problems(_resign(tagged))
    assert any("needs M1-Vendors or M1-Full" in p for p in problems), "a tag IS the feature"


def test_by_vendor_reconciles_and_a_wrong_block_is_named():
    doc = _load("fixture-006-vendors.bidio")
    doc["totals"]["by_vendor"]["roto-house"]["gross"] = "1.00"
    problems = _problems(_resign(doc))
    assert any(p.startswith("totals: by_vendor.roto-house: gross declared 1.00") for p in problems)


def test_a_subbid_must_price_the_same_as_the_masters_items_for_that_vendor():
    doc = _load("fixture-006-vendors.bidio")
    doc["shots"][2]["unit_price"] = "4300"     # the master silently repriced the sub
    # keep the master's totals honest so only the sub-bid rule fires
    entries = V.item_costs(doc, [])
    roll = V.rollup(entries)
    for k in ("shots_subtotal", "gross", "incentive_credit", "net", "discount_total"):
        doc["totals"][k] = V.money_str(roll[k])
    rh = V.rollup([e for e in entries if e["vendor"] == "roto-house"])
    for k in ("shots_subtotal", "gross", "incentive_credit", "net"):
        doc["totals"]["by_vendor"]["roto-house"][k] = V.money_str(rh[k])
    problems = _problems(_resign(doc))
    assert any("price to 7400.00 before discounts but the sub-bid's gross is 7300.00" in p
               for p in problems), problems


def test_a_subbid_nested_document_is_verified_on_its_own():
    doc = _load("fixture-006-vendors.bidio")
    doc["subbids"][0]["document"]["totals"]["net"] = "1.00"
    problems = _problems(_resign(doc))
    assert any(p.startswith("subbids[0] (roto-house): totals: document: net declared 1.00") for p in problems)
    assert any("digest is not the nested document's digest" in p or
               p.startswith("subbids[0] (roto-house): digest: declared") for p in problems)


def test_a_subbid_belongs_to_a_sub_not_the_prime():
    doc = _load("fixture-006-vendors.bidio")
    doc["subbids"][0]["vendor"] = "prime"
    problems = _problems(_resign(doc))
    assert any("is the prime, not a sub" in p for p in problems)


def test_a_site_currency_converts_through_fx_and_needs_a_rate():
    doc = _load("fixture-007-currency-cap.bidio")
    assert doc["sites"][1]["currency"] == "GBP" and doc["fx_rates"][0]["rate"] == 1.72
    entries = V.item_costs(doc, [])
    lon020 = next(e for e in entries if e["kind"] == "shot" and e["site"] == "lon" and e["vendor"] == "prime")
    assert lon020["base"] == V.d("17000") * V.d("1.72")
    norate = copy.deepcopy(doc)
    norate["fx_rates"] = []
    problems = _problems(_resign(norate))
    assert any("prices in GBP but fx_rates carries no rate" in p for p in problems)


def test_a_capped_labour_basis_incentive_scales_its_own_credits_pro_rata():
    doc = _load("fixture-007-currency-cap.bidio")
    entries = V.item_costs(doc, [])
    uk = [e for e in entries if e["site"] == "lon"]
    uk_credit = sum((e["credit"] for e in uk), V.d(0))
    assert V.round2(uk_credit) == V.d("3000.00"), "capped at 3000 over the document"
    ratio = [e["credit"] / e["cost"] for e in uk]
    # 020 at ls 0.80 and 030 at ls 1.0: the scale factor is the same, the shares differ
    assert V.round2(ratio[0] / V.d("0.8")) == V.round2(ratio[1] / V.d("1.0"))
    mtl = [e for e in entries if e["site"] == "mtl"]
    assert all(e["credit"] > 0 for e in mtl), "the Quebec credit is untouched by the UK cap"
    # basis labour: the nonlabour term is dropped even when a rate is declared
    lab = copy.deepcopy(doc)
    lab["incentives"][1]["nonlabour_rate"] = 0.5
    lab["incentives"][1].pop("cap")
    lab_entries = V.item_costs(_resign(lab), [])
    raw = copy.deepcopy(doc)
    raw["incentives"][1].pop("cap")
    raw_entries = V.item_costs(_resign(raw), [])
    assert [e["credit"] for e in lab_entries] == [e["credit"] for e in raw_entries]


def test_jurisdiction_is_iso_3166():
    doc = _load("fixture-007-currency-cap.bidio")
    doc["sites"][0]["jurisdiction"] = "Quebec"
    problems = _problems(_resign(doc))
    assert any(p.startswith("schema: sites/0/jurisdiction") for p in problems)


def test_upgrade_turns_a_0_3_file_into_a_certified_0_5_file():
    old = {
        "bidio": "0.3", "id": "be78b485-26fd-404c-b31a-f2873dabe19e", "conformance": "M1",
        "project": {"title": "Old"}, "parties": {"vendor": {"name": "Old Co", "country": "CA"}},
        "currency": "CAD", "rate_card": {"comp": 800, "fx": 950.5},
        "shots": [{"id": "s1", "code": "010", "quantity": 1, "efforts": {"comp": 2, "fx": 0.5}},
                  {"id": "s2", "code": "020", "quantity": 2, "unit_price": 100.1}],
        "line_items": [{"id": "l1", "label": "Sup", "quantity": 1, "unit_cost": 1200}],
        "totals": {"shots_subtotal": 2275.45, "line_items_subtotal": 1200, "gross": 3475.45,
                   "incentive_credit": 0, "net": 3475.45},
    }
    new = U.upgrade(old)
    assert new["bidio"] == "0.5" and new["rate_card"] == {"comp": "800", "fx": "950.5"}
    assert new["shots"][1]["unit_price"] == "100.1" and new["line_items"][0]["unit_cost"] == "1200"
    assert new["totals"]["gross"] == "3475.45" and new["totals"]["incentive_credit"] == "0"
    assert new["parties"]["vendors"] == [{"key": "prime", "name": "Old Co", "role": "prime", "country": "CA"}]
    assert new["parties"]["vendor"] == {"name": "Old Co", "country": "CA"}, "the 0.3 party stays"
    assert new["digest"] == V.compute_digest(new) and new["provenance"]["source"]["ref"].endswith(old["id"])
    assert _problems(new) == []
    with pytest.raises(ValueError, match="takes a 0.3 or 0.4 document"):
        U.upgrade(new)


def test_upgrade_names_the_file_bidio():
    assert U.out_path(pathlib.Path("/x/FIX_v01.bid.json"), None) == pathlib.Path("/x/FIX_v01.bidio")
    assert U.out_path(pathlib.Path("/x/FIX_v01.bidio"), None) == pathlib.Path("/x/FIX_v01.bidio"), \
        "a .bidio source is not renamed .bidio.bidio (main refuses to overwrite it without --in-place)"
    assert U.out_path(pathlib.Path("/x/a.json"), pathlib.Path("/y")) == pathlib.Path("/y/a.bidio")


def test_the_schema_id_resolves_to_the_hosted_copy_and_the_two_are_one():
    root = json.loads((HERE.parent / "openbidio.schema.json").read_text())
    hosted = json.loads((HERE.parent / "schema" / "0.5" / "openbidio.schema.json").read_text())
    assert root == hosted, "the hosted copy under schema/0.5/ is the root file, byte for byte in meaning"
    assert root["$id"] == "https://openbidio.github.io/openbidio/schema/0.5/openbidio.schema.json"
    older = json.loads((HERE.parent / "schema" / "0.4" / "openbidio.schema.json").read_text())
    assert older["$id"].endswith("/schema/0.4/openbidio.schema.json"), "0.4 stays hosted, frozen"


# ── 0.5: shot assumptions, and a response names what it answers ─────────────

def test_assumptions_are_text_on_a_shot_and_change_no_total():
    doc = _load("fixture-008-vendor-response.bidio")
    assert "Clean plate" in doc["shots"][1]["assumptions"]
    bare = copy.deepcopy(doc)
    for sh in bare["shots"]:
        sh.pop("assumptions", None)
    assert _problems(_resign(bare)) == [], "the totals do not move without them"
    doc["shots"][0]["assumptions"] = 7
    assert any("assumptions" in p for p in _problems(_resign(doc))), "text, never a number"


def test_a_response_names_the_bid_it_answers_never_its_own():
    doc = _load("fixture-008-vendor-response.bidio")
    assert doc["in_response_to"]["bid_id"] == _load("fixture-006-vendors.bidio")["bid_id"]
    doc["in_response_to"]["bid_id"] = doc["bid_id"]
    assert any("revision (revision.supersedes), not a response" in p for p in _problems(_resign(doc)))
    doc = _load("fixture-008-vendor-response.bidio")
    del doc["in_response_to"]["revision"]
    assert any("revision" in p for p in _problems(_resign(doc))), "a response names the revision it answers"


def test_a_nested_response_answers_the_master_it_is_nested_in():
    master = _load("fixture-006-vendors.bidio")
    assert master["subbids"][0]["document"]["in_response_to"]["bid_id"] == master["bid_id"]
    sub = master["subbids"][0]["document"]
    sub["in_response_to"]["bid_id"] = "11111111-2222-4333-8444-555555555555"
    _resign(sub)
    master["subbids"][0]["digest"] = dict(sub["digest"])
    assert any("answers bid '11111111" in p for p in _problems(_resign(master)))


def test_a_0_5_verifier_refuses_a_0_4_file_cleanly_and_upgrade_carries_it():
    old = _load("fixture-006-vendors.bidio")
    old["bidio"] = "0.4"
    for sb in old["subbids"]:
        sb["document"]["bidio"] = "0.4"
        sb["document"].pop("in_response_to", None)
        for sh in sb["document"]["shots"]:
            sh.pop("assumptions", None)
        _resign(sb["document"])
        sb["digest"] = dict(sb["document"]["digest"])
    _resign(old)
    assert any("0.x readers match major.minor exactly" in p for p in _problems(old))
    new = U.upgrade(old)
    assert new["bidio"] == "0.5" and new["subbids"][0]["document"]["bidio"] == "0.5"
    assert new["subbids"][0]["digest"] == new["subbids"][0]["document"]["digest"], "the wrapper takes the new seal"
    assert new["totals"] == old["totals"], "0.4 -> 0.5 moves no money"
    assert _problems(new) == []
