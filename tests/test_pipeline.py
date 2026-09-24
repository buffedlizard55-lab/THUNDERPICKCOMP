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


def synthetic_ledger():
    """Stable test-only baseline, independent of the workflow's mutable live files."""
    return {"meta": {"simulated": True, "currency": "synthetic test units",
                     "settlement_policy": "Synthetic fixtures never settle.",
                     "last_updated_utc": c.stamp(NOW)}, "entries": []}


def offline_seed():
    """Partial recorded fixture replay; not the dynamically restored site journal."""
    return c.collect(c.empty(), c.FixtureFetcher(), NOW, TEAMS, "offline-replay")


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
    return obs, synthetic_ledger()


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
        self.assertEqual(len(doc["checks"]), 9)
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

    def test_live_poly_team_pass_runs_one_bounded_search_per_finalist_form(self):
        # Regression: TEAM_NAMES was referenced but never defined, which crashed
        # the live collector (offline replay never executes this branch).
        from urllib.parse import urlencode as uq
        doc = c.empty()
        doc["events"].append({"key": "polymarket:1", "status": "closed", "title": "old qualifier"})
        mapping = {c.POLY_TEAM_SEARCH + uq({"q": name}): {"events": [], "pagination": {"totalResults": 0}}
                   for name in c.TEAM_NAMES}
        fetcher = FakeFetcher(mapping)
        c.collect_poly_teams(doc, fetcher, NOW, "live")
        row = next(k for k in doc["checks"] if k["source"] == "polymarket_teams")
        self.assertEqual(row["status"], "partial")
        self.assertEqual(len(fetcher.calls), len(c.TEAM_NAMES))
        self.assertGreaterEqual(len(c.TEAM_NAMES), 8)  # at least one query per finalist
        self.assertLessEqual(len(c.TEAM_NAMES), 13)  # stays bounded

    def test_live_poly_team_pass_skips_when_keyed_search_found_open_event(self):
        doc = c.empty()
        doc["events"].append({"key": "polymarket:2", "status": "open", "title": "TWC finals",
                              "last_seen_utc": c.stamp(NOW)})
        doc["last_attempt_utc"] = c.stamp(NOW)
        fetcher = FakeFetcher({})
        c.collect_poly_teams(doc, fetcher, NOW, "live")
        row = next(k for k in doc["checks"] if k["source"] == "polymarket_teams")
        self.assertEqual(row["status"], "ok")
        self.assertIn("skipped", row["detail"])
        self.assertEqual(fetcher.calls, [])


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
        seed = offline_seed()
        seed_ledger = synthetic_ledger()
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
        seed = offline_seed()
        seed_ledger = synthetic_ledger()
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


# ---------------------------------------------------------------------------
# Match pipeline: HLTV + Liquipedia cross-check and pre-start depth gates.
# ---------------------------------------------------------------------------

def match_quote(team, price, size, mid, now=NOW, event_key="kalshi:KXCS2GAME-TEST"):
    """Synthetic match-winner ask; exists only in test memory."""
    q = synthetic_quote(team, price, size, mid, now)
    q["event_key"] = event_key
    q["market_type"] = "match winner"
    q["market_title"] = "FURIA vs. Team Falcons"
    return q


def synthetic_match_obs(now=NOW, status="scheduled-confirmed", scheduled=None, pair=("furia", "falcons")):
    """One double-sourced fixture plus a fresh pre-start two-sided book."""
    obs = c.empty()
    obs["mode"] = "live"
    obs["last_attempt_utc"] = c.stamp(now)
    obs["last_completed_utc"] = c.stamp(now)
    scheduled = scheduled or (now + timedelta(hours=2))
    obs["fixtures"] = [{
        "id": "HLTV-2399999", "hltv_id": "2399999", "team_a": pair[0], "team_b": pair[1],
        "scheduled_utc": c.stamp(scheduled), "group": "A", "stage_label": "groups",
        "finished": False, "derived_winner": None, "series_score": None, "map_scores": [],
        "source_url": "https://www.hltv.org/matches/2399999",
        "liquipedia_url": "https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026",
        "observed_utc": c.stamp(now), "status": status,
        "result_status": "none", "hltv_verified_utc": c.stamp(now),
        "note": "synthetic test fixture",
    }]
    obs["events"] = [{
        "key": "kalshi:KXCS2GAME-TEST", "venue": "Kalshi", "id": "KXCS2GAME-TEST",
        "title": "FURIA vs. Team Falcons", "stage": "tournament-unspecified", "status": "open",
        "first_seen_utc": c.stamp(now), "last_seen_utc": c.stamp(now),
        "source_url": "https://api.elections.kalshi.com/trade-api/v2/events/KXCS2GAME-TEST",
        "review_url": "https://api.elections.kalshi.com/trade-api/v2/events/KXCS2GAME-TEST",
    }]
    obs["quotes"] = [match_quote("FURIA", "0.5500", "200.00", "KXCS2GAME-TEST-FURIA", now),
                     match_quote("Team Falcons", "0.6000", "200.00", "KXCS2GAME-TEST-FAL", now)]
    return obs, synthetic_ledger()


STRATEGIES = json.loads((ROOT / "data" / "strategies.json").read_text())


class MatchStrategyTests(unittest.TestCase):
    def setUp(self):
        self.ranks = comp.team_ranks(TEAMS)
        self.assertEqual(self.ranks["falcons"], 4)
        self.assertEqual(self.ranks["furia"], 8)

    def entries_for(self, obs, ledger, username):
        return [e for e in ledger["entries"] if e["username"] == username]

    def test_offline_or_unconfirmed_or_conflict_never_papers(self):
        for status, mode in (("scheduled-unconfirmed", "live"), ("scheduled-confirmed", "offline-replay"), ("conflict", "live")):
            obs, ledger = synthetic_match_obs(status=status)
            if mode != "live":
                obs["mode"] = mode
            placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
            self.assertEqual(placed, [], msg=status + "/" + mode)

    def test_pre_start_double_sourced_fixture_papers_favorite_and_underdog(self):
        obs, ledger = synthetic_match_obs()
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        users = {e["username"] for e in placed}
        self.assertIn("sim_favorite_backer", users)
        self.assertIn("sim_underdog_hunter", users)
        fav = self.entries_for(obs, ledger, "sim_favorite_backer")[0]
        under = self.entries_for(obs, ledger, "sim_underdog_hunter")[0]
        # Falcons are the Sep-16 favorite (rank 4 < 8) and must back Falcons.
        self.assertEqual(fav["selection"], "Team Falcons")
        self.assertEqual(under["selection"], "FURIA")
        self.assertEqual(fav["match_id"], "HLTV-2399999")
        self.assertEqual(fav["stake"], "25.00")
        self.assertEqual(under["stake"], "15.00")
        self.assertTrue(all(e["settlement"]["result"] == "pending" for e in placed))
        self.assertTrue(all(e["fixture"]["crosscheck"]["fixture_status"] == "scheduled-confirmed" for e in placed))

    def test_insufficient_pre_start_depth_never_papers(self):
        obs, ledger = synthetic_match_obs()
        for q in obs["quotes"]:
            q["ask_size"] = "1.00"  # far below stake/price contracts
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        self.assertEqual(placed, [])

    def test_quote_at_or_after_start_never_papers(self):
        obs, ledger = synthetic_match_obs()
        late = NOW + timedelta(hours=3)  # fixture scheduled NOW+2h
        obs["last_attempt_utc"] = obs["last_completed_utc"] = c.stamp(late)
        for q in obs["quotes"]:
            q["observed_utc"] = c.stamp(late)
            q["source_updated_utc"] = c.stamp(late - timedelta(seconds=25))
        placed = comp.apply_match_strategies(ledger, obs, late, TEAMS, STRATEGIES)
        self.assertEqual(placed, [])

    def test_ambiguous_pair_association_refuses(self):
        obs, ledger = synthetic_match_obs()
        extra = dict(obs["fixtures"][0])
        extra["id"] = "HLTV-2399998"
        extra["hltv_id"] = "2399998"
        obs["fixtures"].append(extra)  # second fixture, same pair, inside 12h
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        self.assertEqual(placed, [])

    def test_contrarian_bets_only_big_underdog_prices(self):
        obs, ledger = synthetic_match_obs()
        for q in obs["quotes"]:
            if q["selection"] == "FURIA":
                q["raw_price"] = "0.3000"  # decimal 3.33 for the underdog
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        contra = self.entries_for(obs, ledger, "sim_contrarian_cap")
        self.assertEqual(len(contra), 1)
        self.assertEqual(contra[0]["selection"], "FURIA")
        self.assertEqual(contra[0]["stake"], "10.00")
        # priced favorite-side-only books never trigger the contrarian
        obs2, ledger2 = synthetic_match_obs()
        for q in obs2["quotes"]:
            q["raw_price"] = "0.6500"
        self.assertEqual(comp.apply_match_strategies(ledger2, obs2, NOW, TEAMS, STRATEGIES),
                         [e for e in comp.apply_match_strategies(synthetic_ledger(), obs2, NOW, TEAMS, STRATEGIES)] or [])
        self.assertEqual(self.entries_for(obs2, ledger2, "sim_contrarian_cap"), [])

    def test_value_engine_bets_only_below_heuristic_fair_minus_edge(self):
        obs, ledger = synthetic_match_obs()
        for q in obs["quotes"]:
            q["raw_price"] = "0.4200" if q["selection"] == "FURIA" else "0.8000"
        # favorite Falcons fair = min(85, 50+2.5*4)=60 -> implied 80 not <= 52; underdog fair 40 -> implied 42 not <= 32
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        self.assertEqual(self.entries_for(obs, ledger, "sim_vrs_value"), [])
        for q in obs["quotes"]:
            if q["selection"] == "FURIA":
                q["raw_price"] = "0.3100"  # implied 31 <= 40-8 -> value bet on FURIA
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        value = self.entries_for(obs, ledger, "sim_vrs_value")
        self.assertEqual(len(value), 1)
        self.assertEqual(value[0]["selection"], "FURIA")

    def test_cache_chaos_bets_only_group_openers(self):
        obs, ledger = synthetic_match_obs()
        placed = comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        chaos = self.entries_for(obs, ledger, "sim_cache_chaos")
        self.assertEqual(len(chaos), 1)  # single fixture = its group's opener
        self.assertEqual(chaos[0]["selection"], "FURIA")  # worse rank side
        # a second fixture in the same group at the same time is not an opener
        obs2, ledger2 = synthetic_match_obs()
        extra = dict(obs2["fixtures"][0]); extra["id"] = "HLTV-2399997"; extra["hltv_id"] = "2399997"
        extra["scheduled_utc"] = c.stamp(NOW + timedelta(hours=1))
        obs2["fixtures"].append(extra)
        placed = comp.apply_match_strategies(ledger2, obs2, NOW, TEAMS, STRATEGIES)
        # Two same-pair fixtures inside the association window: association is
        # ambiguous, so nothing at all may be papered.
        self.assertEqual(placed, [])

    def test_bankroll_budget_caps_pending_stakes(self):
        obs, ledger = synthetic_match_obs()
        # Prefill the favorite backer with 40 × 25-unit pending entries (1000 units).
        for i in range(40):
            ledger["entries"].append({
                "entry_id": f"SIM-prefill-{i}", "username": "sim_favorite_backer",
                "match_id": "TWC26-FINALS-CHAMPION", "event_key": "kalshi:X", "market": "m",
                "selection": f"FURIA-{i}", "decimal_odds": "2", "stake": "25.00",
                "placed_utc": c.stamp(NOW), "simulated": True, "fill_policy": "SIMULATED test",
                "price_source": {}, "settlement": {"result": "pending", "rule": "r"},
                "payout": None, "profit": None,
            })
        comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        # 40 × 25 units are already pending; one more 25 would exceed the cap.
        self.assertEqual(len(self.entries_for(obs, ledger, "sim_favorite_backer")), 40)


class HltvCrosscheckTests(unittest.TestCase):
    REAL_PAGE = (ROOT / "tests" / "fixtures" / "hltv_match_2397860.html").read_text()

    def test_parser_reads_only_verified_markers(self):
        page = c.hltv_match_url("2397860") and __import__("scripts.hltv", fromlist=["parse_hltv_match"]).parse_hltv_match(self.REAL_PAGE, "2397860")
        self.assertEqual(page["status"], "finished")
        self.assertEqual((page["score_team1"], page["score_team2"]), (2, 0))
        self.assertEqual(page["date_utc"], "2026-09-09")
        self.assertEqual(page["team1"], "4914/3dmax")
        self.assertEqual(page["team2"], "13518/acend")

    def test_parser_rejects_wrong_id_and_unidentifiable_pages(self):
        import scripts.hltv as h
        with self.assertRaisesRegex(h.SourceError, "match id"):
            h.parse_hltv_match(self.REAL_PAGE, "1111111")
        with self.assertRaisesRegex(h.SourceError, "title"):
            h.parse_hltv_match("<title>HLTV.org</title>", "2397860")

    def test_liquipedia_real_dates_and_scores_parse(self):
        wikitext = ("==Results==\n===Group Stage===\n===={{HiddenSort|Group A}}====\n"
                    "|{{Match\n|opponent1={{TeamOpponent|3dmax}}|opponent2={{TeamOpponent|acend}}\n"
                    "|date=October 15, 2026 - 13:15 {{Abbr/CEST}} |finished=true\n"
                    "|map1={{Map|map=Cache|finished=true\n|t1firstside=ct|t1t=3|t1ct=10|t2t=2|t2ct=0\n|stats=237518|vod=}}\n"
                    "|map2={{Map|map=Inferno|finished=true\n|t1firstside=t|t1t=9|t1ct=4|t2t=3|t2ct=1\n|stats=237542|vod=}}\n"
                    "|map3={{Map|map=Ancient|finished=skip}}\n|hltv=2397860\n}}\n")
        # 3DMAX/Acend are not finalists: the strict parser must skip this pair.
        self.assertEqual(c.parse_liquipedia_fixtures(wikitext, TEAMS), [])
        wikitext_finals = wikitext.replace("3dmax", "FURIA").replace("acend", "Team Falcons")
        rows = c.parse_liquipedia_fixtures(wikitext_finals, TEAMS)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["scheduled_utc"], "2026-10-15T11:15:00Z")
        self.assertEqual(row["group"], "A")
        self.assertTrue(row["finished"])
        self.assertEqual(row["map_scores"], [[13, 2], [13, 4]])
        self.assertEqual(row["derived_winner"], "team_a")
        self.assertEqual(row["series_score"], [2, 0])

    def test_liquipedia_date_without_timezone_is_never_guessed(self):
        base = ("==Results==\n|{{Match\n|opponent1={{TeamOpponent|FURIA}}|opponent2={{TeamOpponent|Team Falcons}}\n"
                "|date=__DATE__\n|hltv=2397860\n}}\n")
        self.assertEqual(c.parse_liquipedia_fixtures(base.replace("__DATE__", "October 15, 2026 - 13:15"), TEAMS), [])
        self.assertEqual(c.parse_liquipedia_fixtures(base.replace("__DATE__", "October 15, 2026"), TEAMS), [])
        self.assertEqual(c.parse_liquipedia_fixtures(base.replace("__DATE__", "October 15, 2026 - 13:15 {{Abbr/CST}}"), TEAMS), [])
        rows = c.parse_liquipedia_fixtures(base.replace("__DATE__", "October 14, 2026 - 13:00 {{Abbr/CEST}}"), TEAMS)
        self.assertEqual(rows[0]["scheduled_utc"], "2026-10-14T11:00:00Z")

    def test_crosscheck_confirms_then_confirms_result(self):
        import scripts.hltv as h
        obs, ledger = synthetic_match_obs(status="scheduled-unconfirmed")
        # Build the HLTV page for the synthetic fixture: teams FURIA vs Team Falcons, finished 2:0 on the fixture date.
        page = (self.REAL_PAGE.replace("3DMAX", "FURIA").replace("/team/4914/3dmax", "/team/4274/furia")
                .replace("Acend", "Team Falcons").replace("/team/13518/acend", "/team/10568/team-falcons")
                .replace("9th of September 2026", "24th of September 2026")
                .replace("2397860", "2399999"))
        fetcher = FakeFetcher({h.hltv_match_url("2399999"): page})
        c.collect_hltv_crosscheck(obs, fetcher, NOW, TEAMS, "live")
        fixture = obs["fixtures"][0]
        self.assertEqual(fixture["status"], "scheduled-confirmed")
        self.assertEqual([x for x in obs["checks"] if x["source"] == "hltv_crosscheck"][0]["status"], "ok")
        # Now finish it on both sides and require agreement before confirming.
        fixture["finished"] = True
        fixture["derived_winner"] = "team_a"
        fixture["series_score"] = [2, 0]
        fixture["map_scores"] = [[13, 2], [13, 4]]
        fixture["result_status"] = "liquipedia-derived-unconfirmed"
        obs2 = copy.deepcopy(obs)
        obs2["fixtures"][0]["status"] = "scheduled-confirmed"
        c.collect_hltv_crosscheck(obs2, fetcher, NOW, TEAMS, "live")
        self.assertEqual(obs2["fixtures"][0]["result_status"], "confirmed")
        self.assertEqual(obs2["fixtures"][0]["result"]["winner"], "furia")
        self.assertEqual(obs2["fixtures"][0]["result"]["sources"][0].startswith("https://liquipedia.net"), True)

    def test_crosscheck_team_or_date_conflict_blocks_paper(self):
        import scripts.hltv as h
        obs, _ = synthetic_match_obs(status="scheduled-unconfirmed")
        wrong_teams = (self.REAL_PAGE.replace("3DMAX", "Aurora").replace("/team/4914/3dmax", "/team/11039/aurora")
                       .replace("Acend", "Team Falcons").replace("/team/13518/acend", "/team/10568/team-falcons")
                       .replace("9th of September 2026", "24th of September 2026")
                       .replace("2397860", "2399999"))
        fetcher = FakeFetcher({h.hltv_match_url("2399999"): wrong_teams})
        c.collect_hltv_crosscheck(obs, fetcher, NOW, TEAMS, "live")
        fixture = obs["fixtures"][0]
        self.assertEqual(fixture["status"], "conflict")
        self.assertTrue(any(a["code"] == "crosscheck_conflict" for a in obs["alerts"]))
        # Conflicted fixtures are ineligible for the engine.
        placed = comp.apply_match_strategies(synthetic_ledger(), obs, NOW, TEAMS, STRATEGIES)
        self.assertEqual(placed, [])


class SettlementJournalTests(unittest.TestCase):
    def settled_fixture_obs(self):
        obs, ledger = synthetic_match_obs()
        obs["fixtures"][0].update({
            "finished": True, "derived_winner": "team_a", "series_score": [2, 0],
            "result_status": "confirmed",
            "result": {"winner": "furia", "series_score": [2, 0], "confirmed_utc": c.stamp(NOW),
                       "sources": ["https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026",
                                   "https://www.hltv.org/matches/2399999"]},
        })
        # One paper position on FURIA (won) and one on Team Falcons (lost).
        comp.apply_match_strategies(ledger, obs, NOW, TEAMS, STRATEGIES)
        return obs, ledger

    def kalshi_market(self, result, cents):
        return {"ticker": "KXCS2GAME-TEST-FURIA", "status": "settled", "result": result,
                "settlement_value_cents": cents, "title": "FURIA vs. Team Falcons",
                "yes_sub_title": "FURIA"}

    def test_chain_tampering_is_detected(self):
        from scripts.settle import append_row, empty_journal, verify_chain
        from scripts.collect import SourceError
        journal = empty_journal()
        append_row(journal, "SIM-1", "venue_resolution", c.stamp(NOW), {"a": 1})
        append_row(journal, "SIM-1", "result_confirmation", c.stamp(NOW), {"b": 2})
        verify_chain(journal["rows"])
        journal["rows"][0]["observation"]["a"] = 999  # rewrite history
        with self.assertRaisesRegex(SourceError, "chain"):
            verify_chain(journal["rows"])

    def test_agreeing_win_and_loss_settle_with_venue_and_independent_sources(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        markets = {
            st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": self.kalshi_market("yes", 100),
            st.KALSHI + "/markets/KXCS2GAME-TEST-FAL": {"ticker": "KXCS2GAME-TEST-FAL", "status": "settled",
                                                        "result": "no", "settlement_value_cents": 0,
                                                        "yes_sub_title": "Team Falcons"},
        }
        wikitext = "x" * 10
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        st.verify_chain(journal["rows"])
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        furia = by_sel[("sim_underdog_hunter", "FURIA")]
        falcons = by_sel[("sim_favorite_backer", "Team Falcons")]
        self.assertEqual(furia["settlement"]["result"], "win")
        self.assertEqual(furia["payout"], str((Decimal("15.00") / Decimal("0.55")).quantize(Decimal("0.01"))))
        self.assertEqual(falcons["settlement"]["result"], "loss")
        self.assertEqual(falcons["payout"], "0.00")
        for e in by_sel.values():
            urls = [s["url"] for s in e["settlement"]["result_source"]]
            self.assertTrue(any("kalshi.com" in u for u in urls))
            self.assertTrue(any("hltv.org" in u for u in urls))
            self.assertTrue(any("liquipedia.net" in u for u in urls))
        kinds = [r["kind"] for r in journal["rows"]]
        self.assertIn("venue_resolution", kinds)
        self.assertIn("settlement_decision", kinds)

    def test_fifty_fifty_settles_partial_and_never_a_refund(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": self.kalshi_market("yes", 50)}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        furia = by_sel[("sim_underdog_hunter", "FURIA")]
        self.assertEqual(furia["settlement"]["result"], "partial")
        self.assertEqual(furia["settlement"]["payout_fraction"], "0.5000")
        expected = (Decimal("15.00") * Decimal("0.5") / Decimal("0.55")).quantize(Decimal("0.01"))
        self.assertEqual(furia["payout"], str(expected))
        self.assertEqual(furia["profit"], str(expected - Decimal("15.00")))
        # The Falcons leg has no venue receipt yet: it must stay pending.
        self.assertEqual(by_sel[("sim_favorite_backer", "Team Falcons")]["settlement"]["result"], "pending")

    def test_venue_disagreement_with_fixture_holds_pending(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        # Venue claims Falcons won; the double-sourced fixture says FURIA won.
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA":
                   {**self.kalshi_market("yes", 100), "yes_sub_title": "Team Falcons"}}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        self.assertEqual(by_sel[("sim_underdog_hunter", "FURIA")]["settlement"]["result"], "pending")
        self.assertEqual(by_sel[("sim_underdog_hunter", "FURIA")]["payout"], None)
        self.assertTrue(any(r["kind"] == "settlement_hold" for r in journal["rows"]))
        self.assertTrue(any("venue_vs_fixtures" in r.get("conflicts", []) for r in journal["rows"]))

    def test_zero_payout_on_selection_that_fixture_says_won_holds(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        # Kalshi paid the FURIA Yes at 0 cents although the confirmed result says FURIA won.
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": self.kalshi_market("yes", 0)}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        furia = by_sel[("sim_underdog_hunter", "FURIA")]
        self.assertEqual(furia["settlement"]["result"], "pending")  # never a loss against the confirmed result
        holds = [r for r in journal["rows"] if r["kind"] == "settlement_hold" and "venue_vs_fixtures" in r.get("conflicts", [])]
        self.assertTrue(holds)
        # The genuinely losing Falcons leg still has no venue receipt here: pending too.
        self.assertEqual(by_sel[("sim_favorite_backer", "Team Falcons")]["settlement"]["result"], "pending")

    def test_kalshi_wrapped_market_response_resolves(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        # Kalshi GET /markets/{ticker} returns {"market": {...}} — accept the wrapper.
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": {"market": self.kalshi_market("yes", 100)}}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        self.assertEqual(by_sel[("sim_underdog_hunter", "FURIA")]["settlement"]["result"], "win")

    def test_crash_after_journal_write_reapplies_decision_without_refetch(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": self.kalshi_market("yes", 100)}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        settled = by_sel[("sim_underdog_hunter", "FURIA")]
        # Simulate a crash between the journal write and the ledger write.
        settled["settlement"] = {"result": "pending", "rule": settled["settlement"]["rule"]}
        settled["payout"] = None
        settled["profit"] = None
        decisions = [r for r in journal["rows"] if r["kind"] == "settlement_decision"
                     and r["entry_id"] == settled["entry_id"]]
        self.assertEqual(len(decisions), 1)
        # Recovery pass: an empty venue (fetch would fail) must still re-apply the receipt's decision.
        st.settle_all(ledger, obs, journal, FakeFetcher({}))
        recovered = by_sel[("sim_underdog_hunter", "FURIA")]
        self.assertEqual(recovered["settlement"]["result"], "win")
        self.assertEqual(recovered["payout"], str((Decimal("15.00") / Decimal("0.55")).quantize(Decimal("0.01"))))
        self.assertEqual(recovered["settlement"]["settled_utc"], settled["settlement"]["settled_utc"])
        # No duplicate decision receipt was appended for this entry.
        self.assertEqual([r for r in journal["rows"] if r["kind"] == "settlement_decision"
                          and r["entry_id"] == settled["entry_id"]], decisions)
        st.verify_chain(journal["rows"])

    def test_offline_run_without_positions_appends_no_wikitext_hold(self):
        from scripts import settle as st
        obs, ledger = synthetic_match_obs()  # fixtures only, zero paper positions
        journal = st.empty_journal()
        st.settle_all(ledger, obs, journal, FakeFetcher({}))  # Liquipedia unreachable
        self.assertEqual(len(journal["rows"]), 0)

    def test_offline_run_with_pending_outright_appends_one_wikitext_hold(self):
        from scripts import settle as st
        obs, ledger = synthetic_match_obs()
        entry = {"entry_id": "SIM-OUT-1", "username": "sim_champ_correlation", "event_key": "twc26-champion",
                 "match_id": "TWC26-FINALS-CHAMPION", "market": "TWC 2026 Champion", "selection": "FURIA",
                 "stake": "50.00", "decimal_odds": "1.8182",
                 "price_source": {"venue": "Kalshi", "market_id": "KXCS2", "raw_price": "0.55", "ask_size": "200",
                                  "observed_utc": c.stamp(NOW), "source_updated_utc": c.stamp(NOW),
                                  "url": st.KALSHI + "/markets/KXCS2", "event_url": "https://kalshi.com/", "quote_id": "q1"},
                 "fill_policy": "test", "placed_utc": c.stamp(NOW),
                 "settlement": {"result": "pending", "rule": "venue rules apply"}}
        ledger["entries"].append(entry)
        journal = st.empty_journal()
        st.settle_all(ledger, obs, journal, FakeFetcher({}))
        self.assertEqual(entry["settlement"]["result"], "pending")
        # Two holds: one journal-wide (wikitext unavailable) + one per-entry (venue unreachable).
        self.assertEqual([r["kind"] for r in journal["rows"]], ["settlement_hold", "settlement_hold"])
        self.assertEqual(journal["rows"][0]["entry_id"], "journal")
        self.assertIn("Liquipedia", journal["rows"][0]["observation"]["reason"])
        self.assertEqual(journal["rows"][1]["entry_id"], "SIM-OUT-1")

    def test_unresolved_or_canceled_venue_never_settles_and_void_is_never_assumed(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": {"ticker": "KXCS2GAME-TEST-FURIA", "status": "active"}}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        by_sel = {(e["username"], e["selection"]): e for e in ledger["entries"]}
        self.assertEqual(by_sel[("sim_underdog_hunter", "FURIA")]["settlement"]["result"], "pending")
        self.assertTrue(any(r["kind"] == "venue_resolution" and r["observation"] == {"resolved": False}
                            for r in journal["rows"]))
        self.assertTrue(any(r["kind"] == "settlement_hold" for r in journal["rows"]))

    def test_validator_accepts_synthetic_chained_journal(self):
        from scripts import settle as st
        obs, ledger = self.settled_fixture_obs()
        journal = st.empty_journal()
        markets = {st.KALSHI + "/markets/KXCS2GAME-TEST-FURIA": self.kalshi_market("yes", 100)}
        st.settle_all(ledger, obs, journal, FakeFetcher(markets))
        errors = []
        v.ERRORS.clear()
        v.check_settlements(journal, ledger)
        errors.extend(v.ERRORS)
        self.assertEqual(errors, [])


class ArchiveDurabilityTests(unittest.TestCase):
    def test_manifest_records_digests_and_chain_head(self):
        import scripts.archive as arch
        from scripts import settle as st
        journal = st.empty_journal()
        st.append_row(journal, "SIM-1", "venue_resolution", c.stamp(NOW), {"x": 1})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "snap"
            data = Path(tmp) / "data"
            data.mkdir(parents=True)
            (data / "settlements.json").write_text(json.dumps(journal), encoding="utf-8")
            real_data = arch.ROOT / "data"
            copied = []
            try:  # copy the tracked journal into a temp repo view
                for name in ("observations.json", "ledger.json"):
                    shutil2 = data / name
                    shutil2.write_text((real_data / name).read_text(encoding="utf-8"), encoding="utf-8")
                    copied.append(shutil2)
                original_root = arch.ROOT
                arch.ROOT = Path(tmp)  # archive must read from the temp view only
                try:
                    manifest = arch.build(out, run_id="TEST-1")
                finally:
                    arch.ROOT = original_root
                self.assertEqual(set(manifest["files"]), {"observations.json", "ledger.json", "settlements.json"})
                self.assertEqual(manifest["settlement_rows"], 1)
                self.assertTrue(manifest["settlement_chain_head"])
                for name, digest in manifest["files"].items():
                    import hashlib as _h
                    actual = _h.sha256((out / name).read_bytes()).hexdigest()
                    self.assertEqual(digest, actual)
                self.assertEqual(manifest["run_id"], "TEST-1")
            finally:
                for p in copied:
                    p.unlink(missing_ok=True)


class RestoreSettlementsTests(unittest.TestCase):
    def test_longer_chain_wins_but_divergence_stops(self):
        from scripts import settle as st
        base = st.empty_journal()
        st.append_row(base, "SIM-1", "venue_resolution", c.stamp(NOW), {"x": 1})
        longer = st.empty_journal()
        longer["rows"] = list(base["rows"])
        longer["chain_head"] = base["chain_head"]
        st.append_row(longer, "SIM-1", "settlement_hold", c.stamp(NOW), {"y": 2})
        restored = rest.restore_settlements(base, longer)
        self.assertEqual(len(restored["rows"]), 2)
        divergent = st.empty_journal()
        st.append_row(divergent, "SIM-1", "venue_resolution", c.stamp(NOW), {"x": 999})
        with self.assertRaisesRegex(rest.SourceError, "diverge"):
            rest.restore_settlements(base, divergent)
        with self.assertRaisesRegex(rest.SourceError, "missing/rewritten"):
            rest.restore_settlements(longer, base)


class ValidatorLiveCheckSetTests(unittest.TestCase):
    """The post-merge-8 outage: a live run emitted the collector's 9 checks but
    validate.py still hard-coded the old 7-source list, so every scheduled
    publication failed validation and the feed went stale. These tests pin the
    validator to the collector's own SOURCE_IDS so they cannot drift again."""

    def live_doc(self):
        doc = c.collect(c.empty(), c.FixtureFetcher(), NOW, TEAMS, "offline-replay")
        doc["mode"] = "live"  # test-only: assert the live-mode completeness rule
        return doc

    def observed(self, doc):
        v.ERRORS.clear()
        v.check_observations(doc, TEAMS)
        return list(v.ERRORS)

    def test_live_journal_accepts_exactly_the_collector_source_set(self):
        doc = self.live_doc()
        self.assertEqual(len(doc["checks"]), len(c.SOURCE_IDS))
        self.assertEqual(sorted(x["source"] for x in doc["checks"]), sorted(c.SOURCE_IDS))
        self.assertEqual(self.observed(doc), [])

    def test_live_journal_missing_one_source_check_fails(self):
        doc = self.live_doc()
        doc["checks"] = doc["checks"][:-1]
        errors = self.observed(doc)
        self.assertTrue(any("exactly one check per collected source" in e for e in errors))

    def test_live_journal_unknown_source_check_fails(self):
        doc = self.live_doc()
        doc["checks"].append({"source": "made_up_feed", "status": "ok",
                              "url": "https://example.com/feed", "checked_utc": c.stamp(NOW),
                              "records_checked": 0, "scope": "test"})
        errors = self.observed(doc)
        self.assertTrue(any("duplicate or unknown source" in e for e in errors))

    def test_validator_source_set_matches_collector_constant(self):
        from scripts.validate import REQUIRED_SOURCES
        self.assertEqual(tuple(sorted(REQUIRED_SOURCES)), tuple(sorted(c.SOURCE_IDS)))

    def test_tracked_offline_seed_remains_valid_under_derived_set(self):
        seed = json.loads((ROOT / "data" / "observations.json").read_text(encoding="utf-8"))
        self.assertEqual(self.observed(seed), [])


class ArchiveModeGuardTests(unittest.TestCase):
    """Run 36050952696's first archive commit stored the committed offline seed:
    the deploy job's fresh checkout had ROOT/data = seed, not the published
    live journal. build() must refuse to archive the wrong mode and must be
    able to archive an explicit directory."""

    def temp_journal(self, tmp: Path, mode: str) -> Path:
        data = tmp / "data"
        data.mkdir(parents=True, exist_ok=True)
        obs = {"schema_version": 1, "mode": mode,
               "last_attempt_utc": c.stamp(NOW), "last_completed_utc": c.stamp(NOW),
               "checks": [], "vrs_history": [], "roster_signals": [],
               "fixtures": [], "events": [], "quotes": [], "alerts": []}
        (data / "observations.json").write_text(json.dumps(obs), encoding="utf-8")
        (data / "ledger.json").write_text(json.dumps(synthetic_ledger()), encoding="utf-8")
        from scripts import settle as st
        (data / "settlements.json").write_text(json.dumps(st.empty_journal()), encoding="utf-8")
        return data

    def test_archive_refuses_offline_seed_when_live_expected(self):
        import scripts.archive as arch
        with tempfile.TemporaryDirectory() as tmp:
            data = self.temp_journal(Path(tmp), "offline-replay")
            with self.assertRaises(SystemExit):
                arch.build(Path(tmp) / "snap", run_id="T", data_dir=data, expect_mode="live")

    def test_archive_accepts_live_journal_from_explicit_dir(self):
        import scripts.archive as arch
        with tempfile.TemporaryDirectory() as tmp:
            data = self.temp_journal(Path(tmp), "live")
            snap = Path(tmp) / "snap"
            manifest = arch.build(snap, run_id="T", commit_url="https://example/run/T",
                                  data_dir=data, expect_mode="live")
            self.assertEqual(manifest["journal"]["mode"], "live")
            self.assertEqual(manifest["run_id"], "T")
            self.assertEqual(manifest["commit_url"], "https://example/run/T")
            self.assertEqual(set(manifest["files"]), {"observations.json", "ledger.json", "settlements.json"})
            self.assertEqual(json.loads((data / "archive_manifest.json").read_text(encoding="utf-8")), manifest)

    def test_workflow_archives_live_journal_inside_build_job(self):
        text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("--expect-mode live", text)
        build_part = text.split("deploy:", 1)[0]
        archive_at = build_part.index("Archive the live journal")
        artifact_at = build_part.index("Save short-lived recovery artifact")
        self.assertLess(archive_at, artifact_at, "archive must run before the artifact/site packaging in the build job")
        deploy_part = text.split("deploy:", 1)[1]
        self.assertNotIn("scripts.archive", deploy_part, "deploy-job checkout archives the stale seed; archive belongs in the build job")
