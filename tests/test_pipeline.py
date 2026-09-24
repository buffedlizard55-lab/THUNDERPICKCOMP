"""Offline replay of actual *partial* captured responses + synthetic edge cases.

Synthetic markets below exist ONLY in test memory. They must never be published
as real tournament matches, first-party quotes or leaderboard entries.
"""
import copy
import gzip
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from scripts import collect as c
from scripts import competition as comp
from scripts import restore as rest
from scripts import validate as v

ROOT = Path(__file__).resolve().parent.parent
TEAMS = json.loads((ROOT / "data" / "teams.json").read_text())
NOW = datetime(2026, 9, 24, 17, 10, tzinfo=timezone.utc)


class FakeFetcher:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, *, text=False):
        self.calls.append(url)
        if url not in self.mapping:
            raise c.SourceError("synthetic test: no response for " + url)
        value = self.mapping[url]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)


def synthetic_quote(team, price, size, mid, now=NOW, venue="Kalshi"):
    """Completely fabricated controlled test input, NOT a real-market claim."""
    updated = c.stamp(now - timedelta(seconds=25))
    identity = "|".join([venue, mid, team, c.stamp(now), price, size, updated])
    return {
        "quote_id": c.sha(identity), "venue": venue,
        "event_key": "kalshi:TEST-OUTRIGHT", "market_id": mid,
        "market_type": "tournament winner", "market_title": team + " wins championship",
        "selection": team, "raw_price": price, "ask_size": size,
        "price_unit": "USD per $1 Yes contract", "source_updated_utc": updated,
        "observed_utc": c.stamp(now), "source_url": "https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=TEST-OUTRIGHT",
        "event_url": "https://api.elections.kalshi.com/trade-api/v2/markets/" + mid,
        "resolution_rule": "Synthetic test rule: venue pays $1 if the named team wins, $0 otherwise.",
        "quote_status": "fresh", "note": "SYNTHETIC TEST ONLY",
    }


def synthetic_docs(now=NOW):
    obs = c.empty()
    obs["mode"] = "live"
    obs["last_attempt_utc"] = c.stamp(now)
    obs["last_completed_utc"] = c.stamp(now)
    obs["events"] = [{
        "key": "kalshi:TEST-OUTRIGHT", "venue": "Kalshi", "id": "TEST-OUTRIGHT",
        "title": "Thunderpick World Championship 2026 Winner", "stage": "tournament-unspecified",
        "status": "open", "first_seen_utc": c.stamp(now), "last_seen_utc": c.stamp(now),
        "source_url": "https://api.elections.kalshi.com/trade-api/v2/events/TEST-OUTRIGHT",
        "review_url": "https://api.elections.kalshi.com/trade-api/v2/events/TEST-OUTRIGHT",
    }]
    obs["quotes"] = [synthetic_quote("FURIA", "0.5000", "100.00", "TEST-FURIA", now),
                     synthetic_quote("Falcons", "0.6000", "100.00", "TEST-FALCONS", now)]
    ledger = json.loads((ROOT / "data" / "ledger.json").read_text())
    return obs, ledger


class MemoryResponse:
    """Synthetic, in-memory HTTP response; never used as a real price receipt."""

    status = 200

    def __init__(self, body: bytes, encoding: str = ""):
        self.buffer = io.BytesIO(body)
        self.headers = {"Content-Encoding": encoding} if encoding else {}

    def read(self, size: int) -> bytes:
        return self.buffer.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.buffer.close()


class CollectorTests(unittest.TestCase):
    def test_liquipedia_http_accepts_and_boundedly_decodes_required_gzip(self):
        body = b'{"parse":{"wikitext":{"*":"Thunderpick World Championship 2026"}}}'
        with patch.object(c, "urlopen", return_value=MemoryResponse(gzip.compress(body), "gzip")) as open_url:
            decoded = c.Fetcher().get(c.LIQUIPEDIA_API)
        self.assertEqual(decoded["parse"]["wikitext"]["*"], "Thunderpick World Championship 2026")
        req = open_url.call_args.args[0]
        self.assertEqual(req.get_header("Accept-encoding"), "gzip")
        self.assertIn("/issues", req.get_header("User-agent"))
        with patch.object(c, "urlopen", return_value=MemoryResponse(body)):
            self.assertEqual(c.Fetcher().get(c.LIQUIPEDIA_API), decoded)
        with patch.object(c, "urlopen", return_value=MemoryResponse(b"not gzip", "gzip")):
            with self.assertRaisesRegex(c.SourceError, "invalid gzip"):
                c.Fetcher().get(c.LIQUIPEDIA_API)
        with patch.object(c, "urlopen", return_value=MemoryResponse(gzip.compress(b"X" * 4_000_001), "gzip")):
            with self.assertRaisesRegex(c.SourceError, "decompressed response exceeds 4MB"):
                c.Fetcher().get(c.LIQUIPEDIA_API)
        with patch.object(c, "urlopen", return_value=MemoryResponse(body, "br")):
            with self.assertRaisesRegex(c.SourceError, "unsupported content encoding"):
                c.Fetcher().get(c.LIQUIPEDIA_API)

    def test_partial_fixture_replay_is_sourced_but_never_bets(self):
        doc = c.collect(c.empty(), c.FixtureFetcher(), NOW, TEAMS, "offline-replay")
        self.assertEqual(len(doc["checks"]), 7)
        self.assertEqual({r["team_id"]: r["rank"] for r in doc["vrs_history"][0]["teams"]},
                         {"falcons": 3, "legacy": 6, "furia": 7, "9z": 9,
                          "aurora": 12, "betboom": 15, "parivision": 18, "virtuspro": 40})
        self.assertEqual(doc["mode"], "offline-replay")
        self.assertEqual(doc["events"][0]["stage"], "qualifier/series")
        self.assertEqual(doc["events"][0]["status"], "closed")
        self.assertEqual(doc["quotes"], [])
        self.assertEqual(doc["fixtures"], [])
        self.assertTrue(all(x["status"] == "partial" for x in doc["checks"]))
        _, ledger = synthetic_docs()
        self.assertEqual(comp.apply_outright(ledger, doc, NOW), [])
        again = c.collect(doc, c.FixtureFetcher(), NOW, TEAMS, "offline-replay")
        self.assertEqual(again["vrs_history"], doc["vrs_history"])
        self.assertEqual(again["events"], doc["events"])

    def test_vrs_partial_missing_finalist_is_not_unranked(self):
        sample = (c.FIXTURES / "vrs_global_2026_08_03.md").read_text()
        with self.assertRaisesRegex(c.SourceError, "missing finalist"):
            c.parse_vrs(sample, "2026-08-03", TEAMS)
        with self.assertRaisesRegex(c.SourceError, "date"):
            c.parse_vrs(sample, "2026-09-07", TEAMS)

    def test_vrs_ignores_nonfinalist_roster_rows_but_rejects_bad_finalists(self):
        sample = (c.FIXTURES / "vrs_global_2026_09_07.md").read_text()
        self.assertIn("Just Players         | h1te, sm3t, Something, sstiNiX", sample)
        self.assertIn("Just Players         | em0k1d, rexxie, Something, spirit, sstiNiX", sample)
        self.assertEqual(len(c.parse_vrs(sample, "2026-09-07", TEAMS)), 8)
        falcons = next(line for line in sample.splitlines() if "| Falcons " in line)
        with self.assertRaisesRegex(c.SourceError, "duplicate or malformed finalist"):
            c.parse_vrs(sample + "\n" + falcons, "2026-09-07", TEAMS)
        with self.assertRaisesRegex(c.SourceError, "duplicate or malformed finalist"):
            c.parse_vrs(sample.replace("karrigan, kyousuke, m0NESY, NiKo, TeSeS", "karrigan, kyousuke, m0NESY, NiKo"), "2026-09-07", TEAMS)
        with self.assertRaisesRegex(c.SourceError, "malformed Valve VRS row"):
            c.parse_vrs(sample.replace("|   1881 | Falcons", "|   N/A | Falcons"), "2026-09-07", TEAMS)

    def test_verified_qualifier_market_not_usable_for_backfill(self):
        fixture = json.loads((c.FIXTURES / "polymarket_event_twc26_qualifier_closed.json").read_text())
        self.assertTrue(c.twc_event(fixture[0]))
        self.assertEqual(fixture[0]["markets"][0]["outcomePrices"], '["0", "1"]')
        self.assertFalse(comp.eligible_outright(
            synthetic_quote("FURIA", "0.5", "100", "TEST-FURIA"),
            {"status": "closed", "title": fixture[0]["title"], "stage": "qualifier/series"}, NOW))
        self.assertFalse(c.twc_event({"title": "Thunderpick World Championship 2025", "ticker": "cs2-2025"}))
        self.assertFalse(c.twc_event({"title": "Thunderpick World Championship 2025", "ticker": "cs2-2026"}))

    def test_future_fixture_requires_two_teams_utc_date_and_hltv_id(self):
        prefix = "{{DISPLAYTITLE:Thunderpick World Championship 2026}}\n==Results==\n"
        template = "|{{Match\n|opponent1={{TeamOpponent|FURIA}}|opponent2={{TeamOpponent|Team Falcons}}\n|date=2026-10-15T14:00:00Z\n|map1={{Map|map=}}\n|hltv=2388888\n}}\n"
        rows = c.parse_liquipedia_fixtures(prefix + template, TEAMS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "HLTV-2388888")
        self.assertEqual(rows[0]["status"], "scheduled-unconfirmed")
        self.assertEqual(c.parse_liquipedia_fixtures(prefix + template.replace("Z", ""), TEAMS), [])
        self.assertEqual(c.parse_liquipedia_fixtures(prefix + template.replace("2388888", ""), TEAMS), [])
        with self.assertRaisesRegex(c.SourceError, "repeated"):
            c.parse_liquipedia_fixtures(prefix + template + template, TEAMS)

    def test_quote_is_first_party_ask_only_and_bad_time_rejected(self):
        doc = c.empty()
        q = synthetic_quote("FURIA", "0.43", "120", "TEST-ASK")
        q.pop("quote_id"); q.pop("quote_status"); q.pop("note"); q.pop("observed_utc")
        c.quote(doc, q, NOW)
        self.assertEqual(doc["quotes"][0]["raw_price"], "0.43")
        self.assertEqual(doc["quotes"][0]["quote_status"], "fresh")
        with self.assertRaisesRegex(c.SourceError, "between 0 and 1"):
            c.quote(doc, {**q, "raw_price": "1.0000"}, NOW)
        with self.assertRaisesRegex(c.SourceError, "future"):
            c.quote(doc, {**q, "source_updated_utc": c.stamp(NOW + timedelta(minutes=2))}, NOW)
        stale = c.quote(doc, {**q, "source_updated_utc": c.stamp(NOW - timedelta(hours=2))}, NOW)
        self.assertIsNone(stale)
        self.assertEqual(doc["quotes"][-1]["quote_status"], "indicative-only")

    def test_book_market_mismatch_rolls_back_all_new_quotes(self):
        # Fake a relevant TWC event that has two outcome tokens. First book is
        # good, second is malicious/incorrect: no partial market is published.
        e = {"id": "999TEST", "slug": "thunderpick-world-championship-2026-test",
             "title": "Thunderpick World Championship 2026 Finals", "closed": False,
             "markets": [{"id": "test-market", "active": True, "closed": False,
                          "question": "Tournament Winner", "description": "Synthetic settlement rule (tests only)",
                          "conditionId": "0xGOOD", "outcomes": '["FURIA", "Falcons"]',
                          "clobTokenIds": '["T1", "T2"]'}]}
        b1 = "https://clob.polymarket.com/book?" + urlencode({"token_id": "T1"})
        b2 = "https://clob.polymarket.com/book?" + urlencode({"token_id": "T2"})
        mapping = {c.POLY_ACTIVE: {"events": [e], "pagination": {"hasMore": False, "totalResults": 1}},
                   c.POLY_TAG: [], c.POLY_HISTORY: [],
                   b1: {"market": "0xGOOD", "asset_id": "T1", "timestamp": str(int(NOW.timestamp() * 1000)),
                        "asks": [{"price": "0.43", "size": "200"}]},
                   b2: {"market": "0xWRONG", "asset_id": "T2", "timestamp": str(int(NOW.timestamp() * 1000)),
                        "asks": [{"price": "0.55", "size": "200"}]}}
        doc = c.empty()
        c.collect_poly(doc, FakeFetcher(mapping), NOW, "live")
        self.assertEqual(doc["quotes"], [])
        self.assertEqual(doc["events"], [])
        self.assertEqual(doc["checks"][0]["status"], "error")
        self.assertTrue(any(x["code"] == "source_error" for x in doc["alerts"]))

    def test_source_error_never_becomes_a_zero_hit(self):
        mapping = {c.POLY_ACTIVE: c.SourceError("test 429"), c.POLY_TAG: [], c.POLY_HISTORY: []}
        doc = c.empty()
        c.collect_poly(doc, FakeFetcher(mapping), NOW, "live")
        self.assertEqual(doc["checks"][0]["status"], "error")
        self.assertNotIn("0 TWC", doc["checks"][0]["detail"])
        self.assertEqual(doc["checks"][1]["status"], "ok")

    def test_kalshi_pair_is_candidate_only_rules_confirm(self):
        event_url = c.KALSHI + "/events?" + urlencode({"series_ticker": "KXCS2GAME", "status": "open", "limit": c.KALSHI_LIMIT})
        market_url = c.KALSHI + "/markets?" + urlencode({"event_ticker": "TEST-TWC", "limit": 200})
        mapping = {event_url: {"cursor": "", "events": [{"title": "FURIA vs. Falcons", "event_ticker": "TEST-TWC"}]},
                   market_url: {"cursor": "", "markets": [{"ticker": "TEST-TWC-FURIA",
                       "rules_primary": "If FURIA wins a different tournament 2026, Yes wins",
                       "rules_secondary": "Synthetic other-event example"}]},
                   c.KALSHI + "/events?" + urlencode({"series_ticker": "KXCS2", "status": "open", "limit": c.KALSHI_LIMIT}): {"cursor": "", "events": []}}
        doc = c.empty()
        c.collect_kalshi(doc, FakeFetcher(mapping), NOW, TEAMS, "live")
        self.assertEqual(doc["events"], [])
        self.assertEqual(doc["quotes"], [])
        self.assertEqual(doc["checks"][0]["status"], "ok")
        self.assertIn("0 TWC", doc["checks"][0]["detail"])


class CompetitionTests(unittest.TestCase):
    def test_two_atomic_forward_only_paper_decisions_with_exact_receipts(self):
        obs, ledger = synthetic_docs()
        placed = comp.apply_outright(ledger, obs, NOW)
        self.assertEqual(len(placed), 2)
        self.assertEqual({e["selection"] for e in placed}, {"FURIA", "Falcons"})
        self.assertEqual([e["stake"] for e in placed], ["50.00", "50.00"])
        self.assertEqual(placed[0]["price_source"]["raw_price"], "0.5000")
        self.assertEqual(placed[0]["price_source"]["quote_id"], obs["quotes"][0]["quote_id"])
        self.assertTrue(all(e["settlement"]["result"] == "pending" and e["payout"] is None for e in placed))
        self.assertEqual(comp.apply_outright(ledger, obs, NOW), [])  # idempotent
        v.ERRORS.clear()
        v.check_ledger(ledger, {"sim_champ_correlation"}, {"TWC26-FINALS-CHAMPION"}, obs)
        self.assertEqual(v.ERRORS, [], v.ERRORS)

    def test_missing_size_old_market_or_offline_never_papers_one_side(self):
        obs, ledger = synthetic_docs()
        obs["quotes"][1]["ask_size"] = "10"
        self.assertEqual(comp.apply_outright(ledger, obs, NOW), [])
        obs["quotes"][1]["ask_size"] = "100"
        obs["mode"] = "offline-replay"
        self.assertEqual(comp.apply_outright(ledger, obs, NOW), [])
        obs["mode"] = "live"
        obs["quotes"][0]["source_updated_utc"] = c.stamp(NOW - timedelta(hours=2))
        self.assertEqual(comp.apply_outright(ledger, obs, NOW), [])
        obs["quotes"][0]["source_updated_utc"] = c.stamp(NOW - timedelta(seconds=25))
        self.assertEqual(comp.apply_outright(ledger, obs, datetime(2026, 10, 14, tzinfo=timezone.utc)), [])

    def test_a_finals_match_winner_must_never_be_papered_as_champion(self):
        obs, ledger = synthetic_docs()
        obs["events"][0]["title"] = "Counter-Strike: FURIA vs Falcons (BO3) - Thunderpick World Championship 2026 Finals"
        obs["quotes"][0]["venue"] = "Polymarket (international)"
        obs["quotes"][0]["market_title"] = "FURIA vs Falcons - Match Winner"
        obs["quotes"][1]["venue"] = "Polymarket (international)"
        obs["quotes"][1]["market_title"] = "FURIA vs Falcons - Match Winner"
        self.assertEqual(comp.apply_outright(ledger, obs, NOW), [])
        self.assertEqual(ledger["entries"], [])
        # An altered ledger pointing at a matchup cannot pass validation either.
        original, forged = synthetic_docs()
        comp.apply_outright(forged, original, NOW)
        original["events"][0]["title"] = obs["events"][0]["title"]
        v.ERRORS.clear()
        v.check_ledger(forged, {"sim_champ_correlation"}, {"TWC26-FINALS-CHAMPION"}, original)
        self.assertTrue(any("cannot target a match" in msg for msg in v.ERRORS))

    def test_invalid_ledger_money_and_reference_fail(self):
        obs, ledger = synthetic_docs()
        comp.apply_outright(ledger, obs, NOW)
        ledger["entries"][0]["price_source"]["raw_price"] = "NaN"
        v.ERRORS.clear()
        v.check_ledger(ledger, {"sim_champ_correlation"}, {"TWC26-FINALS-CHAMPION"}, obs)
        self.assertTrue(any("finite decimal" in e or "source raw_price differs" in e for e in v.ERRORS))
        ledger["entries"][0]["price_source"]["raw_price"] = "0.5000"
        ledger["entries"][0]["profit"] = "999.00"  # pending must not have P/L
        v.ERRORS.clear()
        v.check_ledger(ledger, {"sim_champ_correlation"}, {"TWC26-FINALS-CHAMPION"}, obs)
        self.assertTrue(any("pending payout/profit" in e for e in v.ERRORS))

    def test_gross_payout_math_and_partial_is_not_void(self):
        stake, price = Decimal("50.00"), Decimal("0.73")
        self.assertEqual(v.gross_payout(stake, price, "win"), Decimal("68.49"))
        self.assertEqual(v.gross_payout(stake, price, "loss"), Decimal("0.00"))
        self.assertEqual(v.gross_payout(stake, price, "void"), Decimal("50.00"))
        self.assertEqual(v.gross_payout(stake, price, "partial", Decimal("0.50")), Decimal("34.25"))
        with self.assertRaises(ValueError):
            v.gross_payout(stake, price, "partial", None)

    def test_published_history_must_cover_earlier_receipts(self):
        obs, ledger = synthetic_docs()
        comp.apply_outright(ledger, obs, NOW)
        current = c.empty()
        current["quotes"] = [obs["quotes"][0]]
        published = copy.deepcopy(current)
        published["quotes"].append(obs["quotes"][1])
        published["last_attempt_utc"] = c.stamp(NOW)
        self.assertEqual(len(rest.restore_observations(current, published)["quotes"]), 2)
        published["quotes"][0]["raw_price"] = "0.99"
        with self.assertRaisesRegex(c.SourceError, "rewrote"):
            rest.restore_observations(current, published)
        original_ledger = {"meta": {"simulated": True}, "entries": [ledger["entries"][0]]}
        newer_ledger = {"meta": {"simulated": True}, "entries": []}
        with self.assertRaisesRegex(c.SourceError, "missing/rewrote"):
            rest.restore_ledger(original_ledger, newer_ledger)

    def test_legacy_pages_seed_cannot_erase_last_successful_journal(self):
        seed = json.loads((ROOT / "data" / "observations.json").read_text())
        seed_ledger = json.loads((ROOT / "data" / "ledger.json").read_text())
        # Synthetic decision lives only in memory, not in published data.
        paper, later_ledger = synthetic_docs()
        comp.apply_outright(later_ledger, paper, NOW)
        checkpoint = copy.deepcopy(seed)
        checkpoint["mode"] = "live"
        checkpoint["last_attempt_utc"] = c.stamp(NOW + timedelta(minutes=1))
        checkpoint["events"] += paper["events"]
        checkpoint["quotes"] += paper["quotes"]
        selected, selected_ledger, source = rest.choose_history(
            seed, seed_ledger, seed, seed_ledger, checkpoint, later_ledger, require_live=True)
        self.assertEqual((source, len(selected["quotes"]), len(selected_ledger["entries"])),
                         ("Actions checkpoint", 2, 2))
        self.assertEqual(rest.choose_history(seed, seed_ledger, None, None,
                                             checkpoint, later_ledger, require_live=True)[2],
                         "Actions checkpoint")
        with self.assertRaisesRegex(c.SourceError, "reverted to offline"):
            rest.choose_history(seed, seed_ledger, seed, seed_ledger, None, None, require_live=True)
        with self.assertRaisesRegex(c.SourceError, "no published or successful"):
            rest.choose_history(seed, seed_ledger, None, None, None, None, require_live=True)
        # A newer Pages journal covering both prior quotes and positions wins.
        newer = copy.deepcopy(checkpoint)
        newer["last_attempt_utc"] = c.stamp(NOW + timedelta(minutes=2))
        newer["quotes"].append(synthetic_quote("FURIA", "0.49", "100", "TEST-NEW"))
        self.assertEqual(rest.choose_history(seed, seed_ledger, newer, later_ledger,
                                             checkpoint, later_ledger, require_live=True)[2], "Pages")
        # A newer timestamp with a missing receipt/decision is *not* acceptable.
        newer["quotes"].pop()
        newer["quotes"].pop()
        with self.assertRaisesRegex(c.SourceError, "missing/rewrote"):
            rest.choose_history(seed, seed_ledger, newer, later_ledger,
                                checkpoint, later_ledger, require_live=True)
        damaged_ledger = copy.deepcopy(later_ledger)
        damaged_ledger["entries"].pop()
        with self.assertRaisesRegex(c.SourceError, "missing/rewrote"):
            rest.choose_history(seed, seed_ledger, checkpoint, damaged_ledger,
                                checkpoint, later_ledger, require_live=True)

    def test_actions_artifact_path_layout_requires_exactly_one_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            payload = {"entries": []}
            (root / "data" / "ledger.json").write_text(json.dumps(payload))
            self.assertEqual(rest.artifact_json(root, "ledger.json"), payload)
            (root / "ledger.json").write_text(json.dumps(payload))
            with self.assertRaisesRegex(c.SourceError, "exactly one"):
                rest.artifact_json(root, "ledger.json")

    def test_restore_cli_uses_checkpoint_when_pages_reverts_to_offline_seed(self):
        seed = json.loads((ROOT / "data" / "observations.json").read_text())
        seed_ledger = json.loads((ROOT / "data" / "ledger.json").read_text())
        newer = copy.deepcopy(seed)
        newer["mode"] = "live"
        newer["last_attempt_utc"] = c.stamp(NOW + timedelta(minutes=1))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkpoint = root / "artifact"
            checkpoint.mkdir()
            observation = root / "observations.json"
            ledger = root / "ledger.json"
            observation.write_text(json.dumps(seed))
            ledger.write_text(json.dumps(seed_ledger))
            (checkpoint / "observations.json").write_text(json.dumps(newer))
            (checkpoint / "ledger.json").write_text(json.dumps(seed_ledger))
            with patch.object(rest, "OUTPUT", observation), patch.object(rest, "LEDGER", ledger):
                self.assertEqual(rest.main(["--observations", str(observation),
                                            "--ledger", str(ledger), "--artifact-dir", str(checkpoint),
                                            "--require-live-history"]), 0)
            self.assertEqual(json.loads(observation.read_text())["mode"], "live")
            self.assertEqual(json.loads(ledger.read_text())["entries"], [])


if __name__ == "__main__":
    unittest.main()
