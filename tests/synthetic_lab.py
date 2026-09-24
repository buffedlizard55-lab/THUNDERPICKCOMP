"""SYNTHETIC lines for engine tests only. Never written under data/; never published."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from scripts.historical_lines import CHECKPOINTS, empty_store, save_store


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make(lab: Path, n: int = 400, seed: int = 7, teams: int = 30) -> dict:
    rng = random.Random(seed)
    names = [f"Synth{i}" for i in range(teams)]
    strength = {t: rng.gauss(0, 1) for t in names}
    store = empty_store()
    store["mode"] = "synthetic-test"
    t0 = 1780000000
    for i in range(n):
        a, b = rng.sample(names, 2)
        cutoff = t0 + i * 5400
        p_true = 1 / (1 + 10 ** ((strength[b] - strength[a]) / 1.5))
        win = 0 if rng.random() < p_true else 1
        venue = "kalshi" if i % 3 else "polymarket"
        quotes = {}
        for label, back in CHECKPOINTS:
            pa = min(0.95, max(0.05, p_true + rng.gauss(0, 0.05)))
            t = cutoff - back - 600
            if venue == "kalshi":
                ask_a, bid_a = round(pa + 0.02, 2), round(pa - 0.02, 2)
                ask_b, bid_b = round(1 - pa + 0.02, 2), round(1 - pa - 0.02, 2)
                quotes[label] = [{"t": t, "ask": f"{ask_a:.4f}", "bid": f"{bid_a:.4f}", "last": None, "vol": "10.0000"},
                                 {"t": t, "ask": f"{ask_b:.4f}", "bid": f"{bid_b:.4f}", "last": None, "vol": "10.0000"}]
            else:
                quotes[label] = [{"t": t, "p": round(pa, 3)}, {"t": t, "p": round(1 - pa, 3)}]
        store["lines"].append({
            "line_id": f"{venue[0].upper()}:SYN{i}", "venue": venue, "market_ids": [f"SYN{i}"],
            "competition": "IEM Synthetic" if i % 4 == 0 else "Synthetic Cup", "format": "BO3" if venue == "polymarket" else None,
            "teams": [a, b], "cutoff_utc": iso(cutoff), "start_evidence": "synthetic", "settled_utc": iso(cutoff + 7200),
            "settlement": ["1.0000", "0.0000"] if win == 0 else ["0.0000", "1.0000"], "winner": win,
            "volume": ["1.0000", None], "quotes": quotes, "price_urls": ["https://example.invalid/synthetic"],
            "market_urls": [], "review_url": "https://example.invalid/synthetic", "flags": []})
    store["last_run_utc"] = iso(t0 + n * 5400)
    save_store(store, lab)
    return store
