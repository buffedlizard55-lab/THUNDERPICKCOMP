#!/usr/bin/env python3
"""Strategy lab: replay 1,000+ distinct simulated CS2 betting strategies on REAL historical lines.

Run from the repository root:  python3 -m scripts.strategy_lab [--lab-dir data/lab]

Inputs : data/lab/lines/*.json + lines_meta.json (real venue receipts, see scripts/historical_lines.py)
Outputs: data/lab/strategies.json   every strategy definition (params, rule text, simulated username)
         data/lab/leaderboard.json  per-strategy results, full sample + chronological train/test split
         data/lab/analytics.json    dataset coverage, calibration, family/dimension summaries,
                                    multiple-testing context, irregularities flagged for review
         data/lab/matches.json      match table (cross-venue links) referenced by ledgers
         data/lab/ledgers/<id>.json every simulated bet for featured strategies (build artifact)

Rules that keep this honest:
  * A strategy may only use information timestamped BEFORE its decision checkpoint: quotes at or
    before the checkpoint and Elo ratings built from matches that SETTLED before it.
  * Entry price = venue receipt (Kalshi yes_ask close; Polymarket reference p + 1c slippage).
  * Kalshi contracts are whole numbers; Polymarket shares round down to 0.01.
  * Fees: Kalshi general taker formula (M=1, Jul 7 2026 schedule); Polymarket sports taker rate 0.05
    (current docs; applied to all dates, which is conservative where fees were lower/absent).
  * Settlement = the venue's own final settlement value (1/0, or 0.5 / fair value when it said so).
  * Everything is SIMULATED. Nothing here was executed and nothing here is betting advice.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import re
import unicodedata
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .historical_lines import CHECKPOINTS, LAB, load_store, parse_iso

START_BANKROLL = 1000.0
CP_LABELS = [label for label, _ in CHECKPOINTS]
CP_BACK = dict(CHECKPOINTS)
KALSHI_MAX_SPREAD = 0.10
POLY_SLIPPAGE = 0.01
POLY_FEE_RATE = 0.05
KALSHI_FEE_RATE = 0.07
LINK_WINDOW = 4 * 3600
QUALIFY_BETS = 30
# Order-book depth at the quote time is NOT known (Kalshi candles give top-of-book only; Polymarket gives a
# reference price). A hard per-bet cap keeps simulated sizes plausible for thin CS2 books and stops
# compounding stakes from producing fantasy bankrolls.
MAX_STAKE = 50.0
TRAIN_FRACTION = 0.70
TOP_TIER = re.compile(r"\b(IEM|BLAST|ESL Pro League|PGL|Major|StarLadder|StarSeries|Thunderpick World Championship|"
                      r"FISSURE|BetBoom Dacha|Esports World Cup|CS Asia Championships|Perfect World)\b", re.I)
STRIP_TOKENS = {"team", "esports", "esport", "gaming", "club", "e-sports"}


# --------------------------------------------------------------------------- helpers

def r4(x: float) -> float:
    return round(x + 0.0, 4)


def ts(value: str) -> int:
    return int(parse_iso(value).timestamp())


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_team(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    words = [w for w in re.split(r"[^a-z0-9]+", text) if w and w not in STRIP_TOKENS]
    return "".join(words)


def kalshi_fee(contracts: int, price: float) -> float:
    """round up(0.07 x C x P x (1-P)) to the centicent (kalshi.com/docs/kalshi-fee-schedule.pdf)."""
    raw = KALSHI_FEE_RATE * contracts * price * (1 - price)
    return math.ceil(raw * 10000 - 1e-7) / 10000


def poly_fee(shares: float, price: float) -> float:
    """C x feeRate x p x (1-p), sports feeRate 0.05, 5 dp (docs.polymarket.com/trading/fees)."""
    return round(shares * POLY_FEE_RATE * price * (1 - price), 5)


def position(venue: str, stake: float, price: float) -> tuple[float, float, float] | None:
    """(contracts, cost, fee) for a target stake, or None if below one contract/share."""
    if venue == "kalshi":
        contracts = math.floor(stake / price + 1e-9)
        if contracts < 1:
            return None
        return float(contracts), r4(contracts * price), kalshi_fee(contracts, price)
    shares = math.floor(stake / price * 100 + 1e-9) / 100
    if shares < 1:
        return None
    return shares, r4(shares * price), poly_fee(shares, price)


def norm_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 5:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 4) if den else None


# --------------------------------------------------------------------------- quotes & matches

def venue_quote(line: dict, label: str, side: int) -> dict | None:
    """Normalised, gated quote for buying `side` at checkpoint `label`, or None."""
    pair = line["quotes"][label]
    q = pair[side]
    if not q:
        return None
    if line["venue"] == "kalshi":
        ask, bid = float(q["ask"]), float(q["bid"])
        if bid <= 0 or ask > 0.99 or ask < 0.02 or ask - bid > KALSHI_MAX_SPREAD + 1e-9:
            return None
        return {"venue": "kalshi", "buy": ask, "implied": (ask + bid) / 2, "t": q["t"], "spread": r4(ask - bid)}
    p = q["p"]
    other = pair[1 - side]
    if not 0.02 <= p <= 0.98 or (other and abs(p + other["p"] - 1) > 0.05):
        return None
    return {"venue": "polymarket", "buy": min(0.99, r4(p + POLY_SLIPPAGE)), "implied": p, "t": q["t"], "spread": None}


def build_matches(lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """One match per real fixture; a Kalshi and a Polymarket line are linked only when both
    normalised team names agree and the cutoffs are within 4h with a UNIQUE candidate."""
    irregular: list[dict] = []
    usable = [l for l in lines if "no_prestart_quotes" not in l["flags"]]
    by_pair: dict[frozenset, list[dict]] = defaultdict(list)
    for line in usable:
        names = [norm_team(t) for t in line["teams"]]
        if not all(names) or names[0] == names[1]:
            irregular.append({"type": "unnormalisable_team_names", "line_id": line["line_id"], "teams": line["teams"]})
            continue
        by_pair[frozenset(names)].append(line)
    matches: list[dict] = []
    for pair, group in by_pair.items():
        group.sort(key=lambda l: ts(l["cutoff_utc"]))
        used = set()
        for i, line in enumerate(group):
            if line["line_id"] in used:
                continue
            used.add(line["line_id"])
            cut = ts(line["cutoff_utc"])
            near = [g for g in group[i + 1:] if g["line_id"] not in used and abs(ts(g["cutoff_utc"]) - cut) <= LINK_WINDOW]
            same_venue = [g for g in near if g["venue"] == line["venue"]]
            other = [g for g in near if g["venue"] != line["venue"]]
            for dup in same_venue:  # a second market for the same fixture on the same venue
                used.add(dup["line_id"])
                irregular.append({"type": "duplicate_same_venue_market", "line_id": dup["line_id"], "kept": line["line_id"]})
            linked = {line["venue"]: line}
            if len(other) == 1:
                linked[other[0]["venue"]] = other[0]
                used.add(other[0]["line_id"])
            elif len(other) > 1:
                irregular.append({"type": "ambiguous_cross_venue_link", "line_id": line["line_id"],
                                  "candidates": [o["line_id"] for o in other]})
            ref = linked.get("kalshi") or linked["polymarket"]
            names = [norm_team(t) for t in ref["teams"]]
            align = {}
            for venue, l in linked.items():
                ln = [norm_team(t) for t in l["teams"]]
                align[venue] = [ln.index(n) for n in names]  # align[venue][ref_side] -> venue side
            winners = {}
            for venue, l in linked.items():
                if l["winner"] is not None:
                    winners[venue] = align[venue].index(l["winner"])
            if len(set(winners.values())) > 1:
                irregular.append({"type": "venue_result_conflict", "lines": [l["line_id"] for l in linked.values()],
                                  "detail": "Kalshi and Polymarket settled this fixture for different teams; excluded."})
                continue
            fmt = next((l["format"] for l in linked.values() if l.get("format")), None)
            settle_times = [ts(l["settled_utc"]) for l in linked.values() if l.get("settled_utc")]
            if not settle_times:
                irregular.append({"type": "missing_settlement_time", "lines": [l["line_id"] for l in linked.values()]})
                continue
            settled = max(settle_times)
            matches.append({
                "teams": ref["teams"],
                "norm": names,
                "competition": ref["competition"],
                "format": fmt,
                "tier": "top" if TOP_TIER.search(" ".join(l["competition"] for l in linked.values())) else "other",
                "cutoff": min(ts(l["cutoff_utc"]) for l in linked.values()),
                "settled": settled,
                "winner": next(iter(winners.values())) if winners else None,
                "lines": linked,
                "align": align,
                "cross_checked": len(winners) == 2,
            })
    matches.sort(key=lambda m: (m["cutoff"], "|".join(sorted(l["line_id"] for l in m["lines"].values()))))
    for i, m in enumerate(matches):
        m["id"] = f"M{i + 1:05d}"
    urls = {l["line_id"]: l.get("review_url") for l in lines}
    for item in irregular:  # every irregularity links back to the venue pages for manual review
        ids = [item.get("line_id"), item.get("kept"), *item.get("lines", []), *item.get("candidates", [])]
        item["review_urls"] = [urls[i] for i in ids if i and urls.get(i)]
    return matches, irregular


def match_quote(m: dict, venue: str, label: str, side: int) -> dict | None:
    cache = m.get("_q")
    if cache is not None:
        return cache.get((venue, label, side))
    line = m["lines"].get(venue)
    if not line:
        return None
    q = venue_quote(line, label, m["align"][venue][side])
    if q is None:
        return None
    sv = float(line["settlement"][m["align"][venue][side]])
    return dict(q, settle=sv, line_id=line["line_id"])


def reference_quotes(m: dict, venue_pref: str, label: str):
    """(qA, qB) both from ONE venue for decision-making: preferred venue, else the other if 'best'."""
    order = {"kalshi": ["kalshi"], "polymarket": ["polymarket"], "best": ["kalshi", "polymarket"]}[venue_pref]
    for venue in order:
        qa, qb = match_quote(m, venue, label, 0), match_quote(m, venue, label, 1)
        if qa and qb:
            return qa, qb
    return None


def execution_quote(m: dict, venue_pref: str, label: str, side: int):
    if venue_pref != "best":
        return match_quote(m, venue_pref, label, side)
    options = [q for q in (match_quote(m, v, label, side) for v in ("kalshi", "polymarket")) if q]
    return min(options, key=lambda q: (q["buy"], q["venue"] != "kalshi")) if options else None


# --------------------------------------------------------------------------- walk-forward Elo

def elo_tables(matches: list[dict], ks=(16, 32, 48)) -> dict:
    """elo[K][match_id][label] = (P(side0 wins), games0, games1) using ONLY matches settled
    strictly before that match's checkpoint time."""
    settled = sorted((m for m in matches if m["winner"] is not None), key=lambda m: (m["settled"], m["id"]))
    decisions = sorted(((m["cutoff"] - CP_BACK[label], m["id"], label, m) for m in matches for label in CP_LABELS),
                       key=lambda d: (d[0], d[1], d[2]))
    out = {}
    for k in ks:
        rating: dict[str, float] = defaultdict(lambda: 1500.0)
        games: Counter = Counter()
        table: dict[str, dict] = defaultdict(dict)
        j = 0
        for t, mid, label, m in decisions:
            while j < len(settled) and settled[j]["settled"] < t:
                s = settled[j]
                a, b = s["norm"]
                ea = 1 / (1 + 10 ** ((rating[b] - rating[a]) / 400))
                score = 1.0 if s["winner"] == 0 else 0.0
                rating[a] += k * (score - ea)
                rating[b] -= k * (score - ea)
                games[a] += 1
                games[b] += 1
                j += 1
            a, b = m["norm"]
            table[mid][label] = (1 / (1 + 10 ** ((rating[b] - rating[a]) / 400)), games[a], games[b])
        out[k] = table
    return out


def form_tables(matches: list[dict]) -> dict:
    """form[match_id][label] = (streak_a, streak_b, hours_since_prev_start_a, hours_since_prev_start_b, h2h_winner)

    Walk-forward: streaks and head-to-head use only matches SETTLED before the decision time; the
    fatigue gap uses only matches that STARTED (cutoff) before it. Streak > 0 = consecutive wins,
    < 0 = consecutive losses. h2h_winner is the side (of this match) that won the last settled meeting.
    """
    settled = sorted((m for m in matches if m["winner"] is not None), key=lambda m: (m["settled"], m["id"]))
    starts = sorted(matches, key=lambda m: (m["cutoff"], m["id"]))
    decisions = sorted(((m["cutoff"] - CP_BACK[label], m["id"], label, m) for m in matches for label in CP_LABELS),
                       key=lambda d: (d[0], d[1], d[2]))
    streak: Counter = Counter()
    last_start: dict[str, int] = {}
    h2h: dict[frozenset, str] = {}
    table: dict[str, dict] = defaultdict(dict)
    i = j = 0
    for t, mid, label, m in decisions:
        while i < len(settled) and settled[i]["settled"] < t:
            x = settled[i]
            w, l = x["norm"][x["winner"]], x["norm"][1 - x["winner"]]
            streak[w] = streak[w] + 1 if streak[w] > 0 else 1
            streak[l] = streak[l] - 1 if streak[l] < 0 else -1
            h2h[frozenset(x["norm"])] = w
            i += 1
        while j < len(starts) and starts[j]["cutoff"] < t:
            for team in starts[j]["norm"]:
                last_start[team] = starts[j]["cutoff"]
            j += 1
        a, b = m["norm"]
        gap = [None if team not in last_start or last_start[team] >= m["cutoff"] else (t - last_start[team]) / 3600
               for team in (a, b)]
        winner = h2h.get(frozenset((a, b)))
        table[mid][label] = (streak[a], streak[b], gap[0], gap[1], None if winner is None else (0 if winner == a else 1))
    return table


# --------------------------------------------------------------------------- strategy universe

ADJ = ["Frosty", "Silent", "Rapid", "Lucky", "Sharp", "Calm", "Bold", "Clutch", "Steady", "Wild", "Cold", "Quiet",
       "Swift", "Iron", "Neon", "Lunar", "Solar", "Hidden", "Brave", "Crisp", "Dusty", "Grim", "Hyper", "Jolly",
       "Keen", "Lazy", "Mellow", "Nimble", "Odd", "Proud", "Rusty", "Sly", "Tidy", "Vivid", "Witty", "Zen", "Amber",
       "Cobalt", "Crimson", "Golden"]
NOUN = ["AWP", "Deagle", "Smoke", "Flash", "Molly", "Entry", "Lurker", "Anchor", "Rifler", "IGL", "Eco", "Force",
        "Retake", "Plant", "Defuse", "Ninja", "Peek", "Prefire", "Wallbang", "Spray", "Tap", "Flick", "Jiggle",
        "Boost", "Ladder", "Window", "Connector", "Banana", "Palace", "Heaven", "Pit", "Catwalk", "Tunnels",
        "Mid", "Ramp", "Short", "Long", "Site", "Spawn", "Timing"]
STAKES = {"flat": "flat 10u", "pct": "2% of cash (max 50u)", "fixed_win": "stake to win 10u (max 50u)",
          "kelly": "quarter-Kelly (max 5% of cash, max 50u)"}
SESSIONS = {"asia": (0, 8), "europe": (8, 16), "americas": (16, 24)}
VENUES = {"kalshi": "Kalshi ask", "polymarket": "Polymarket ref+1c", "best": "best price of Kalshi/Polymarket"}


def strategy_universe() -> list[dict]:
    specs: list[tuple[str, dict]] = []
    bands = [(0.05, 0.20), (0.20, 0.35), (0.35, 0.50), (0.05, 0.50), (0.50, 0.65), (0.65, 0.80), (0.80, 0.95), (0.50, 0.95)]
    for lo, hi in bands:
        for cp in CP_LABELS:
            for venue in VENUES:
                for stake in ("flat", "pct", "fixed_win"):
                    specs.append(("price_band", {"lo": lo, "hi": hi, "cp": cp, "venue": venue, "stake": stake}))
    for k in (16, 32, 48):
        for edge in (0.0, 0.03, 0.06, 0.10, 0.15):
            for mg in (3, 10):
                for cp in ("T-6h", "T-1h", "T-0"):
                    for venue in VENUES:
                        for stake in ("flat", "kelly"):
                            specs.append(("elo_value", {"k": k, "edge": edge, "min_games": mg, "cp": cp, "venue": venue, "stake": stake}))
    for direction in ("follow", "fade"):
        for thr in (0.03, 0.06, 0.10):
            for window in (("T-24h", "T-1h"), ("T-6h", "T-0"), ("T-24h", "T-0"), ("T-6h", "T-1h")):
                for venue in VENUES:
                    for stake in ("flat", "pct"):
                        specs.append(("line_move", {"direction": direction, "thr": thr, "from": window[0], "cp": window[1],
                                                    "venue": venue, "stake": stake}))
    for side in ("favorite", "underdog"):
        for fmt in ("BO1", "BO3", "BO5"):
            for cp in CP_LABELS:
                for stake in ("flat", "pct"):
                    specs.append(("format", {"side": side, "format": fmt, "cp": cp, "venue": "best", "stake": stake}))
    for cap in (0.60, 0.70, 0.80, 0.90):
        for k in (16, 32, 48):
            for cp in ("T-6h", "T-1h", "T-0"):
                for venue in VENUES:
                    specs.append(("elo_consensus", {"cap": cap, "k": k, "min_games": 5, "cp": cp, "venue": venue, "stake": "flat"}))
    for min_p in (0.50, 0.55, 0.60):
        for k in (16, 32, 48):
            for cp in ("T-6h", "T-1h", "T-0"):
                for venue in VENUES:
                    specs.append(("elo_contrarian", {"min_p": min_p, "k": k, "min_games": 5, "cp": cp, "venue": venue, "stake": "flat"}))
    for side in ("favorite", "underdog"):
        for tier in ("top", "other"):
            for cp in CP_LABELS:
                for venue in VENUES:
                    specs.append(("tier", {"side": side, "tier": tier, "cp": cp, "venue": venue, "stake": "flat"}))
    for spread in (0.02, 0.04, 0.06):
        for side in ("favorite", "underdog"):
            for cp in CP_LABELS:
                for stake in ("flat", "pct"):
                    specs.append(("tight_spread", {"max_spread": spread, "side": side, "cp": cp, "venue": "kalshi", "stake": stake}))
    for mode in ("follow", "fade"):
        for n in (2, 3, 4):
            for cp in ("T-6h", "T-1h", "T-0"):
                for venue in VENUES:
                    specs.append(("form_streak", {"mode": mode, "n": n, "cp": cp, "venue": venue, "stake": "flat"}))
    for hours in (6, 12):
        for only_dog in (False, True):
            for cp in ("T-6h", "T-1h", "T-0"):
                for venue in VENUES:
                    specs.append(("fatigue", {"hours": hours, "only_underdog": only_dog, "cp": cp, "venue": venue, "stake": "flat"}))
    for mode in ("repeat", "revenge"):
        for cp in ("T-6h", "T-1h", "T-0"):
            for venue in VENUES:
                specs.append(("head_to_head", {"mode": mode, "cp": cp, "venue": venue, "stake": "flat"}))
    for session in ("asia", "europe", "americas"):
        for side in ("favorite", "underdog"):
            for cp in CP_LABELS:
                specs.append(("session", {"session": session, "side": side, "cp": cp, "venue": "best", "stake": "flat"}))
    specs.append(("control_no_bet", {"cp": "T-0", "venue": "best", "stake": "flat"}))
    for seed in (1, 2, 3):
        for venue in VENUES:
            specs.append(("control_coin_flip", {"seed": seed, "cp": "T-0", "venue": venue, "stake": "flat"}))

    out, seen = [], set()
    order = list(range(len(ADJ) * len(NOUN)))
    # Deterministic, collision-free usernames.
    order.sort(key=lambda i: hashlib.sha256(f"user{i}".encode()).hexdigest())
    for i, (family, params) in enumerate(specs):
        canon = json.dumps({"family": family, "params": params}, sort_keys=True)
        digest = hashlib.sha256(canon.encode()).hexdigest()[:16]
        if digest in seen:
            raise ValueError(f"duplicate strategy definition {canon}")
        seen.add(digest)
        n = order[i % len(order)]
        username = f"sim_{ADJ[n // len(NOUN)]}{NOUN[n % len(NOUN)]}_{i + 1:04d}"
        out.append({"id": f"S{i + 1:04d}", "username": username, "family": family, "params": params,
                    "definition_hash": digest, "rule": describe(family, params)})
    return out


def describe(family: str, p: dict) -> str:
    tail = f" at {p['cp']} via {VENUES[p['venue']]}; stake {STAKES[p['stake']]}."
    if family == "price_band":
        who = "underdog" if p["hi"] <= 0.5 else "favorite"
        return f"Back the {who} when its market-implied probability is in [{p['lo']:.2f}, {p['hi']:.2f})" + tail
    if family == "elo_value":
        return (f"Back the side whose walk-forward Elo (K={p['k']}) probability exceeds the entry price by at least "
                f"{p['edge']:.2f} (both teams ≥{p['min_games']} prior settled matches)" + tail)
    if family == "line_move":
        if p["direction"] == "follow":
            rule = f"Follow steam: back the side whose implied probability ROSE by ≥{p['thr']:.2f}"
        else:
            rule = f"Fade the move: back the side whose implied probability FELL by ≥{p['thr']:.2f}"
        return f"{rule} between {p['from']} and {p['cp']} (same venue at both times)" + tail
    if family == "format":
        return f"Back the market {p['side']} in {p['format']} matches only (format from Polymarket title)" + tail
    if family == "elo_consensus":
        return (f"Back the favorite only when Elo (K={p['k']}) agrees and the entry price ≤ {p['cap']:.2f} "
                f"(both teams ≥{p['min_games']} matches)") + tail
    if family == "elo_contrarian":
        return (f"Back the market underdog when Elo (K={p['k']}) gives it ≥{p['min_p']:.2f} "
                f"(both teams ≥{p['min_games']} matches)") + tail
    if family == "tier":
        label = "top-tier (keyword heuristic: IEM/BLAST/ESL Pro League/PGL/Major/...)" if p["tier"] == "top" else "non-top-tier"
        return f"Back the market {p['side']} in {label} competitions" + tail
    if family == "tight_spread":
        return f"Back the market {p['side']} only when the Kalshi bid/ask spread on it is ≤ {p['max_spread']:.2f}" + tail
    if family == "form_streak":
        verb = "Back" if p["mode"] == "follow" else "Fade (back the opponent of)"
        return (f"{verb} a team on a ≥{p['n']}-match win streak (walk-forward, settled results only) "
                f"when its opponent is not on a win streak") + tail
    if family == "fatigue":
        dog = " only when the rested team is the market underdog" if p["only_underdog"] else ""
        return (f"Back the rested team when its opponent started another match within the previous {p['hours']}h "
                f"and it did not{dog}") + tail
    if family == "head_to_head":
        who = "last meeting's winner (repeat)" if p["mode"] == "repeat" else "last meeting's loser (revenge)"
        return f"Back the {who} when the two teams have a prior settled meeting in the dataset" + tail
    if family == "session":
        hours = SESSIONS[p["session"]]
        return (f"Back the market {p['side']} in matches starting {hours[0]:02d}:00–{hours[1]:02d}:00 UTC "
                f"({p['session']} session)") + tail
    if family == "control_no_bet":
        return "Control: never bets (bankroll must stay exactly 1,000u)."
    if family == "control_coin_flip":
        return f"Control: deterministic coin flip (seed {p['seed']}) on every match" + tail
    raise ValueError(family)


def decide(s: dict, m: dict, elo: dict) -> tuple[int, dict, float | None] | None:
    """(side, execution quote, model probability or None) or None. Uses only pre-checkpoint data."""
    fam, p = s["family"], s["params"]
    cp, venue = p["cp"], p["venue"]
    if fam == "control_no_bet":
        return None
    ref = reference_quotes(m, venue, cp)
    if ref is None:
        return None
    ia, ib = ref[0]["implied"], ref[1]["implied"]
    fav = 0 if ia > ib else 1 if ib > ia else None
    side, model = None, None
    if fam == "control_coin_flip":
        side = int(hashlib.sha256(f"{p['seed']}:{m['id']}".encode()).hexdigest(), 16) % 2
    elif fam == "price_band":
        if fav is None:
            return None
        side = fav if p["lo"] >= 0.5 else 1 - fav
        if not p["lo"] <= ref[side]["implied"] < p["hi"]:
            return None
    elif fam in ("elo_value", "elo_consensus", "elo_contrarian"):
        pa, ga, gb = elo[p["k"]][m["id"]][cp]
        if min(ga, gb) < p["min_games"]:
            return None
        probs = (pa, 1 - pa)
        if fam == "elo_value":
            edges = []
            for sd in (0, 1):
                q = execution_quote(m, venue, cp, sd)
                if q:
                    edges.append((probs[sd] - q["buy"], sd))
            if not edges:
                return None
            best_edge, side = max(edges)
            if best_edge < p["edge"] or best_edge <= 0 and p["edge"] == 0:
                return None
        elif fam == "elo_consensus":
            if fav is None or probs[fav] <= 0.5:
                return None
            side = fav
        else:
            if fav is None or probs[1 - fav] < p["min_p"]:
                return None
            side = 1 - fav
        model = probs[side]
    elif fam == "line_move":
        before = reference_quotes(m, venue, p["from"])
        if before is None or before[0]["venue"] != ref[0]["venue"]:
            return None
        delta = ia - before[0]["implied"]  # movement toward side 0
        if abs(delta) < p["thr"]:
            return None
        riser = 0 if delta > 0 else 1
        side = riser if p["direction"] == "follow" else 1 - riser
    elif fam == "format":
        if m["format"] != p["format"] or fav is None:
            return None
        side = fav if p["side"] == "favorite" else 1 - fav
    elif fam == "tier":
        if m["tier"] != p["tier"] or fav is None:
            return None
        side = fav if p["side"] == "favorite" else 1 - fav
    elif fam in ("form_streak", "fatigue", "head_to_head"):
        sa, sb, ga, gb, h2h = elo["form"][m["id"]][cp]
        if fam == "form_streak":
            hot = [sd for sd, (mine, theirs) in enumerate(((sa, sb), (sb, sa))) if mine >= p["n"] and theirs <= 0]
            if len(hot) != 1:
                return None
            side = hot[0] if p["mode"] == "follow" else 1 - hot[0]
        elif fam == "fatigue":
            tired = [g is not None and g <= p["hours"] for g in (ga, gb)]
            if tired.count(True) != 1:
                return None
            side = tired.index(False)
            if p["only_underdog"] and (fav is None or side == fav):
                return None
        else:
            if h2h is None:
                return None
            side = h2h if p["mode"] == "repeat" else 1 - h2h
    elif fam == "session":
        lo, hi = SESSIONS[p["session"]]
        if not lo <= datetime.fromtimestamp(m["cutoff"], tz=timezone.utc).hour < hi or fav is None:
            return None
        side = fav if p["side"] == "favorite" else 1 - fav
    elif fam == "tight_spread":
        if fav is None:
            return None
        side = fav if p["side"] == "favorite" else 1 - fav
        if ref[side]["spread"] is None or ref[side]["spread"] > p["max_spread"] + 1e-9:
            return None
    if side is None:
        return None
    q = execution_quote(m, venue, cp, side)
    if q is None:
        return None
    if fam == "elo_consensus" and q["buy"] > p["cap"]:
        return None
    return side, q, model


def stake_for(s: dict, cash: float, q: dict, model: float | None) -> float:
    return min(MAX_STAKE, _stake(s, cash, q, model))


def _stake(s: dict, cash: float, q: dict, model: float | None) -> float:
    kind = s["params"]["stake"]
    if kind == "flat":
        return 10.0
    if kind == "pct":
        return 0.02 * cash
    if kind == "fixed_win":
        return min(50.0, 10.0 * q["buy"] / (1 - q["buy"]))
    if kind == "kelly":
        if model is None or model <= q["buy"]:
            return 0.0
        f = (model - q["buy"]) / (1 - q["buy"])
        return min(0.05 * cash, 0.25 * f * cash)
    raise ValueError(kind)


# --------------------------------------------------------------------------- simulation

def downsample(curve: list[float], n: int) -> list[float]:
    """Evenly spaced equity points (always keeps first and last) for leaderboard sparklines."""
    if len(curve) <= n:
        return [round(x, 1) for x in curve]
    step = (len(curve) - 1) / (n - 1)
    return [round(curve[round(i * step)], 1) for i in range(n)]


def simulate(s: dict, matches: list[dict], elo: dict) -> tuple[list[list], dict]:
    cp = s["params"]["cp"]
    cash = START_BANKROLL
    open_pos: list[tuple[int, int, float]] = []  # heap of (settle_ts, bet_index, payout)
    locked = 0.0  # cost + fee of open positions
    bets: list[list] = []
    skipped = 0
    curve = [START_BANKROLL]
    ordered = sorted(matches, key=lambda m: (m["cutoff"] - CP_BACK[cp], m["id"]))

    def settle_until(t: int) -> None:
        nonlocal cash, locked
        while open_pos and open_pos[0][0] <= t:
            _, idx, payout = heapq.heappop(open_pos)
            cash = r4(cash + payout)
            locked = r4(locked - bets[idx][6] - bets[idx][7])
            bets[idx][-1] = r4(cash + locked)  # equity (open positions at cost) after this settlement
            curve.append(bets[idx][-1])

    for m in ordered:
        decision_t = m["cutoff"] - CP_BACK[cp]
        settle_until(decision_t)
        d = decide(s, m, elo)
        if d is None:
            continue
        side, q, model = d
        if q["t"] > decision_t:  # defensive: quote must not postdate the decision time
            raise AssertionError(f"look-ahead quote in {s['id']} {m['id']}")
        stake = stake_for(s, cash, q, model)
        pos = position(q["venue"], stake, q["buy"]) if stake >= 1 else None
        if pos is None:
            continue
        contracts, cost, fee = pos
        if cost + fee > cash + 1e-9:
            skipped += 1
            continue
        cash = r4(cash - cost - fee)
        locked = r4(locked + cost + fee)
        payout = r4(contracts * q["settle"])
        pnl = r4(payout - cost - fee)
        # [match_idx, venue, side, quote_t, price, contracts, cost, fee, settle, payout, pnl, model, equity]
        bets.append([m["idx"], q["venue"][0], side, q["t"], q["buy"], contracts, cost, fee, q["settle"], payout, pnl,
                     None if model is None else round(model, 4), None])
        heapq.heappush(open_pos, (m["settled"], len(bets) - 1, payout))
    settle_until(2 ** 62)
    return bets, {"skipped_insufficient_cash": skipped, "curve": curve, "final": cash}


def metrics(bets: list[list], matches: list[dict], closing: dict, final: float | None = None, curve=None) -> dict:
    n = len(bets)
    staked = sum(b[6] for b in bets)
    fees = sum(b[7] for b in bets)
    pnl = sum(b[10] for b in bets)
    wins = sum(1 for b in bets if b[8] == 1.0)
    losses = sum(1 for b in bets if b[8] == 0.0)
    exp_pnl = var = 0.0
    clv = []
    for b in bets:
        price, c = b[4], b[5]
        exp_pnl += -b[7]
        var += c * c * price * (1 - price)
        close = closing.get((b[0], b[1], b[2]))
        if close is not None:
            clv.append(close - price)
    z = (pnl - exp_pnl) / math.sqrt(var) if var > 0 else None
    out = {
        "bets": n, "wins": wins, "losses": losses, "other_settlements": n - wins - losses,
        "staked": r4(staked), "fees": r4(fees), "pnl": r4(pnl),
        "roi": round(pnl / (staked + fees), 4) if staked + fees > 0 else None,
        "win_rate": round(wins / n, 4) if n else None,
        "avg_price": round(sum(b[4] for b in bets) / n, 4) if n else None,
        "avg_clv": round(sum(clv) / len(clv), 4) if clv else None,
        "z_vs_price": round(z, 3) if z is not None else None,
        "p_value": round(1 - norm_cdf(z), 6) if z is not None else None,
    }
    if curve is not None:
        peak, mdd = START_BANKROLL, 0.0
        for v in curve:
            peak = max(peak, v)
            mdd = max(mdd, (peak - v) / peak if peak else 0)
        out["max_drawdown"] = round(mdd, 4)
        out["final_bankroll"] = r4(final)
    return out


def closing_prices(matches: list[dict]) -> dict:
    """T-0 buy price per (match_idx, venue initial, side) — the closing line for CLV."""
    out = {}
    for m in matches:
        for venue in m["lines"]:
            for side in (0, 1):
                q = match_quote(m, venue, "T-0", side)
                if q:
                    out[(m["idx"], venue[0], side)] = q["buy"]
    return out


def calibration(matches: list[dict]) -> list[dict]:
    rows = []
    for venue in ("kalshi", "polymarket"):
        for label in CP_LABELS:
            buckets = defaultdict(lambda: {"n": 0, "wins": 0, "implied": 0.0, "buy": 0.0, "pnl": 0.0, "cost": 0.0})
            for m in matches:
                if m["winner"] is None or venue not in m["lines"]:
                    continue
                for side in (0, 1):
                    q = match_quote(m, venue, label, side)
                    if not q:
                        continue
                    b = min(9, int(q["implied"] * 10))
                    cell = buckets[b]
                    cell["n"] += 1
                    cell["wins"] += int(q["settle"] == 1.0)
                    cell["implied"] += q["implied"]
                    cell["buy"] += q["buy"]
                    pos = position(venue, 10.0, q["buy"])
                    if pos:
                        c, cost, fee = pos
                        cell["pnl"] += c * q["settle"] - cost - fee
                        cell["cost"] += cost + fee
            for b in sorted(buckets):
                c = buckets[b]
                rows.append({"venue": venue, "checkpoint": label, "bucket": f"{b / 10:.1f}-{(b + 1) / 10:.1f}",
                             "n": c["n"], "win_rate": round(c["wins"] / c["n"], 4),
                             "avg_implied": round(c["implied"] / c["n"], 4), "avg_buy": round(c["buy"] / c["n"], 4),
                             "flat_roi_after_fees": round(c["pnl"] / c["cost"], 4) if c["cost"] else None})
    return rows


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    mid = len(xs) // 2
    return round(xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2, 4)


def group_summary(rows: list[dict], key) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = []
    for k, rs in sorted(groups.items()):
        active = [r for r in rs if r["all"]["bets"] >= QUALIFY_BETS]
        out.append({"group": k, "strategies": len(rs), "qualified": len(active),
                    "median_roi": median([r["all"]["roi"] for r in active]),
                    "best_roi": max((r["all"]["roi"] for r in active), default=None),
                    "share_profitable": round(sum(r["all"]["pnl"] > 0 for r in active) / len(active), 4) if active else None,
                    "median_test_roi": median([r["test"]["roi"] for r in active if r["test"]["bets"] >= 10])})
    return out


def run(lab: Path) -> dict:
    store = load_store(lab)
    lines = store["lines"]
    matches, irregular = build_matches(lines)
    for i, m in enumerate(matches):
        m["idx"] = i
        cache = {}
        for venue in m["lines"]:
            for label in CP_LABELS:
                for side in (0, 1):
                    q = match_quote(m, venue, label, side)
                    # A linked match uses the EARLIEST venue start as its cutoff; a quote measured from
                    # the other venue's later start could be in-play, so it is unavailable here.
                    if q and q["t"] <= m["cutoff"] - CP_BACK[label]:
                        cache[(venue, label, side)] = q
                    elif q:
                        m.setdefault("_dropped_late_quotes", 0)
                        m["_dropped_late_quotes"] += 1
        m["_q"] = cache
    elo = elo_tables(matches)
    elo["form"] = form_tables(matches)
    closing = closing_prices(matches)
    strategies = strategy_universe()
    cutoffs = sorted(m["cutoff"] for m in matches)
    split_ts = cutoffs[int(len(cutoffs) * TRAIN_FRACTION)] if cutoffs else 0
    rows, ledgers, fingerprints_sel, fingerprints_full = [], {}, set(), set()
    for s in strategies:
        bets, info = simulate(s, matches, elo)
        train = [b for b in bets if matches[b[0]]["cutoff"] < split_ts]
        test = [b for b in bets if matches[b[0]]["cutoff"] >= split_ts]
        row = {"id": s["id"], "username": s["username"], "family": s["family"], "venue": s["params"]["venue"],
               "checkpoint": s["params"]["cp"], "stake": s["params"]["stake"],
               "all": metrics(bets, matches, closing, info["final"], info["curve"]),
               "train": metrics(train, matches, closing), "test": metrics(test, matches, closing),
               "skipped_insufficient_cash": info["skipped_insufficient_cash"],
               "spark": downsample(info["curve"], 24)}
        sel = hashlib.sha256(json.dumps([[b[0], b[1], b[2]] for b in bets]).encode()).hexdigest()
        full = hashlib.sha256(json.dumps([[b[0], b[1], b[2], b[6]] for b in bets]).encode()).hexdigest()
        row["selection_fingerprint"] = sel[:16]
        if bets:
            fingerprints_sel.add(sel)
            fingerprints_full.add(full)
        rows.append(row)
        ledgers[s["id"]] = bets
    rows.sort(key=lambda r: (-r["all"]["final_bankroll"], r["id"]))
    for rank, r in enumerate(rows, 1):
        r["rank"] = rank
        r["qualified"] = r["all"]["bets"] >= QUALIFY_BETS

    n_strat = len(strategies)
    qualified = [r for r in rows if r["qualified"]]
    tested = [r for r in qualified if r["all"]["p_value"] is not None]
    bonf = 0.05 / max(1, len(tested))
    train_test = [(r["train"]["roi"], r["test"]["roi"]) for r in qualified
                  if r["train"]["bets"] >= 20 and r["test"]["bets"] >= 10]
    top_train = sorted((r for r in qualified if r["train"]["bets"] >= 20 and r["test"]["bets"] >= 10),
                       key=lambda r: -r["train"]["roi"])[:20]
    venues = Counter(l["venue"] for l in lines)
    flags = Counter(f for l in lines for f in l["flags"])
    meta = {k: store.get(k) for k in ("last_run_utc", "mode", "coverage", "errors")}
    dataset = {
        "lines_total": len(lines), "lines_by_venue": dict(venues), "line_flags": dict(flags),
        "matches_simulated": len(matches),
        "matches_cross_venue": sum(1 for m in matches if len(m["lines"]) == 2),
        "matches_cross_checked_results": sum(1 for m in matches if m["cross_checked"]),
        "venue_result_conflicts": sum(1 for x in irregular if x["type"] == "venue_result_conflict"),
        "quotes_dropped_after_match_cutoff": sum(m.get("_dropped_late_quotes", 0) for m in matches),
        "first_cutoff_utc": iso(cutoffs[0]) if cutoffs else None,
        "last_cutoff_utc": iso(cutoffs[-1]) if cutoffs else None,
        "train_test_split_utc": iso(split_ts) if cutoffs else None,
        "excluded_by_venue": {v: len(x) for v, x in (store.get("excluded") or {}).items()},
        "excluded_reasons": dict(Counter(re.sub(r"[\d.:'\"\[\]{}]+", "#", reason)[:80]
                                         for bucket in (store.get("excluded") or {}).values() for reason in bucket.values()).most_common(15)),
        "collector": meta,
    }
    analytics = {
        "schema_version": 1,
        "simulated": True,
        "generated_from_lines_run_utc": store.get("last_run_utc"),
        "dataset": dataset,
        "distinctness": {
            "strategy_definitions": n_strat,
            "unique_definition_hashes": len({s["definition_hash"] for s in strategies}),
            "strategies_with_bets": sum(1 for r in rows if r["all"]["bets"]),
            "unique_bet_selection_sets": len(fingerprints_sel),
            "unique_ledgers_incl_stakes": len(fingerprints_full),
            "qualified_strategies_min_bets": QUALIFY_BETS,
            "qualified": len(qualified),
        },
        "multiple_testing": {
            "tested": len(tested),
            "p_below_0_05": sum(1 for r in tested if r["all"]["p_value"] < 0.05),
            "expected_false_positives_at_0_05": round(0.05 * len(tested), 1),
            "bonferroni_threshold": bonf,
            "pass_bonferroni": sum(1 for r in tested if r["all"]["p_value"] < bonf),
            "note": ("z compares realised P/L with what the entry prices themselves imply (fair-price null). With "
                     "hundreds of correlated strategies, some will look 'significant' by chance; only Bonferroni "
                     "survivors that also hold up out-of-sample deserve further forward testing."),
        },
        "out_of_sample": {
            "spearman_train_vs_test_roi": spearman([a for a, _ in train_test], [b for _, b in train_test]),
            "pairs": len(train_test),
            "top20_by_train_roi_mean_train": round(sum(r["train"]["roi"] for r in top_train) / len(top_train), 4) if top_train else None,
            "top20_by_train_roi_mean_test": round(sum(r["test"]["roi"] for r in top_train) / len(top_train), 4) if top_train else None,
        },
        "calibration": calibration(matches),
        "by_family": group_summary(rows, lambda r: r["family"]),
        "by_venue": group_summary(rows, lambda r: r["venue"]),
        "by_checkpoint": group_summary(rows, lambda r: r["checkpoint"]),
        "by_stake": group_summary(rows, lambda r: r["stake"]),
        "irregularities": irregular[:500],
        "irregularities_total": len(irregular),
        "assumptions": [
            "Kalshi entry = yes_ask close of the last hourly candle at/before the checkpoint (≤90 min old); requires bid>0 and spread ≤0.10. Depth unknown: fills assumed at that ask.",
            "Polymarket entry = CLOB prices-history reference price + 0.01 slippage (≤90 min old); p must be in [0.02,0.98] and the two outcomes must sum within 0.05 of 1.",
            "Kalshi contracts are integers; Polymarket shares round down to 0.01. Fees: Kalshi round-up(0.07·C·P·(1−P)); Polymarket 0.05·C·p·(1−p) (current sports rate applied to all dates).",
            "Cutoff = earliest credible scheduled start (Kalshi rules time cross-checked with the ticker clock; Polymarket min(gameStartTime, description time)). Checkpoints are measured back from it.",
            "Elo is walk-forward: only matches whose venue settlement timestamp precedes the decision time update ratings. Team identity = normalised venue team name (renames/rosters not modelled).",
            "Cash is locked at entry and released at the venue settlement timestamp. Start 1,000 units per simulated user. Settlement uses the venue's final value, including 50/50 or fair-price outcomes.",
            f"Every bet is capped at {MAX_STAKE:.0f} units because order-book depth at the quote time is unknown; sizing cannot compound into fills the market may not have offered.",
            "Tier is a keyword heuristic on the competition name; format is known only when Polymarket's title states BO1/BO3/BO5.",
        ],
    }
    featured = set()
    for r in qualified[:30]:                       # top of the competition leaderboard
        featured.add(r["id"])
    oos = [r for r in qualified if r["test"]["bets"] >= 10 and r["test"]["roi"] is not None]
    for r in sorted(oos, key=lambda r: (-r["test"]["roi"], r["id"]))[:20]:   # best out-of-sample
        featured.add(r["id"])
    for r in qualified[-10:]:                      # bottom of the leaderboard
        featured.add(r["id"])
    for fam in {r["family"] for r in rows}:
        best = next((r for r in rows if r["family"] == fam and (r["qualified"] or fam.startswith("control"))), None)
        if best:
            featured.add(best["id"])
    for r in rows:
        r["ledger_published"] = r["id"] in featured
    return {"strategies": strategies, "rows": rows, "analytics": analytics, "matches": matches,
            "ledgers": {k: v for k, v in ledgers.items() if k in featured}, "all_ledgers": ledgers}


def write(lab: Path, result: dict) -> None:
    def dump(path: Path, doc, pretty=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1 if pretty else None,
                                   separators=None if pretty else (",", ":")) + "\n", encoding="utf-8")

    header = {"schema_version": 1, "simulated": True, "start_bankroll": START_BANKROLL,
              "generated_from_lines_run_utc": result["analytics"]["generated_from_lines_run_utc"]}
    dump(lab / "strategies.json", dict(header, strategies=result["strategies"]))
    # One row per line: daily re-commits delta-compress in git instead of rewriting one huge line.
    head = json.dumps(dict(header, qualify_bets=QUALIFY_BETS), ensure_ascii=False, separators=(",", ":"))[:-1]
    body = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in result["rows"])
    (lab / "leaderboard.json").write_text(head + ',"rows":[\n' + body + "\n]}\n", encoding="utf-8")
    dump(lab / "analytics.json", result["analytics"], pretty=True)
    table = [{"id": m["id"], "teams": m["teams"], "competition": m["competition"], "format": m["format"],
              "tier": m["tier"], "cutoff_utc": iso(m["cutoff"]), "settled_utc": iso(m["settled"]), "winner": m["winner"],
              "cross_checked": m["cross_checked"],
              "lines": {v: {"line_id": l["line_id"], "side_map": m["align"][v], "price_urls": l["price_urls"],
                            "market_urls": l["market_urls"], "review_url": l["review_url"]} for v, l in m["lines"].items()}}
             for m in result["matches"]]
    dump(lab / "matches.json", dict(header, matches=table))
    led_dir = lab / "ledgers"
    led_dir.mkdir(parents=True, exist_ok=True)
    for old in led_dir.glob("S*.json"):
        old.unlink()
    cols = ["match_idx", "venue", "side", "quote_t", "price", "contracts", "cost", "fee", "settle", "payout", "pnl",
            "model_prob", "equity_after_settle"]
    for sid, bets in result["ledgers"].items():
        dump(led_dir / f"{sid}.json", dict(header, strategy_id=sid, columns=cols, bets=bets))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lab-dir", type=Path, default=LAB)
    ap.add_argument("--ledger", help="print the full ledger of one strategy id (any strategy, not only featured)")
    args = ap.parse_args(argv)
    result = run(args.lab_dir)
    if args.ledger:
        print(json.dumps(result["all_ledgers"][args.ledger]))
        return 0
    write(args.lab_dir, result)
    d = result["analytics"]["distinctness"]
    print(f"Strategy lab: {d['strategy_definitions']} strategies ({d['unique_bet_selection_sets']} unique bet "
          f"selections, {d['qualified']} qualified) over {result['analytics']['dataset']['matches_simulated']} matches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
