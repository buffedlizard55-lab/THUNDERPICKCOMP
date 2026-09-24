"""Conservative, reproducible paper-trade engine for the outright strategy.

Never infers an executable fill, uses a resolved/post-event price, or settles a
position. Match strategies additionally require a *double-sourced* fixture
(HLTV + Liquipedia agreement on HLTV id, teams and UTC date), a strictly
pre-start fresh first-party ask with enough top-of-book size, and an
unambiguous quote-to-fixture association. Everything here is simulated.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .collect import MAX_QUOTE_AGE, SourceError, canonical_team, money, parse_time, sha, stamp

ROOT = Path(__file__).resolve().parent.parent
END_BEFORE = datetime(2026, 10, 14, tzinfo=timezone.utc)  # event begins Oct 14 (day, UTC)
MAX_DECISION_LAG = timedelta(minutes=2)
MAX_PAIR_SKEW = timedelta(seconds=60)
MATCH_ASSOCIATION_WINDOW = timedelta(hours=12)  # quote-time to fixture-start association
MATCH_BANKROLL = Decimal("1000.00")  # pending-stake budget per simulated user


def team_ranks(teams: list[dict]) -> dict:
    """Dated Sep-16 organizer VRS reveal rank per finalist id (data/teams.json)."""
    ranks = {}
    for t in teams:
        rank = t.get("vrs_rank_2026_09_16")
        if not isinstance(rank, int) or rank <= 0:
            raise SourceError("teams.json is missing the dated Sep-16 VRS rank needed by match strategies")
        ranks[t["id"]] = rank
    return ranks


def canonical_pair(title: str, ranks: dict) -> frozenset | None:
    """The finalist id pair an event/market title names, else None."""
    names = re.split(r"\s+vs\.?\s+", str(title), flags=re.I)
    if len(names) != 2:
        return None
    id_by_name = {}
    for team_id in ranks:
        id_by_name[re.sub(r"[^a-z0-9]", "", team_id.lower())] = team_id
    id_by_name.update({"virtuspro": "virtuspro", "vp": "virtuspro", "betboom": "betboom",
                       "aurora": "aurora", "falcons": "falcons", "9z": "9z"})
    a = id_by_name.get(re.sub(r"[^a-z0-9]", "", names[0].lower()))
    b = id_by_name.get(re.sub(r"[^a-z0-9]", "", names[1].lower()))
    if not a or not b or a == b:
        return None
    return frozenset((a, b))


def display_name(team_id: str, teams: list[dict]) -> str:
    for t in teams:
        if t["id"] == team_id:
            return t["name"]
    raise SourceError("unknown finalist id " + str(team_id))


def eligible_match_quote(q: dict, fixture: dict, event: dict, now: datetime, stake: Decimal,
                         fixtures: list[dict], events_by_key: dict) -> bool:
    """A fresh, pre-start, first-party match-winner ask associated with THIS fixture."""
    if q.get("quote_status") != "fresh" or q.get("event_key") not in events_by_key:
        return False
    if event.get("status") != "open" or event.get("stage") == "qualifier/series":
        return False
    question = str(q.get("market_title", "")).lower()
    title = str(event.get("title", "")).lower()
    # A map/game market is never the series match-winner.
    if re.search(r"\bmap\b|\bgame\b|pistol|round\b", question):
        return False
    if q.get("venue") == "Kalshi" and q.get("market_type") != "match winner":
        return False
    observed = parse_time(q["observed_utc"])
    if observed > now or now - observed > MAX_DECISION_LAG:
        return False
    if parse_time(q["source_updated_utc"]) > now or now - parse_time(q["source_updated_utc"]) > MAX_QUOTE_AGE:
        return False
    scheduled = parse_time(fixture["scheduled_utc"])
    if not now < scheduled or observed >= scheduled:
        return False  # strictly pre-start decisions only; never after first map
    # Associate the quote with exactly one fixture of the same pair near this time.
    pair = frozenset((fixture["team_a"], fixture["team_b"]))
    near = [f for f in fixtures
            if frozenset((f["team_a"], f["team_b"])) == pair
            and abs(parse_time(f["scheduled_utc"]) - observed) <= MATCH_ASSOCIATION_WINDOW
            and f["status"] != "conflict"]
    if len(near) != 1 or near[0]["id"] != fixture["id"]:
        return False
    price = money(q["raw_price"], "ask")
    if not Decimal(0) < price < Decimal(1):
        return False
    size = money(q.get("ask_size"), "ask_size") if q.get("ask_size") is not None else Decimal(0)
    return size >= stake / price  # pre-start depth check for the modeled amount


def best_ask(qs: list[dict], team_id: str, teams: list[dict]) -> dict | None:
    """Lowest eligible ask explicitly naming this finalist (market id breaks ties).

    Selections are matched canonically (display name or known alias, e.g.
    'Falcons' for Team Falcons), never by substring guessing."""
    candidates = []
    for q in qs:
        selection = str(q.get("selection", "")).strip()
        if canonical_team(selection, teams) != team_id and canonical_team(selection + " wins", teams) != team_id:
            continue
        candidates.append((money(q["raw_price"], "ask"), q["market_id"], q))
    return min(candidates, key=lambda item: (item[0], item[1]))[2] if candidates else None


def match_decision(quote: dict, fixture: dict, username: str, stake: Decimal, now: datetime) -> dict:
    p = money(quote["raw_price"], "ask")
    odds = Decimal(1) / p
    return {
        "entry_id": "SIM-" + sha(username + "|" + fixture["id"] + "|" + quote["selection"]),
        "username": username,
        "match_id": fixture["id"],  # double-sourced fixture, not an outright reference
        "event_key": quote["event_key"],
        "market": quote["market_title"],
        "selection": quote["selection"],
        "decimal_odds": str(odds.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)),
        "stake": str(stake.quantize(Decimal("0.01"))),
        "placed_utc": stamp(now),
        "simulated": True,
        "fill_policy": "SIMULATED paper decision at first-party observed best ask; no real order/fill. Fee and slippage excluded; gross payout in units, size checked against top-of-book shares/contracts.",
        "fixture": {
            "id": fixture["id"], "team_a": fixture["team_a"], "team_b": fixture["team_b"],
            "scheduled_utc": fixture["scheduled_utc"], "group": fixture.get("group"),
            "stage_label": fixture.get("stage_label"),
            "crosscheck": {"fixture_status": fixture["status"], "result_status": fixture.get("result_status", "none"),
                           "sources": [fixture["liquipedia_url"], fixture["source_url"]]},
        },
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


def group_openers(fixtures: list[dict]) -> set:
    """Earliest scheduled-confirmed fixture per group label (deterministic)."""
    by_group = {}
    for f in fixtures:
        if f.get("status") == "scheduled-confirmed" and f.get("stage_label") == "groups" and f.get("group"):
            key = f["group"]
            if key not in by_group or (f["scheduled_utc"], f["id"]) < (by_group[key]["scheduled_utc"], by_group[key]["id"]):
                by_group[key] = f
    return {f["id"] for f in by_group.values()}


def confirmed_group_losses(fixtures: list[dict], team_id: str) -> int:
    losses = 0
    for f in fixtures:
        result = f.get("result") or {}
        if (f.get("result_status") == "confirmed" and f.get("stage_label") == "groups"
                and team_id in (f["team_a"], f["team_b"]) and result.get("winner") and result["winner"] != team_id):
            losses += 1
    return losses


def apply_match_strategies(ledger: dict, observations: dict, now: datetime,
                           teams: list[dict], strategies: list[dict]) -> list[dict]:
    """Run the six published match policies under double-source + depth gates.

    Nothing here invents an opponent, a result, or a price: fixtures must be
    cross-confirmed by both HLTV and Liquipedia, and every decision references
    an immutable same-run first-party ask with enough pre-start size. If no
    eligible fixture/quote exists, no position is created.
    """
    if observations.get("mode") != "live" or observations.get("last_completed_utc") != stamp(now):
        return []  # offline replay and stale observations can NEVER create positions
    ranks = team_ranks(teams)
    fixtures = [f for f in observations["fixtures"] if f.get("status") == "scheduled-confirmed"]
    if not fixtures:
        return []
    events_by_key = {e["key"]: e for e in observations["events"]}
    quotes = observations["quotes"]
    settings = {s["username"]: s for s in strategies}
    openers = group_openers(observations["fixtures"])
    placed = []
    existing_ids = {e["entry_id"] for e in ledger["entries"]}
    for username, stake, rule in (
        ("sim_favorite_backer", Decimal("25.00"), "favorite"),
        ("sim_underdog_hunter", Decimal("15.00"), "underdog"),
        ("sim_vrs_value", Decimal("20.00"), "value"),
        ("sim_cache_chaos", Decimal("12.00"), "chaos"),
        ("sim_qualifier_fade", Decimal("20.00"), "fade"),
        ("sim_contrarian_cap", Decimal("10.00"), "contrarian"),
    ):
        policy = settings.get(username)
        if not policy or policy.get("status") != "active":
            continue
        declared = money(policy.get("stake_units"), username + ".stake_units")
        if declared != stake:
            raise SourceError(f"{username}: engine stake {stake} disagrees with published stake_units {declared}")
        pending = sum((money(e["stake"], "stake") for e in ledger["entries"]
                       if e.get("username") == username and (e.get("settlement") or {}).get("result") == "pending"),
                      Decimal(0))
        entries = []
        for fixture in sorted(fixtures, key=lambda f: (f["scheduled_utc"], f["id"])):
            candidates = [q for q in quotes
                          if eligible_match_quote(q, fixture, events_by_key.get(q.get("event_key"), {}), now, stake,
                                                  observations["fixtures"], events_by_key)]
            if not candidates:
                continue
            rank_a, rank_b = ranks[fixture["team_a"]], ranks[fixture["team_b"]]
            favorite_id, underdog_id = ((fixture["team_a"], fixture["team_b"]) if rank_a < rank_b
                                        else (fixture["team_b"], fixture["team_a"]) if rank_b < rank_a else (None, None))
            target = None
            if rule == "favorite":
                target = favorite_id
            elif rule == "underdog":
                target = underdog_id
            elif rule == "value":
                # PUBLISHED HEURISTIC (labeled as analysis, not fact):
                # fair(favorite) = min(85%, 50% + 2.5%/rank gap); bet a side whose
                # market-implied probability is >= 8 points below its fair value.
                if favorite_id is None:
                    continue
                gap = abs(rank_a - rank_b)
                fair_fav = min(Decimal("85"), Decimal("50") + Decimal("2.5") * gap)
                fair_under = Decimal("100") - fair_fav
                for side, fair in ((favorite_id, fair_fav), (underdog_id, fair_under)):
                    q = best_ask(candidates, side, teams)
                    if q and money(q["raw_price"], "ask") * 100 <= fair - Decimal("8"):
                        target = side
                        break
            elif rule == "chaos":
                if fixture["id"] not in openers or underdog_id is None:
                    continue
                target = underdog_id
            elif rule == "fade":
                if "virtuspro" not in (fixture["team_a"], fixture["team_b"]):
                    continue
                if fixture.get("stage_label") != "groups":
                    continue
                if confirmed_group_losses(observations["fixtures"], "virtuspro") >= 2:
                    continue  # VP eliminated per double-sourced group results
                target = fixture["team_b"] if fixture["team_a"] == "virtuspro" else fixture["team_a"]
            elif rule == "contrarian":
                if underdog_id is None:
                    continue
                q = best_ask(candidates, underdog_id, teams)
                if q and Decimal(1) / money(q["raw_price"], "ask") >= Decimal("3.00"):
                    target = underdog_id
            if target is None:
                continue
            quote = best_ask(candidates, target, teams)
            if quote is None:
                continue
            entry = match_decision(quote, fixture, username, stake, now)
            if entry["entry_id"] in existing_ids:
                continue  # one decision per strategy/match/selection, never re-placed
            if pending + stake > MATCH_BANKROLL:
                continue  # simulated bankroll budget including pending positions
            entries.append(entry)
            existing_ids.add(entry["entry_id"])
            pending += stake
        ids = [e["entry_id"] for e in entries]
        if len(ids) != len(set(ids)) or any(i in {e["entry_id"] for e in ledger["entries"]} for i in ids):
            raise SourceError("duplicate match paper entry id")
        ledger["entries"].extend(entries)
        placed.extend(entries)
    if placed:
        ledger["meta"]["last_updated_utc"] = stamp(now)
    return placed


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
    teams = json.loads((ROOT / "data" / "teams.json").read_text(encoding="utf-8"))
    strategies = json.loads((ROOT / "data" / "strategies.json").read_text(encoding="utf-8"))
    entries = apply_outright(ledger, observations, now)
    entries += apply_match_strategies(ledger, observations, now, teams, strategies)
    if entries:
        tmp = ledger_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(ledger_path)
    print(f"Simulated paper positions appended: {len(entries)}; prior positions retained: {len(ledger['entries']) - len(entries)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
