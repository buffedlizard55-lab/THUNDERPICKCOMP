"""Conservative, reproducible paper-trade engine for the outright strategy.

Never infers an executable fill, uses a resolved/post-event price, or settles a
position. Rules for other usernames remain published but inactive until a
verified fixture/result pipeline exists. Everything here is simulated.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .collect import MAX_QUOTE_AGE, SourceError, money, parse_time, sha, stamp

ROOT = Path(__file__).resolve().parent.parent
END_BEFORE = datetime(2026, 10, 14, tzinfo=timezone.utc)  # event begins Oct 14 (day, UTC)
MAX_DECISION_LAG = timedelta(minutes=2)
MAX_PAIR_SKEW = timedelta(seconds=60)


def eligible_outright(quote: dict, event: dict, now: datetime) -> bool:
    """An *observed ask*, not a completed trade or a prediction of the winner."""
    if event.get("status") != "open" or event.get("stage") == "qualifier/series":
        return False
    title = str(event.get("title", "")).lower()
    if "thunderpick world championship" not in title or "2026" not in title:
        return False
    question = str(quote.get("market_title", "")).lower()
    # Most CS2 events at both venues name teams as "A vs B". Even if that
    # event is at the Finals, a match-winner contract is NOT a tournament-
    # winner outright. The two markets must never be interchanged.
    if re.search(r"\bvs\.?\b", title) or "closed qualifier" in title:
        return False
    if re.search(r"\b(map|match|game)\b", question):
        return False
    if quote.get("quote_status") != "fresh":
        return False
    observed = parse_time(quote["observed_utc"])
    if observed > now or now - observed > MAX_DECISION_LAG:
        return False
    if quote.get("venue") == "Kalshi" and quote.get("market_type") != "tournament winner":
        return False
    if quote.get("venue") == "Polymarket (international)" and not (
        re.search(r"\b(winner|champion|win)\b", title) or
        re.search(r"\btournament\s+winner\b", question) or
        ("championship" in question and re.search(r"\b(winner|champion|win)\b", question))
    ):
        return False
    if parse_time(quote["source_updated_utc"]) > now or now - parse_time(quote["source_updated_utc"]) > MAX_QUOTE_AGE:
        return False
    return now < END_BEFORE


def pick(qs: list[dict], stake: Decimal, name: str) -> dict | None:
    # Only an explicitly named team's Yes contract/outcome is eligible. No
    # guessing from a binary market's 'No' or a common team-name substring.
    candidates = []
    for q in qs:
        selected = str(q.get("selection", "")).strip().lower()
        if selected not in {name.lower(), name.lower() + " wins"}:
            continue
        price = money(q["raw_price"], "ask")
        size = money(q.get("ask_size"), "ask_size") if q.get("ask_size") is not None else Decimal(0)
        if not Decimal(0) < price < Decimal(1) or size < stake / price:
            continue
        candidates.append((price, q["market_id"], q))
    return min(candidates, key=lambda item: (item[0], item[1]))[2] if candidates else None


def decision(quote: dict, username: str, stake: Decimal, now: datetime) -> dict:
    p = money(quote["raw_price"], "ask")
    odds = Decimal(1) / p
    return {
        "entry_id": "SIM-" + sha(username + "|" + quote["event_key"] + "|" + quote["selection"]),
        "username": username,
        "match_id": "TWC26-FINALS-CHAMPION",  # outright, not a scheduled match
        "event_key": quote["event_key"],
        "market": quote["market_title"],
        "selection": quote["selection"],
        "decimal_odds": str(odds.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)),
        "stake": str(stake.quantize(Decimal("0.01"))),
        "placed_utc": stamp(now),
        "simulated": True,
        "fill_policy": "SIMULATED paper decision at first-party observed best ask; no real order/fill. Fee and slippage excluded; gross payout in units, size checked against top-of-book shares/contracts.",
        "price_source": {
            "venue": quote["venue"], "market_id": quote["market_id"],
            "url": quote["source_url"], "event_url": quote["event_url"],
            "raw_price": quote["raw_price"], "price_unit": quote["price_unit"],
            "ask_size": quote["ask_size"], "quote_id": quote["quote_id"],
            "observed_utc": quote["observed_utc"],
            "source_updated_utc": quote["source_updated_utc"],
        },
        "settlement": {
            "result": "pending", "rule": quote["resolution_rule"],
            "settled_utc": None, "result_source": None,
        },
        "payout": None, "profit": None,
    }


def apply_outright(ledger: dict, observations: dict, now: datetime) -> list[dict]:
    """Append the two correlated positions atomically, or append nothing."""
    if observations.get("mode") != "live" or observations.get("last_completed_utc") != stamp(now):
        return []  # offline replay and stale observations can NEVER create positions
    started = parse_time(observations["last_attempt_utc"])
    if started > now:
        raise SourceError("collection finished before it started")
    username = "sim_champ_correlation"
    existing = [e for e in ledger["entries"] if e.get("username") == username]
    if existing:
        return []  # one-shot strategy; settlement is a separate verified step
    events = {e["key"]: e for e in observations["events"]}
    qs = [q for q in observations["quotes"] if q.get("event_key") in events and
          parse_time(q["observed_utc"]) >= started and
          eligible_outright(q, events[q["event_key"]], now)]
    stake = Decimal("50.00")
    furia, falcons = pick(qs, stake, "FURIA"), pick(qs, stake, "Falcons")
    if not furia or not falcons:
        return []
    if abs(parse_time(furia["observed_utc"]) - parse_time(falcons["observed_utc"])) > MAX_PAIR_SKEW:
        return []  # different enough in time that prices cannot be compared as one pair
    if furia["market_id"] == falcons["market_id"]:
        raise SourceError("two teams mapped to same contract; refuse to paper-trade")
    placed = [decision(furia, username, stake, now), decision(falcons, username, stake, now)]
    if any(e["entry_id"] in {row["entry_id"] for row in ledger["entries"]} for e in placed):
        raise SourceError("duplicate entry id")
    ledger["entries"].extend(placed)
    ledger["meta"]["last_updated_utc"] = stamp(now)
    return placed


def main() -> int:
    # The collector must have run in the SAME job, and observations must have
    # come from live primary APIs. A workflow failure blocks publication.
    observations = json.loads((ROOT / "data" / "observations.json").read_text(encoding="utf-8"))
    ledger_path = ROOT / "data" / "ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    now = parse_time(observations["last_completed_utc"])
    if abs((datetime.now(timezone.utc) - now).total_seconds()) > 300:
        raise SourceError("paper-trade engine requires a freshly collected live snapshot")
    entries = apply_outright(ledger, observations, now)
    if entries:
        tmp = ledger_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(ledger_path)
    print(f"Simulated outright positions appended: {len(entries)}; prior positions retained: {len(ledger['entries']) - len(entries)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
