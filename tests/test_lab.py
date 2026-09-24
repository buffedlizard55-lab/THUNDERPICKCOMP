"""Strategy lab + historical line store. Real-fixture replays plus SYNTHETIC in-memory/tmp data only."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import historical_lines as hl
from scripts import strategy_lab as lab
from tests.synthetic_lab import make


class LineStoreTests(unittest.TestCase):
    def test_fixture_replay_builds_real_lines_and_audits_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(hl.main(["--fixtures", "--lab-dir", str(d), "--budget-minutes", "1"]), 0)
            store = hl.load_store(d)
            venues = sorted(r["venue"] for r in store["lines"])
            self.assertEqual(venues, ["kalshi", "polymarket"])
            k = next(r for r in store["lines"] if r["venue"] == "kalshi")
            # Recorded real candle: GBC ask .6200 / bid .5400 in the last candle before the 2:15 PM EDT start.
            t0 = k["quotes"]["T-0"]
            self.assertEqual({t0[0]["ask"], t0[1]["ask"]}, {"0.6200", "0.4500"})
            self.assertTrue(all(q["t"] <= hl.parse_iso(k["cutoff_utc"]).timestamp() - 300
                                for label, back in hl.CHECKPOINTS if k["quotes"].get(label)
                                for q in k["quotes"][label] if q))
            self.assertEqual(hl.main(["--fixtures", "--lab-dir", str(d), "--audit", "2"]), 0)
            report = json.loads((d / "audit.json").read_text())
            self.assertEqual((report["mismatches"], report["matches"]), (0, 2))

    def test_monthly_shards_legacy_migration_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            store = make(d / "src", n=40)
            legacy = copy.deepcopy(store)
            (d / "lines.json").write_text(json.dumps(legacy))
            migrated = hl.load_store(d)  # legacy single file is read once...
            hl.save_store(migrated, d)   # ...then written as shards and removed
            self.assertFalse((d / "lines.json").exists())
            meta = json.loads((d / "lines_meta.json").read_text())
            self.assertEqual(meta["lines_total"], 40)
            self.assertEqual(sum(meta["shards"].values()), 40)
            again = hl.load_store(d)
            self.assertEqual([r["line_id"] for r in again["lines"]], [r["line_id"] for r in store["lines"]])
            shard = sorted((d / "lines").glob("*.json"))[0]
            rows = json.loads(shard.read_text())
            rows.append(rows[0])
            shard.write_text(json.dumps(rows))
            with self.assertRaisesRegex(hl.LineError, "duplicate"):
                hl.load_store(d)
            rows[-1] = dict(rows[0], line_id="X:other", cutoff_utc="1999-01-01T00:00:00Z")
            shard.write_text(json.dumps(rows))
            with self.assertRaisesRegex(hl.LineError, "another month"):
                hl.load_store(d)

    def test_unsettled_market_is_retried_not_excluded(self):
        self.assertTrue(issubclass(hl.NotYetFinal, hl.LineError))
        market = json.loads((hl.FIXTURES / "poly_markets_page.json").read_text())[0]
        market = dict(market, umaResolutionStatus="proposed", closed=False)
        with self.assertRaises(hl.NotYetFinal):
            hl.build_poly_line(market, hl.FixtureFetcher())


class LabMathTests(unittest.TestCase):
    def test_kalshi_integer_contracts_and_round_up_fee(self):
        contracts, cost, fee = lab.position("kalshi", 10.0, 0.62)
        self.assertEqual((contracts, cost), (16.0, 9.92))
        self.assertEqual(fee, 0.2639)  # 0.07*16*0.62*0.38 = 0.263872 -> rounded UP to the centicent
        self.assertEqual(lab.kalshi_fee(1, 0.5), 0.0175)
        self.assertEqual(lab.kalshi_fee(100, 0.5), 1.75)
        self.assertIsNone(lab.position("kalshi", 0.5, 0.62))

    def test_polymarket_shares_floor_to_cents_and_fee(self):
        shares, cost, fee = lab.position("polymarket", 10.0, 0.74)
        self.assertEqual(shares, 13.51)
        self.assertEqual(cost, 9.9974)
        self.assertEqual(fee, round(13.51 * 0.05 * 0.74 * 0.26, 5))

    def test_every_stake_is_capped(self):
        s = {"params": {"stake": "pct"}}
        self.assertEqual(lab.stake_for(s, 1_000_000.0, {"buy": 0.5}, None), lab.MAX_STAKE)
        s = {"params": {"stake": "kelly"}}
        self.assertEqual(lab.stake_for(s, 1_000_000.0, {"buy": 0.3}, 0.9), lab.MAX_STAKE)
        self.assertEqual(lab.stake_for(s, 1000.0, {"buy": 0.6}, 0.5), 0.0)

    def test_quote_gates_reject_empty_books(self):
        line = {"venue": "kalshi", "quotes": {"T-1h": [{"t": 1, "ask": "0.9900", "bid": "0.0300"},
                                                        {"t": 1, "ask": "0.9200", "bid": "0.0100"}]},
                "settlement": ["1.0000", "0.0000"]}
        self.assertIsNone(lab.venue_quote(line, "T-1h", 0))
        line["quotes"]["T-1h"][0] = {"t": 1, "ask": "0.5000", "bid": "0.4600"}
        self.assertIsNotNone(lab.venue_quote(line, "T-1h", 0))

    def test_universe_is_large_distinct_and_deterministic(self):
        a, b = lab.strategy_universe(), lab.strategy_universe()
        self.assertEqual(a, b)
        self.assertGreaterEqual(len(a), 1000)
        self.assertEqual(len({s["id"] for s in a}), len(a))
        self.assertEqual(len({s["username"] for s in a}), len(a))
        self.assertEqual(len({json.dumps(s["params"], sort_keys=True) + s["family"] for s in a}), len(a))
        self.assertTrue(all(s["username"].startswith("sim_") for s in a))


class LabRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        make(cls.dir, n=260, teams=12)
        cls.result = lab.run(cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_controls_and_accounting(self):
        rows = {r["id"]: r for r in self.result["rows"]}
        no_bet = next(r for r in rows.values() if r["family"] == "control_no_bet")
        self.assertEqual((no_bet["all"]["bets"], no_bet["all"]["final_bankroll"]), (0, 1000.0))
        for sid, bets in self.result["all_ledgers"].items():
            final = rows[sid]["all"]["final_bankroll"]
            self.assertAlmostEqual(final, 1000.0 + sum(b[10] for b in bets), places=2)
            for b in bets:
                self.assertAlmostEqual(b[10], b[9] - b[6] - b[7], places=3)  # pnl = payout - cost - fee
                self.assertLessEqual(b[6], lab.MAX_STAKE + 1e-6)
                if b[1] == "k":
                    self.assertEqual(b[5], int(b[5]))

    def test_no_look_ahead_and_elo_walk_forward(self):
        matches = self.result["matches"]
        strategies = {s["id"]: s for s in self.result["strategies"]}
        for sid, bets in self.result["all_ledgers"].items():
            cp = strategies[sid]["params"]["cp"]
            for b in bets:
                self.assertLessEqual(b[3], matches[b[0]]["cutoff"] - lab.CP_BACK[cp])
        # Brute force: Elo game counts must equal matches settled strictly before each decision time.
        table = lab.elo_tables(matches, ks=(16,))[16]
        for m in matches[::7]:
            for label in lab.CP_LABELS:
                t = m["cutoff"] - lab.CP_BACK[label]
                prior = [x for x in matches if x["winner"] is not None and x["settled"] < t]
                a, b = m["norm"]
                expect = (sum(a in x["norm"] for x in prior), sum(b in x["norm"] for x in prior))
                self.assertEqual(table[m["id"]][label][1:], expect)

    def test_leaderboard_is_ranked_and_deterministic(self):
        rows = self.result["rows"]
        self.assertEqual([r["rank"] for r in rows], list(range(1, len(rows) + 1)))
        banks = [r["all"]["final_bankroll"] for r in rows]
        self.assertEqual(banks, sorted(banks, reverse=True))
        again = lab.run(self.dir)
        self.assertEqual(json.dumps(again["rows"]), json.dumps(rows))
        lab.write(self.dir, self.result)
        doc = json.loads((self.dir / "leaderboard.json").read_text())
        self.assertTrue(doc["simulated"])
        self.assertEqual(len(doc["rows"]), len(rows))
        self.assertTrue((self.dir / "ledgers").is_dir())

    def test_validator_recomputes_ledgers_and_catches_tampering(self):
        import scripts.validate as v
        lab.write(self.dir, self.result)
        v.ERRORS.clear()
        v.check_lab(self.dir, allow_synthetic=True)
        self.assertEqual(v.ERRORS, [])
        led_path = next(p for p in sorted((self.dir / "ledgers").glob("S*.json"))
                        if json.loads(p.read_text())["bets"])
        original = led_path.read_text()
        led = json.loads(original)
        led["bets"][0][7] = round(led["bets"][0][7] - 0.01, 4)  # under-charge a fee
        led_path.write_text(json.dumps(led))
        v.ERRORS.clear()
        v.check_lab(self.dir, allow_synthetic=True)
        self.assertTrue(any("cost/fee do not recompute" in e for e in v.ERRORS))
        led_path.write_text(original)
        shard = sorted((self.dir / "lines").glob("*.json"))[0]
        rows = json.loads(shard.read_text())
        pair = next(iter(rows[0]["quotes"].values()))
        pair[0]["t"] = hl.parse_iso(rows[0]["cutoff_utc"]).timestamp() + 60  # quote after the start
        saved = shard.read_text()
        shard.write_text(json.dumps(rows))
        v.ERRORS.clear()
        v.check_lab(self.dir, allow_synthetic=True)
        self.assertTrue(any("look-ahead" in e for e in v.ERRORS))
        v.ERRORS.clear()
        v.check_lab(self.dir)  # synthetic receipts are never acceptable as real data
        self.assertTrue(any("unexpected mode" in e or "allowlist" in e for e in v.ERRORS))
        shard.write_text(saved)
        v.ERRORS.clear()

    def test_late_cross_venue_quote_is_dropped(self):
        k = copy.deepcopy(next(r for r in hl.load_store(self.dir)["lines"] if r["venue"] == "kalshi"))
        k["line_id"] = "K:LINK"
        p = copy.deepcopy(k)
        p.update(venue="polymarket", line_id="P:LINK", cutoff_utc=lab.iso(lab.ts(k["cutoff_utc"]) - 3600))
        p["quotes"] = {label: [{"t": q[0]["t"] - 3600, "p": 0.5}, {"t": q[1]["t"] - 3600, "p": 0.5}]
                       for label, q in k["quotes"].items()}
        matches, _ = lab.build_matches([k, p])
        self.assertEqual(len(matches), 1)
        m = matches[0]
        self.assertEqual(m["cutoff"], lab.ts(p["cutoff_utc"]))
        # Kalshi's T-0 quote is 10 min before ITS start, i.e. 50 min AFTER the linked match cutoff.
        q = lab.match_quote(m, "kalshi", "T-0", 0)
        self.assertGreater(q["t"], m["cutoff"] - lab.CP_BACK["T-0"])
        # run() must therefore treat it as unavailable (the per-match quote cache drops it).
        with tempfile.TemporaryDirectory() as tmp:
            store = hl.empty_store()
            store["lines"] = [k, p]
            hl.save_store(store, Path(tmp))
            result = lab.run(Path(tmp))
            only = result["matches"][0]
            self.assertIsNone(lab.match_quote(only, "kalshi", "T-0", 0))
            self.assertIsNotNone(lab.match_quote(only, "polymarket", "T-0", 0))
            self.assertGreaterEqual(result["analytics"]["dataset"]["quotes_dropped_after_match_cutoff"], 2)


if __name__ == "__main__":
    unittest.main()
