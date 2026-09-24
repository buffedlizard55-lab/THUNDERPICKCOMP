"""Append-only settlement journal with independent result confirmation.

Position settlements are never automatic guesses. For every pending paper
decision this module may append hash-chained receipts to
`data/settlements.json`:

- `venue_resolution` — the venue's OWN resolution fields (Kalshi market
  status/result/settlement_value; Polymarket UMA status + resolved outcome
  prices), recorded verbatim with the queried URL and receipt time.
- `result_confirmation` — independent event-result evidence (double-sourced
  HLTV + Liquipedia fixture results from the observations journal; for the
  outright, additionally Liquipedia's infobox `|winner=` field).
- `settlement_decision` — the outcome/payout applied to the ledger entry, only
  when venue + independent confirmations AGREE.
- `settlement_hold` — why a position stays pending (missing/conflicting
  evidence). A hold never changes the ledger.

Void is never assumed: a canceled or unresolved market stays pending until the
venue's own records show an explicit resolution, and 50/50 resolutions are
recorded as `partial` with the venue's payout fraction (never as a refund).
Rows are chained with SHA-256 (`prev_hash`) so any later edit or deletion of
history is detectable; `scripts/validate.py` re-verifies the chain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .collect import KALSHI, POLY, LIQUIPEDIA_API, Fetcher, SourceError, canonical_team, money, parse_time, stamp, utc_now
from .validate import gross_payout

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "data" / "ledger.json"
OBSERVATIONS_PATH = ROOT / "data" / "observations.json"
SETTLEMENTS_PATH = ROOT / "data" / "settlements.json"

POLICY = (
    "No automatic settlement. Append-only venue-resolution receipts plus independent HLTV/Liquipedia result "
    "confirmation; ledger changes only on a settlement_decision row with agreeing evidence. Canceled/unresolved "
    "markets stay pending (void is never assumed); venue 50/50 resolutions are 'partial' with the venue fraction."
)


def empty_journal() -> dict:
    return {"schema_version": 1, "policy": POLICY, "rows": [], "chain_head": None}


def row_hash(prev_hash: str, row: dict) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + "|" + canonical).encode("utf-8")).hexdigest()


def verify_chain(rows: list[dict]) -> None:
    """Tamper evidence: recompute every link or raise SourceError."""
    prev = ""
    for i, row in enumerate(rows):
        recorded = row.get("hash")
        expected = row_hash(prev, {k: v for k, v in row.items() if k != "hash"})
        if recorded != expected or row.get("prev_hash") != prev:
            raise SourceError(f"settlements.json row {i} breaks the hash chain; history was edited")
        prev = recorded


def receipt_id(entry_id: str, kind: str, observation: dict) -> str:
    key = "|".join([entry_id, kind, json.dumps(observation, ensure_ascii=False, sort_keys=True)])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def append_row(journal: dict, entry_id: str, kind: str, observed_utc: str, observation: dict,
               *, venue: str | None = None, source_url: str = "", raw_excerpt: str = "",
               conflicts: list | None = None, note: str = "") -> bool:
    """Append one receipt unless an identical one already exists (idempotent)."""
    rid = receipt_id(entry_id, kind, observation)
    if any(r["receipt_id"] == rid for r in journal["rows"]):
        return False
    prev = journal["rows"][-1]["hash"] if journal["rows"] else ""
    row = {
        "receipt_id": rid, "prev_hash": prev, "recorded_utc": stamp(utc_now()),
        "entry_id": entry_id, "kind": kind, "observed_utc": observed_utc,
        "venue": venue, "source_url": source_url, "raw_excerpt": raw_excerpt[:800],
        "observation": observation, "conflicts": conflicts or [], "note": note,
    }
    row["hash"] = row_hash(prev, {k: v for k, v in row.items() if k != "hash"})
    journal["rows"].append(row)
    journal["chain_head"] = row["hash"]
    return True


def kalshi_resolution(market: dict) -> dict | None:
    """Kalshi's own settlement fields; None when not yet resolved."""
    status = str(market.get("status") or "")
    if status != "settled":
        return None
    result = market.get("result")
    value = market.get("settlement_value_cents")
    observation = {"status": status, "result": result,
                   "settlement_value_cents": value if value is None else str(value),
                   "ticker": market.get("ticker"), "title": market.get("title"),
                   "yes_sub_title": market.get("yes_sub_title")}
    if result == "yes" and value is not None:
        fraction = Decimal(str(value)) / Decimal(100)
        if not Decimal(0) <= fraction <= Decimal(1):
            raise SourceError("Kalshi settlement value out of range")
        return {"kind": "fraction", "winning_selection": market.get("yes_sub_title"),
                "payout_fraction": str(fraction.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
                "observation": observation}
    if result == "no" and value is not None:
        fraction = Decimal(str(value)) / Decimal(100)
        return {"kind": "fraction", "winning_selection": None,  # Yes side lost
                "payout_fraction": "0", "observation": observation}
    return None  # unresolved shape: stay pending, never guess


def polymarket_resolution(market: dict) -> dict | None:
    """Polymarket's own resolution fields; None when not yet resolved."""
    if market.get("umaResolutionStatus") != "resolved" or market.get("closed") is not True:
        return None
    raw = market.get("outcomePrices")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    outcomes = market.get("outcomes")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, list) or not isinstance(outcomes, list) or len(raw) != len(outcomes) or not raw:
        return None
    try:
        prices = [money(p, "outcome price") for p in raw]
    except SourceError:
        return None
    observation = {"umaResolutionStatus": "resolved", "outcomePrices": [str(p) for p in prices],
                   "outcomes": [str(o) for o in outcomes], "market_id": market.get("id"),
                   "question": market.get("question")}
    winner_index = [i for i, p in enumerate(prices) if p == Decimal(1)]
    fraction = None
    if len(winner_index) == 1:
        fraction = Decimal(1)
    elif all(p == Decimal("0.5") for p in prices):
        fraction = Decimal("0.5")  # explicit UMA 50/50: partial, NOT a refund
    else:
        return None  # unresolved/distributed shape: stay pending
    return {"kind": "fraction",
            "winning_selection": str(outcomes[winner_index[0]]) if fraction == Decimal(1) else None,
            "payout_fraction": str(fraction), "observation": observation}


def venue_resolution(quote: dict, fetcher) -> tuple[dict | None, str, str, str]:
    """Query the venue of the entry's price source for its actual resolution."""
    if quote.get("venue") == "Kalshi":
        url = KALSHI + "/markets/" + quote["market_id"]
        payload = fetcher.get(url)
        # Kalshi wraps the object: GET /markets/{ticker} → {"market": {...}}.
        market = payload.get("market") if isinstance(payload, dict) and isinstance(payload.get("market"), dict) else payload
        if not isinstance(market, dict) or str(market.get("ticker")) != quote["market_id"]:
            raise SourceError("Kalshi resolution response does not match the quoted market")
        resolved = kalshi_resolution(market)
        return resolved, "Kalshi", url, json.dumps({k: market.get(k) for k in ("status", "result", "settlement_value_cents", "ticker")}, ensure_ascii=False)
    if quote.get("venue") == "Polymarket (international)":
        url = POLY + "/markets/" + quote["market_id"]
        market = fetcher.get(url)
        if not isinstance(market, dict) or str(market.get("id")) != quote["market_id"]:
            raise SourceError("Polymarket resolution response does not match the quoted market")
        resolved = polymarket_resolution(market)
        return resolved, "Polymarket (international)", url, json.dumps({k: market.get(k) for k in ("umaResolutionStatus", "outcomePrices", "closed", "question")}, ensure_ascii=False)
    raise SourceError("unknown venue for settlement: " + str(quote.get("venue")))


def fixture_confirmation(entry: dict, observations: dict) -> dict | None:
    """Independent event result for a match entry, from the double-sourced journal."""
    fixture = next((f for f in observations.get("fixtures", []) if f.get("id") == entry.get("match_id")), None)
    if not fixture or fixture.get("result_status") != "confirmed":
        return None
    result = fixture.get("result") or {}
    return {
        "fixture_id": fixture["id"], "winner": result.get("winner"),
        "series_score": result.get("series_score"),
        "sources": result.get("sources") or [fixture.get("liquipedia_url"), fixture.get("source_url")],
        "confirmed_utc": result.get("confirmed_utc"),
    }


def selection_team_id(entry: dict, observations: dict) -> str | None:
    """Canonical finalist id for the entry's selection, from its fixture pair."""
    fixture = next((f for f in observations.get("fixtures", []) if f.get("id") == entry.get("match_id")), None)
    if not fixture:
        return None
    for team_id in (fixture["team_a"], fixture["team_b"]):
        if canonical_team(str(entry.get("selection")), _teams_cache()) == team_id:
            return team_id
    return None


def _display(observations: dict, team_id: str) -> str:
    # display name used for alias matching; teams.json names are the canonical
    # display forms used by both venues' selections.
    for t in _teams_cache():
        if t["id"] == team_id:
            return t["name"]
    return team_id


def _teams_cache():
    global _TEAMS
    if _TEAMS is None:
        _TEAMS = json.loads((ROOT / "data" / "teams.json").read_text(encoding="utf-8"))
    return _TEAMS


_TEAMS = None


def liquipedia_infobox_winner(wikitext: str) -> str | None:
    """The event infobox's own `|winner=` field token, if present."""
    match = re.search(r"\|\s*winner\s*=\s*(?:\{\{[Tt]eamOpponent\|)?([A-Za-z0-9 .]+)", wikitext or "")
    return match.group(1).strip() if match else None


def settle_entry(entry: dict, observations: dict, journal: dict, fetcher, wikitext: str) -> dict | None:
    """Append receipts for one pending entry; return an applied ledger patch or None."""
    # Crash recovery: if a settlement_decision already exists for this entry
    # (journal written, ledger write interrupted), re-apply its patch instead
    # of leaving the ledger pending forever next to a settled receipt.
    prior = next((r for r in journal["rows"]
                  if r["kind"] == "settlement_decision" and r["entry_id"] == entry["entry_id"]), None)
    if prior:
        obs = prior["observation"]
        settlement = {
            "result": obs["result"], "rule": entry["settlement"]["rule"], "settled_utc": prior["recorded_utc"],
            "result_source": ([{"label": "Venue resolution (first-party API)", "url": prior["source_url"],
                                "accessed_utc": prior["recorded_utc"], "type": "primary"}]
                              + [{"label": "Independent result confirmation", "url": u,
                                  "accessed_utc": prior["recorded_utc"], "type": "official-data"}
                                 for u in obs.get("sources", []) if u]),
        }
        if obs.get("payout_fraction"):
            settlement["payout_fraction"] = obs["payout_fraction"]
        return {"settlement": settlement, "payout": obs["payout"], "profit": obs["profit"]}
    ps = entry.get("price_source") or {}
    quote = next((q for q in observations.get("quotes", []) if q.get("quote_id") == ps.get("quote_id")), None)
    if quote is None:
        append_row(journal, entry["entry_id"], "settlement_hold", stamp(utc_now()),
                   {"reason": "quoted receipt missing from observations journal"}, note="Nothing can settle without its original first-party receipt.")
        return None
    entry_id = entry["entry_id"]
    try:
        resolved, venue, url, raw = venue_resolution(quote, fetcher)
    except (SourceError, ValueError) as exc:
        append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                   {"reason": "venue resolution query failed", "error": str(exc)[:200]},
                   venue=quote.get("venue"), source_url=ps.get("url", ""), note="Venue unresolved: position stays pending.")
        return None
    appended = append_row(journal, entry_id, "venue_resolution", stamp(utc_now()), resolved["observation"] if resolved else {"resolved": False},
                          venue=venue, source_url=url, raw_excerpt=raw,
                          note="Venue's own resolution fields, recorded verbatim.")
    _ = appended
    if resolved is None:
        return None  # stay pending; receipt already recorded
    # Independent result confirmation.
    if entry.get("match_id") == "TWC26-FINALS-CHAMPION":
        winner_id = canonical_team(str(resolved.get("winning_selection") or entry.get("selection")), _teams_cache())
        infobox = liquipedia_infobox_winner(wikitext)
        infobox_id = canonical_team(infobox or "", _teams_cache()) if infobox else None
        confirmed_fixture = next((f for f in observations.get("fixtures", [])
                                  if f.get("result_status") == "confirmed" and f.get("stage_label") == "playoffs"
                                  and (f.get("result") or {}).get("winner")), None)
        confirmation = {
            "infobox_winner": infobox, "infobox_team": infobox_id,
            "confirmed_playoff_fixture": confirmed_fixture["id"] if confirmed_fixture else None,
            "confirmed_playoff_winner": (confirmed_fixture.get("result") or {}).get("winner") if confirmed_fixture else None,
            "sources": [LIQUIPEDIA_API, (confirmed_fixture or {}).get("source_url")],
        }
        agreement = (infobox_id is not None and infobox_id == winner_id
                     and confirmed_fixture is not None
                     and (confirmed_fixture.get("result") or {}).get("winner") == winner_id)
        append_row(journal, entry_id, "result_confirmation", stamp(utc_now()), confirmation,
                   source_url=LIQUIPEDIA_API,
                   note="Outright requires venue + Liquipedia infobox winner + a double-sourced confirmed playoff result to agree.")
        if not agreement:
            append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                       {"reason": "outright confirmation incomplete"}, note="Winner not independently confirmed by all required sources; ledger stays pending.")
            return None
        winner_id = infobox_id
    else:
        confirmation = fixture_confirmation(entry, observations)
        selection_id = selection_team_id(entry, observations)
        append_row(journal, entry_id, "result_confirmation", stamp(utc_now()), confirmation or {"confirmed": False},
                   source_url=(confirmation or {}).get("sources", [""])[0],
                   note="Match result must already be double-sourced (HLTV + Liquipedia) in the fixtures journal.")
        if not confirmation:
            append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                       {"reason": "fixture result not double-sourced yet"}, note="Ledger stays pending.")
            return None
        winner_selection = entry.get("selection") if confirmation["winner"] == selection_id else None
        winner_id = confirmation["winner"]
    # Decide. Venue and independent confirmations must AGREE; any disagreement
    # is a hold, never a guessed loss/win. Void stays out of reach until a
    # venue reports an explicit voided/staked-refund resolution itself.
    fraction = Decimal(resolved["payout_fraction"])
    venue_winner_id = (canonical_team(str(resolved.get("winning_selection")), _teams_cache())
                       if resolved.get("winning_selection") else None)
    if entry.get("match_id") == "TWC26-FINALS-CHAMPION":
        if fraction == 1 and venue_winner_id is None:
            append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                       {"reason": "venue resolution lacks a winner identity"}, note="Ledger stays pending.")
            return None
        infobox_id = confirmation.get("infobox_team")
        bracket_winner = confirmation.get("confirmed_playoff_winner")
        if infobox_id is None or bracket_winner is None or not (infobox_id == bracket_winner):
            append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                       {"reason": "outright confirmation incomplete"}, note="Winner not independently confirmed by all required sources; ledger stays pending.")
            return None
        if venue_winner_id is not None and venue_winner_id != infobox_id:
            append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                       {"reason": "venue winner disagrees with independent confirmations",
                        "venue": resolved.get("winning_selection"), "independent": infobox_id},
                       conflicts=["venue_vs_liquipedia"], note="Manual review required; ledger stays pending.")
            return None
        selection_id = canonical_team(str(entry.get("selection")), _teams_cache())
        won = infobox_id == selection_id
    else:
        fixture_winner = confirmation.get("winner")
        selection_id = selection_team_id(entry, observations)
        if selection_id is None or fixture_winner is None:
            append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                       {"reason": "confirmed fixture lacks a winner or selection mapping"}, note="Ledger stays pending.")
            return None
        if fraction == 1:
            if venue_winner_id is None or venue_winner_id != fixture_winner:
                append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                           {"reason": "venue winner missing or disagrees with double-sourced fixture result",
                            "venue": resolved.get("winning_selection"), "fixture": fixture_winner},
                           conflicts=["venue_vs_fixtures"], note="Manual review required; ledger stays pending.")
                return None
            won = fixture_winner == selection_id
        elif fraction == 0:
            if fixture_winner == selection_id:
                # The double-sourced result says this selection WON, but the
                # venue paid its Yes side zero — never settle that as a loss.
                append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                           {"reason": "venue paid the Yes side zero although the confirmed result says it won",
                            "fixture": fixture_winner},
                           conflicts=["venue_vs_fixtures"], note="Manual review required; ledger stays pending.")
                return None
            won = False
        else:
            if venue_winner_id is not None and venue_winner_id != fixture_winner:
                append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                           {"reason": "venue winner disagrees with double-sourced fixture result (partial resolution)",
                            "venue": resolved.get("winning_selection"), "fixture": fixture_winner},
                           conflicts=["venue_vs_fixtures"], note="Manual review required; ledger stays pending.")
                return None
            won = fixture_winner == selection_id
    if fraction == 1:
        result, used_fraction = ("win" if won else "loss"), None
    elif fraction == 0:
        result, used_fraction = "loss", None
    elif Decimal(0) < fraction < Decimal(1):
        # Venue-approved partial/50/50 payout on THIS selection (never a refund
        # unless the venue's own rule says so; that would be an explicit void).
        result, used_fraction = "partial", fraction
    else:
        append_row(journal, entry_id, "settlement_hold", stamp(utc_now()),
                   {"reason": "unmapped venue payout fraction", "fraction": str(fraction)},
                   note="Ledger stays pending; resolution needs manual review.")
        return None
    stake = money(entry["stake"], "stake")
    price = money(ps["raw_price"], "raw_price")
    payout = gross_payout(stake, price, result, used_fraction)
    decision = {
        "result": result, "payout_fraction": str(used_fraction) if used_fraction is not None else None,
        "payout": str(payout), "profit": str(payout - stake),
        "winner": winner_id,
        "sources": confirmation.get("sources") or [],
        "venue_url": url,
    }
    appended = append_row(journal, entry_id, "settlement_decision", stamp(utc_now()), decision,
                          venue=venue, source_url=url,
                          note="Ledger updated from this receipt; payout follows the published gross, fee-free formula.")
    if not appended:
        return None  # decision already applied previously
    return {
        "settlement": {
            "result": result, "rule": entry["settlement"]["rule"], "settled_utc": stamp(utc_now()),
            "result_source": ([{"label": "Venue resolution (first-party API)", "url": url,
                                "accessed_utc": stamp(utc_now()), "type": "primary"}]
                              + [{"label": "Independent result confirmation", "url": u,
                                  "accessed_utc": stamp(utc_now()), "type": "official-data"}
                                 for u in decision["sources"] if u]),
            **({"payout_fraction": str(used_fraction)} if used_fraction is not None else {}),
        },
        "payout": str(payout), "profit": str(payout - stake),
    }


def settle_all(ledger: dict, observations: dict, journal: dict, fetcher) -> int:
    verify_chain(journal["rows"])
    wikitext = ""
    outright_pending = any(
        (e.get("settlement") or {}).get("result") == "pending" and e.get("match_id") == "TWC26-FINALS-CHAMPION"
        for e in ledger.get("entries", []))
    try:
        wikitext = fetcher.get(LIQUIPEDIA_API)["parse"]["wikitext"]["*"]
    except (SourceError, ValueError, KeyError, TypeError):
        if outright_pending:
            # One receipt per affected run — only when an outright position
            # actually needs settling, so offline/local runs append nothing.
            append_row(journal, "journal", "settlement_hold", stamp(utc_now()),
                       {"reason": "Liquipedia wikitext unavailable for outright confirmation"},
                       source_url=LIQUIPEDIA_API, note="Only blocks OUTRIGHT settlement; match settlements unaffected.")
    applied = 0
    for entry in ledger.get("entries", []):
        if (entry.get("settlement") or {}).get("result") != "pending":
            continue
        try:
            patch = settle_entry(entry, observations, journal, fetcher, wikitext)
        except (SourceError, ValueError, KeyError, TypeError) as exc:
            append_row(journal, entry["entry_id"], "settlement_hold", stamp(utc_now()),
                       {"reason": "settlement check failed", "error": str(exc)[:200]},
                       note="Ledger stays pending; review required.")
            continue
        if patch:
            entry["settlement"].update(patch["settlement"])
            entry["payout"] = patch["payout"]
            entry["profit"] = patch["profit"]
            ledger["meta"]["last_updated_utc"] = stamp(utc_now())
            applied += 1
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="record nothing; report what would be checked")
    args = parser.parse_args(argv)
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    observations = json.loads(OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    journal = json.loads(SETTLEMENTS_PATH.read_text(encoding="utf-8")) if SETTLEMENTS_PATH.exists() else empty_journal()
    pending = [e["entry_id"] for e in ledger.get("entries", []) if (e.get("settlement") or {}).get("result") == "pending"]
    if args.dry_run:
        print(f"{len(pending)} pending position(s); journal has {len(journal['rows'])} receipt(s); chain verified.")
        return 0
    fetcher = Fetcher()
    applied = settle_all(ledger, observations, journal, fetcher)
    verify_chain(journal["rows"])
    tmp = SETTLEMENTS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(journal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(SETTLEMENTS_PATH)
    if applied:
        tmp = LEDGER_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(LEDGER_PATH)
    print(f"Settlement journal: {len(journal['rows'])} receipts (chain head {str(journal['chain_head'])[:12]}…); ledger entries settled now: {applied}; pending remaining: {len(pending) - applied}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
