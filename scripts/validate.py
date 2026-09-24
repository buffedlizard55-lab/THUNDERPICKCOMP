#!/usr/bin/env python3
"""Validate THUNDERPICKCOMP data files: schema, provenance, references, money math.

Fails (exit 1) on any violation. Run: python3 scripts/validate.py
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # allow `python3 scripts/validate.py` to import scripts.*
    sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
ERRORS = []


def err(msg):
    ERRORS.append(msg)


def load(name):
    p = DATA / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        err(f"{name}: file missing")
    except json.JSONDecodeError as e:
        err(f"{name}: invalid JSON: {e}")
    return None


ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
URL = re.compile(r"^https://\S+$")
TYPES = {"primary", "official-data", "secondary"}
STATUSES = {"verified", "flagged", "unverified", "stale"}

# The live collector's exact check list is the single source of truth. A live
# journal must report one check per collected source — no fewer (a silently
# skipped source would fake coverage) and no more (an unknown source would
# bypass this validator's per-check rules).
try:  # works as `python3 scripts/validate.py` and as `python3 -m scripts.validate`
    from scripts.collect import SOURCE_IDS as REQUIRED_SOURCES
except ImportError:
    from collect import SOURCE_IDS as REQUIRED_SOURCES


def check_iso(value, where):
    if not isinstance(value, str) or not ISO.match(value):
        err(f"{where}: timestamp must be ISO-8601 UTC like 2026-09-24T05:30:00Z, got {value!r}")
        return
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        err(f"{where}: unparseable timestamp {value!r}")
        return
    if dt > datetime.now(timezone.utc):
        err(f"{where}: timestamp is in the future: {value}")


def decimal(value, where, lower=None, upper=None):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation()
    except (InvalidOperation, ValueError, TypeError):
        err(f"{where}: must be a finite decimal, got {value!r}")
        return None
    if lower is not None and result <= lower:
        err(f"{where}: must be > {lower}, got {result}")
    if upper is not None and result >= upper:
        err(f"{where}: must be < {upper}, got {result}")
    return result


def check_url(value, where):
    if not isinstance(value, str) or not URL.match(value):
        err(f"{where}: HTTPS URL required, got {value!r}")


def check_sources(sources, where, require=True):
    if not isinstance(sources, list) or not sources:
        if require:
            err(f"{where}: missing required sources[]")
        return
    for i, s in enumerate(sources):
        w = f"{where}.sources[{i}]"
        if not isinstance(s, dict):
            err(f"{w}: source must be an object")
            continue
        if not s.get("label"):
            err(f"{w}: missing label")
        check_url(s.get("url"), w)
        check_iso(s.get("accessed_utc"), w)
        if s.get("type") not in TYPES:
            err(f"{w}: type must be one of {sorted(TYPES)}, got {s.get('type')!r}")


def check_master(entries):
    if entries is None:
        return set()
    ids = set()
    cats = {"tournament", "team", "roster", "format", "broadcast", "qualifier",
            "match", "market-data"}
    for i, e in enumerate(entries):
        w = f"master_list[{i}]"
        for f in ("id", "category", "claim", "detail", "sources", "verified_utc",
                  "status", "flags", "notes"):
            if f not in e:
                err(f"{w}: missing field {f}")
        if e.get("id") in ids:
            err(f"{w}: duplicate id {e.get('id')}")
        ids.add(e.get("id"))
        if e.get("id") and not re.match(r"^ML-\d{3}$", e["id"]):
            err(f"{w}: id must match ML-###, got {e['id']!r}")
        if e.get("category") not in cats:
            err(f"{w}: category must be one of {sorted(cats)}, got {e.get('category')!r}")
        if not e.get("claim") or not e.get("detail"):
            err(f"{w}: claim/detail must be non-empty")
        if e.get("status") not in STATUSES:
            err(f"{w}: status must be one of {sorted(STATUSES)}, got {e.get('status')!r}")
        if not isinstance(e.get("flags"), list):
            err(f"{w}: flags must be a list")
        if "verified_utc" in e:
            check_iso(e["verified_utc"], w)
        check_sources(e.get("sources"), w)
        # Status/flag coherence
        if e.get("status") == "flagged" and not e.get("flags"):
            err(f"{w}: flagged status requires at least one flag")
    if len(entries) < 20:
        err(f"master_list: expected >= 20 entries, got {len(entries)}")
    return ids


def check_teams(teams, master_ids):
    if teams is None:
        return set()
    ids = set()
    if len(teams) != 8:
        err(f"teams: expected 8 finalists, got {len(teams)}")
    for i, t in enumerate(teams):
        w = f"teams[{i}]"
        for f in ("id", "name", "route", "vrs_rank_2026_09_16",
                  "hltv_rank_observed", "hltv_rank_observed_utc", "roster",
                  "coach", "sources", "master_list"):
            if f not in t:
                err(f"{w}: missing field {f}")
        if t.get("id") in ids:
            err(f"{w}: duplicate id {t.get('id')}")
        ids.add(t.get("id"))
        for f in ("vrs_rank_2026_09_16", "hltv_rank_observed"):
            v = t.get(f)
            if not isinstance(v, int) or v < 1:
                err(f"{w}: {f} must be a positive int, got {v!r}")
        if "hltv_rank_observed_utc" in t:
            check_iso(t["hltv_rank_observed_utc"], w)
        roster = t.get("roster") or []
        if len(roster) != 5:
            err(f"{w}: roster must have exactly 5 players, got {len(roster)}")
        handles = set()
        for j, p in enumerate(roster):
            if not p.get("handle"):
                err(f"{w}.roster[{j}]: missing handle")
            if p.get("handle") in handles:
                err(f"{w}.roster[{j}]: duplicate handle {p.get('handle')}")
            handles.add(p.get("handle"))
            if not p.get("nation"):
                err(f"{w}.roster[{j}]: missing nation")
        if not (t.get("coach") or {}).get("handle"):
            err(f"{w}: missing coach.handle")
        check_sources(t.get("sources"), w)
        if t.get("master_list") not in master_ids:
            err(f"{w}: master_list ref {t.get('master_list')!r} not in master list")
    return ids


def check_matches(matches, master_ids):
    if matches is None:
        return set()
    ids = set()
    for i, m in enumerate(matches):
        w = f"matches[{i}]"
        for f in ("id", "event", "stage", "status", "detail", "sources",
                  "master_list"):
            if f not in m:
                err(f"{w}: missing field {f}")
        if m.get("id") in ids:
            err(f"{w}: duplicate id {m.get('id')}")
        ids.add(m.get("id"))
        if m.get("status") not in {"scheduled", "final", "tbd"}:
            err(f"{w}: bad status {m.get('status')!r}")
        if m.get("status") == "final" and not m.get("detail"):
            err(f"{w}: final record needs detail")
        check_sources(m.get("sources"), w)
        if m.get("master_list") not in master_ids:
            err(f"{w}: master_list ref {m.get('master_list')!r} not in master list")
    return ids


def check_market_sources(srcs, master_ids):
    if srcs is None:
        return
    ids = set()
    for i, s in enumerate(srcs):
        w = f"market_sources[{i}]"
        for f in ("id", "name", "kind", "url", "access", "coverage",
                  "last_checked_utc", "status", "master_list"):
            if f not in s:
                err(f"{w}: missing field {f}")
        if s.get("id") in ids:
            err(f"{w}: duplicate id {s.get('id')}")
        ids.add(s.get("id"))
        if s.get("url") and not URL.match(s["url"]):
            err(f"{w}: url must be https, got {s.get('url')!r}")
        if s.get("docs_url") and not URL.match(s["docs_url"]):
            err(f"{w}: docs_url must be https, got {s.get('docs_url')!r}")
        if "last_checked_utc" in s:
            check_iso(s["last_checked_utc"], w)
        if s.get("master_list") not in master_ids:
            err(f"{w}: master_list ref {s.get('master_list')!r} not in master list")


def check_strategies(strats):
    if strats is None:
        return set()
    users = set()
    for i, s in enumerate(strats):
        w = f"strategies[{i}]"
        for f in ("username", "simulated", "strategy", "description", "rules",
                  "bankroll_start", "status"):
            if f not in s:
                err(f"{w}: missing field {f}")
        if s.get("username") in users:
            err(f"{w}: duplicate username {s.get('username')}")
        users.add(s.get("username"))
        if s.get("simulated") is not True:
            err(f"{w}: simulated must be true")
        if not isinstance(s.get("rules"), list) or not s["rules"]:
            err(f"{w}: rules must be a non-empty list")
        try:
            if float(s.get("bankroll_start", 0)) <= 0:
                err(f"{w}: bankroll_start must be > 0")
        except (TypeError, ValueError):
            err(f"{w}: bankroll_start must be numeric")
        if "stake_units" in s:
            try:
                if float(s["stake_units"]) <= 0:
                    err(f"{w}: stake_units must be > 0 when present")
            except (TypeError, ValueError):
                err(f"{w}: stake_units must be numeric")
        if s.get("status") not in {"active", "paused", "retired"}:
            err(f"{w}: bad status {s.get('status')!r}")
    return users


def check_changes(changes, teams, master_ids):
    if changes is None:
        return
    if not isinstance(changes, list):
        err("roster_changes: expected array")
        return
    team_ids = {t.get("id") for t in teams or []}
    seen = set()
    for i, row in enumerate(changes):
        w = f"roster_changes[{i}]"
        if not isinstance(row, dict):
            err(f"{w}: expected object")
            continue
        if not re.fullmatch(r"RC-\d{3}", str(row.get("id", ""))) or row["id"] in seen:
            err(f"{w}: missing, malformed or duplicate id")
        seen.add(row.get("id"))
        if row.get("team_id") not in team_ids or row.get("master_list") not in master_ids:
            err(f"{w}: missing referenced team / master-list entry")
        for field in ("kind", "player", "fact", "impact"):
            if not row.get(field):
                err(f"{w}: missing {field}")
        check_iso(row.get("published_utc"), w + ".published_utc")
        check_iso(row.get("verified_utc"), w + ".verified_utc")
        if (row.get("published_utc") or "") > (row.get("verified_utc") or ""):
            err(f"{w}: publication is after verification")
        check_sources(row.get("sources"), w)
        if not any(src.get("type") == "primary" for src in row.get("sources", []) if isinstance(src, dict)):
            err(f"{w}: verified move needs a primary team/player source")


def check_observations(obs, teams):
    if not isinstance(obs, dict) or obs.get("schema_version") != 1:
        err("observations: missing/unknown schema v1")
        return set()
    mode = obs.get("mode")
    if mode not in {"not-run", "offline-replay", "live"}:
        err(f"observations: unexpected mode {mode!r}")
    if mode != "not-run":
        check_iso(obs.get("last_attempt_utc"), "observations.last_attempt_utc")
        check_iso(obs.get("last_completed_utc"), "observations.last_completed_utc")
        if (obs.get("last_attempt_utc") or "") > (obs.get("last_completed_utc") or ""):
            err("observations: completion precedes attempt")
    team_ids = {t.get("id") for t in teams or []}
    for field in ("checks", "vrs_history", "roster_signals", "fixtures", "events", "quotes", "alerts"):
        if not isinstance(obs.get(field), list):
            err(f"observations.{field}: expected array")
            return set()
    if mode == "live":
        seen_live = [c.get("source") for c in obs["checks"]
                     if isinstance(c, dict) and isinstance(c.get("source"), str)]
        if len(obs["checks"]) != len(REQUIRED_SOURCES) or sorted(seen_live) != sorted(REQUIRED_SOURCES):
            err(f"observations: live run must report exactly one check per collected source "
                f"{', '.join(REQUIRED_SOURCES)} (got {len(obs['checks'])} checks)")
    checked = set()
    for i, c in enumerate(obs["checks"]):
        w = f"observations.checks[{i}]"
        if not isinstance(c, dict):
            err(f"{w}: expected object")
            continue
        if c.get("source") in checked or c.get("source") not in set(REQUIRED_SOURCES):
            err(f"{w}: duplicate or unknown source")
        checked.add(c.get("source"))
        if c.get("status") not in {"ok", "partial", "error"}:
            err(f"{w}: invalid status")
        check_url(c.get("url"), w)
        check_iso(c.get("checked_utc"), w)
        if not isinstance(c.get("records_checked"), int) or c["records_checked"] < 0 or not c.get("scope"):
            err(f"{w}: missing scope or invalid count")
    seen_dates = set()
    previous_date = ""
    for i, snapshot in enumerate(obs["vrs_history"]):
        w = f"observations.vrs_history[{i}]"
        date = snapshot.get("snapshot_date", "")
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except (TypeError, ValueError):
            err(f"{w}: invalid snapshot date")
        if date in seen_dates or date <= previous_date:
            err(f"{w}: duplicate or out-of-order date")
        previous_date = date
        seen_dates.add(date)
        check_url(snapshot.get("url"), w)
        check_iso(snapshot.get("observed_utc"), w)
        rows = snapshot.get("teams")
        if not isinstance(rows, list) or {r.get("team_id") for r in rows} != team_ids:
            err(f"{w}: must contain exactly the eight finalists")
            continue
        for row in rows:
            if type(row.get("rank")) is not int or row["rank"] <= 0 or type(row.get("points")) is not int or row["points"] <= 0:
                err(f"{w}: invalid Valve rank/points")
            if not isinstance(row.get("roster"), list) or len(row["roster"]) != 5 or len(set(row["roster"])) != 5:
                err(f"{w}: invalid VRS ranked roster")
    signals = set()
    for i, row in enumerate(obs["roster_signals"]):
        w = f"observations.roster_signals[{i}]"
        if row.get("id") in signals or row.get("team_id") not in team_ids:
            err(f"{w}: duplicate id or unknown team")
        signals.add(row.get("id"))
        if row.get("old_snapshot_date") not in seen_dates or row.get("new_snapshot_date") not in seen_dates or not row.get("old_snapshot_date", "") < row.get("new_snapshot_date", ""):
            err(f"{w}: invalid snapshot references")
        for f in ("old_url", "new_url"):
            check_url(row.get(f), w)
        if not row.get("removed") and not row.get("added"):
            err(f"{w}: roster signal must explain the difference")
    event_ids = set()
    for i, e in enumerate(obs["events"]):
        w = f"observations.events[{i}]"
        if not isinstance(e, dict) or e.get("key") in event_ids or not e.get("key"):
            err(f"{w}: duplicate/missing event key")
            continue
        event_ids.add(e["key"])
        if not e.get("title") or e.get("status") not in {"open", "closed"} or e.get("venue") not in {"Kalshi", "Polymarket (international)"}:
            err(f"{w}: malformed venue/event/status")
        for f in ("source_url", "review_url"):
            check_url(e.get(f), w)
        for f in ("first_seen_utc", "last_seen_utc"):
            check_iso(e.get(f), w)
    seen_fixtures = set()
    fixture_ids = set()
    for i, row in enumerate(obs["fixtures"]):
        w = f"observations.fixtures[{i}]"
        if row.get("id") in seen_fixtures or not re.fullmatch(r"HLTV-\d{6,9}", row.get("id", "")):
            err(f"{w}: duplicate/malformed HLTV match id")
        seen_fixtures.add(row.get("id"))
        fixture_ids.add(row.get("id"))
        if row.get("team_a") not in team_ids or row.get("team_b") not in team_ids or row.get("team_a") == row.get("team_b"):
            err(f"{w}: malformed teams")
        check_iso(row.get("scheduled_utc"), w)
        check_iso(row.get("observed_utc"), w)
        for f in ("source_url", "liquipedia_url"):
            check_url(row.get(f), w)
        if row.get("status") not in {"scheduled-unconfirmed", "scheduled-confirmed", "conflict"}:
            err(f"{w}: fixture must be unconfirmed, double-source confirmed, or in explicit conflict")
        if row.get("status") == "scheduled-confirmed" and not row.get("hltv_verified_utc"):
            err(f"{w}: confirmed fixture must record its HLTV verification time")
        if row.get("result_status") == "confirmed":
            result = row.get("result") or {}
            if result.get("winner") not in team_ids or not isinstance(result.get("series_score"), list):
                err(f"{w}: confirmed result needs a finalist winner and series score")
            check_iso(result.get("confirmed_utc"), w + ".result.confirmed_utc")
            for u in result.get("sources") or []:
                check_url(u, w + ".result.sources")
        if row.get("result_status") == "conflict" and row.get("status") != "conflict":
            err(f"{w}: result conflict must mark the whole fixture conflicted")
    ids = set()
    if mode == "offline-replay" and obs["quotes"]:
        err("observations: offline replay must not publish quotes or create bets")
    for i, q in enumerate(obs["quotes"]):
        w = f"observations.quotes[{i}]"
        if not isinstance(q, dict) or not q.get("quote_id") or q.get("quote_id") in ids:
            err(f"{w}: duplicate/missing quote ID")
            continue
        ids.add(q["quote_id"])
        if q.get("event_key") not in event_ids or not q.get("market_id") or not q.get("selection") or not q.get("resolution_rule"):
            err(f"{w}: missing event, market id, selection or settlement rule")
        if q.get("venue") not in {"Kalshi", "Polymarket (international)"}:
            err(f"{w}: unknown venue")
        raw_price = decimal(q.get("raw_price"), w + ".raw_price", lower=Decimal(0), upper=Decimal(1))
        size = decimal(q["ask_size"], w + ".ask_size") if q.get("ask_size") is not None else None
        if size is not None and size < 0:
            err(f"{w}: negative size")
        if raw_price is not None and all(isinstance(q.get(f), str) for f in ("venue", "market_id", "selection", "observed_utc")):
            identity = "|".join([q["venue"], q["market_id"], q["selection"], q["observed_utc"], str(raw_price), str(q.get("ask_size")), str(q.get("source_updated_utc"))])
            if q["quote_id"] != hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]:
                err(f"{w}: quote ID does not match immutable price/size/time fields")
        check_iso(q.get("observed_utc"), w)
        if q.get("source_updated_utc") is not None:
            check_iso(q["source_updated_utc"], w + ".source_updated_utc")
        elif q.get("quote_status") != "indicative-only":
            err(f"{w}: fresh quote needs a first-party book timestamp")
        for f in ("source_url", "event_url"):
            check_url(q.get(f), w)
        if q.get("quote_status") not in {"fresh", "indicative-only"}:
            err(f"{w}: quote freshness unknown")
        if q.get("source_updated_utc") and q.get("observed_utc"):
            try:
                lag = (datetime.strptime(q["observed_utc"], "%Y-%m-%dT%H:%M:%SZ") -
                       datetime.strptime(q["source_updated_utc"], "%Y-%m-%dT%H:%M:%SZ")).total_seconds()
                if lag < 0:
                    err(f"{w}: venue book timestamp after receipt")
                if q.get("quote_status") == "fresh" and (lag > 600 or size is None or size <= 0):
                    err(f"{w}: a fresh ask needs a book update within 10 minutes and positive size")
            except (TypeError, ValueError):
                err(f"{w}: quote/book timestamps invalid")
        if q.get("observed_utc") and obs.get("last_completed_utc") and q["observed_utc"] > obs["last_completed_utc"]:
            err(f"{w}: observation occurred after last completed run")
    for i, a in enumerate(obs["alerts"]):
        if not a.get("code") or not a.get("message"):
            err(f"observations.alerts[{i}]: missing code/message")
        if a.get("source_url"):
            check_url(a["source_url"], f"observations.alerts[{i}]")
    return ids


def gross_payout(stake, raw_price, result, fraction=None):
    """Pure Decimal gross paper math. No exchange fees or real fills."""
    if result == "win":
        raw = stake / raw_price
    elif result == "loss":
        raw = Decimal(0)
    elif result == "void":
        raw = stake
    elif result == "partial" and fraction is not None and 0 < fraction < 1:
        raw = stake * fraction / raw_price
    else:
        raise ValueError("invalid settled result or payout fraction")
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def check_ledger(ledger, users, match_ids, observations, paused_users=()):
    if ledger is None:
        return
    meta = ledger.get("meta") or {}
    for f in ("simulated", "currency", "settlement_policy", "last_updated_utc"):
        if f not in meta:
            err(f"ledger.meta: missing field {f}")
    if meta.get("simulated") is not True:
        err("ledger.meta: simulated must be true")
    check_iso(meta.get("last_updated_utc"), "ledger.meta.last_updated_utc")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        err("ledger.entries: expected array")
        return
    quote_by_id = {q["quote_id"]: q for q in (observations or {}).get("quotes", []) if isinstance(q, dict) and q.get("quote_id")}
    event_by_key = {ev["key"]: ev for ev in (observations or {}).get("events", []) if isinstance(ev, dict) and ev.get("key")}
    seen, positions = set(), set()
    for i, e in enumerate(entries):
        w = f"ledger.entries[{i}]"
        if not isinstance(e, dict):
            err(f"{w}: expected object")
            continue
        for f in ("entry_id", "username", "match_id", "market", "selection", "decimal_odds",
                  "stake", "placed_utc", "price_source", "settlement", "payout", "profit", "fill_policy"):
            if f not in e:
                err(f"{w}: missing field {f}")
        if not e.get("entry_id") or e.get("entry_id") in seen:
            err(f"{w}: duplicate/missing entry_id")
        seen.add(e.get("entry_id"))
        if e.get("username") not in users or e.get("match_id") not in match_ids or e.get("simulated") is not True:
            err(f"{w}: unknown user/match or not labeled simulated")
        if e.get("username") == "sim_flat_observer" or e.get("username") in paused_users:
            err(f"{w}: control/paused policy must not create a paper decision")
        if e.get("username") == "sim_champ_correlation":
            if e.get("match_id") != "TWC26-FINALS-CHAMPION" or e.get("selection") not in {"FURIA", "Falcons"}:
                err(f"{w}: outright policy must target the confirmed Finals winner market and one of its two teams")
            if isinstance(e.get("placed_utc"), str) and e["placed_utc"] >= "2026-10-14T00:00:00Z":
                err(f"{w}: outright paper decision is after pre-event cutoff")
        if not isinstance(e.get("fill_policy"), str) or "SIMULATED" not in e["fill_policy"]:
            err(f"{w}: paper fill must be explicitly labeled")
        pair = (e.get("username"), e.get("event_key"), e.get("selection"))
        if pair in positions:
            err(f"{w}: duplicate user/event/selection paper position")
        positions.add(pair)
        stake = decimal(e.get("stake"), w + ".stake", lower=Decimal(0))
        odds = decimal(e.get("decimal_odds"), w + ".decimal_odds", lower=Decimal(1))
        check_iso(e.get("placed_utc"), w)
        ps = e.get("price_source") or {}
        q = quote_by_id.get(ps.get("quote_id"))
        if not q:
            err(f"{w}: missing quote ID in append-only observations")
        else:
            for field, observed in (("venue", "venue"), ("market_id", "market_id"),
                                     ("raw_price", "raw_price"), ("url", "source_url"),
                                     ("observed_utc", "observed_utc")):
                if str(ps.get(field)) != str(q.get(observed)):
                    err(f"{w}: source {field} differs from immutable quote {ps.get('quote_id')}")
            if e.get("selection") != q.get("selection") or e.get("event_key") != q.get("event_key"):
                err(f"{w}: ledger selection/event does not match quote")
            if q.get("quote_status") != "fresh":
                err(f"{w}: cannot paper-trade an old/missing-size quote")
            if e.get("username") == "sim_champ_correlation":
                event = event_by_key.get(q.get("event_key"), {})
                title = str(event.get("title", "")).lower()
                question = str(q.get("market_title", "")).lower()
                if ("thunderpick world championship" not in title or "2026" not in title or
                        re.search(r"\bvs\.?\b", title) or event.get("stage") == "qualifier/series"):
                    err(f"{w}: paper champion cannot target a match or qualifier event")
                if q.get("venue") == "Kalshi" and q.get("market_type") != "tournament winner":
                    err(f"{w}: Kalshi contract is not a tournament-winner outright")
                if q.get("venue") == "Polymarket (international)" and (
                        re.search(r"\b(map|match|game)\b", question) or
                        not (re.search(r"\b(winner|champion|win)\b", title) or
                             re.search(r"\btournament\s+winner\b", question) or
                             ("championship" in question and re.search(r"\b(winner|champion|win)\b", question)))):
                    err(f"{w}: Polymarket contract is not a tournament-winner outright")
        check_url(ps.get("url"), w + ".price_source")
        check_iso(ps.get("observed_utc"), w + ".price_source.observed_utc")
        check_iso(ps.get("source_updated_utc"), w + ".price_source.source_updated_utc")
        if e.get("placed_utc") and ps.get("observed_utc"):
            try:
                delay = datetime.strptime(e["placed_utc"], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(ps["observed_utc"], "%Y-%m-%dT%H:%M:%SZ")
                if not 0 <= delay.total_seconds() <= 120:
                    err(f"{w}: decision must be 0–120s after its quote receipt")
            except ValueError:
                err(f"{w}: invalid quote-to-decision timestamps")
        raw_price = decimal(ps.get("raw_price"), w + ".price_source.raw_price", lower=Decimal(0), upper=Decimal(1))
        if odds is not None and raw_price is not None and abs(odds - Decimal(1) / raw_price) > Decimal("0.00000002"):
            err(f"{w}: decimal odds not derived from the raw price")
        if stake is not None and raw_price is not None:
            size = decimal(ps.get("ask_size"), w + ".price_source.ask_size")
            if size is not None and size < stake / raw_price:
                err(f"{w}: top-of-book size is too small for paper stake")
        settlement = e.get("settlement") or {}
        result = settlement.get("result")
        if result not in {"win", "loss", "void", "partial", "pending"}:
            err(f"{w}: invalid settlement result {result!r}")
            continue
        if not settlement.get("rule"):
            err(f"{w}: market resolution rule required even when pending")
        if q and settlement.get("rule") != q.get("resolution_rule"):
            err(f"{w}: market rule not identical to first captured rule")
        if result == "pending":
            if e.get("payout") is not None or e.get("profit") is not None or settlement.get("settled_utc"):
                err(f"{w}: pending payout/profit/settlement time must all be null")
            continue
        check_iso(settlement.get("settled_utc"), w + ".settled_utc")
        if settlement.get("settled_utc") and e.get("placed_utc"):
            if settlement["settled_utc"] < e["placed_utc"]:
                err(f"{w}: cannot settle before the paper decision")
            if e.get("match_id") == "TWC26-FINALS-CHAMPION" and settlement["settled_utc"] < "2026-10-18T00:00:00Z":
                err(f"{w}: cannot settle an outright before the Finals date")
        check_sources(settlement.get("result_source"), w + ".result_source")
        urls = [s.get("url", "") for s in (settlement.get("result_source") or []) if isinstance(s, dict)]
        venue_host = "kalshi.com" if ps.get("venue") == "Kalshi" else "polymarket.com"
        if not (any(venue_host in u for u in urls) and any("hltv.org" in u for u in urls) and
                any("liquipedia.net" in u for u in urls)):
            err(f"{w}: settlement needs venue resolution plus independent HLTV and Liquipedia result links")
        payout = decimal(e.get("payout"), w + ".payout")
        profit = decimal(e.get("profit"), w + ".profit")
        if stake is None or raw_price is None or payout is None or profit is None:
            continue
        fraction = None
        if result == "partial":
            fraction = decimal(settlement.get("payout_fraction"), w + ".payout_fraction", lower=Decimal(0), upper=Decimal(1))
            if fraction is None:
                continue
        try:
            expected = gross_payout(stake, raw_price, result, fraction)
        except (ValueError, ArithmeticError):
            err(f"{w}: invalid settled gross payout")
            continue
        if payout != expected or profit != payout - stake:
            err(f"{w}: payout/profit do not match gross price math ({expected}, {expected - stake})")

    champion = [e for e in entries if isinstance(e, dict) and e.get("username") == "sim_champ_correlation"]
    if champion:
        if len(champion) != 2 or {e.get("selection") for e in champion} != {"FURIA", "Falcons"}:
            err("ledger: champion strategy must contain exactly one FURIA/Falcons pair, or none")
        elif champion[0].get("placed_utc") != champion[1].get("placed_utc"):
            err("ledger: champion pair must be recorded atomically at the same paper-decision UTC time")
        for e in champion:
            if decimal(e.get("stake"), "ledger.champion.stake") != Decimal("50.00"):
                err("ledger: champion policy stake must be exactly 50 units per leg")


def check_settlements(settlements, ledger):
    """Tamper-evident settlement receipts plus ledger consistency."""
    try:  # works as `python3 -m scripts.validate` and as `python3 scripts/validate.py`
        from scripts.settle import verify_chain
    except ImportError:
        from settle import verify_chain
    if settlements is None:
        settled = [e for e in (ledger or {}).get("entries", []) if (e.get("settlement") or {}).get("result") not in (None, "pending")]
        if settled:
            err(f"settlements.json: missing while {len(settled)} ledger entries are settled")
        return
    if settlements.get("schema_version") != 1:
        err("settlements: unknown schema version")
        return
    rows = settlements.get("rows")
    if not isinstance(rows, list):
        err("settlements.rows: expected array")
        return
    try:
        verify_chain(rows)
    except Exception as exc:  # chain tampering is fatal for the run
        err(f"settlements: {exc}")
        return
    previous_time = ""
    decisions = {}
    for i, row in enumerate(rows):
        w = f"settlements.rows[{i}]"
        for f in ("receipt_id", "prev_hash", "hash", "recorded_utc", "observed_utc", "entry_id", "kind", "observation"):
            if f not in row:
                err(f"{w}: missing field {f}")
        check_iso(row.get("recorded_utc"), w + ".recorded_utc")
        check_iso(row.get("observed_utc"), w + ".observed_utc")
        if row.get("recorded_utc", "") < previous_time:
            err(f"{w}: recorded_utc moved backwards; journal must be append-only")
        previous_time = row.get("recorded_utc", "")
        if row.get("kind") not in {"venue_resolution", "result_confirmation", "settlement_decision", "settlement_hold"}:
            err(f"{w}: unknown receipt kind {row.get('kind')!r}")
        if row.get("source_url"):
            check_url(row.get("source_url"), w)
        if row.get("kind") == "settlement_decision":
            if row.get("entry_id") in decisions:
                err(f"{w}: duplicate settlement decision for {row.get('entry_id')}")
            decisions[row.get("entry_id")] = row.get("observation") or {}
    entry_ids = {e.get("entry_id"): e for e in (ledger or {}).get("entries", []) if isinstance(e, dict)}
    for entry_id, observation in decisions.items():
        entry = entry_ids.get(entry_id)
        if not entry:
            err(f"settlements: decision receipt for unknown ledger entry {entry_id!r}")
            continue
        settlement = entry.get("settlement") or {}
        if settlement.get("result") == "pending":
            err(f"settlements: decision receipt exists but ledger entry {entry_id} is still pending")
        if observation.get("result") != settlement.get("result") or observation.get("payout") != str(entry.get("payout")):
            err(f"settlements: decision receipt disagrees with ledger entry {entry_id}")
    for e in (ledger or {}).get("entries", []):
        result = (e.get("settlement") or {}).get("result")
        if result not in (None, "pending") and e.get("entry_id") not in decisions:
            err(f"settlements: settled ledger entry {e.get('entry_id')} has no settlement_decision receipt")


def check_player_stats(stats):
    """A dated, sourced player-stat window must exist before any rating row."""
    if stats is None:
        return
    policy = stats.get("policy") or {}
    for f in ("source_name", "source_url", "window_days", "min_maps", "metric", "defined_utc"):
        if f not in policy:
            err(f"player_stats.policy: missing field {f}")
    if policy.get("source_url"):
        check_url(policy.get("source_url"), "player_stats.policy.source_url")
    check_iso(policy.get("defined_utc"), "player_stats.policy.defined_utc")
    if not isinstance(policy.get("window_days"), int) or policy.get("window_days") <= 0 or policy.get("window_days") > 365:
        err("player_stats.policy: window_days must be a positive int ≤ 365")
    players = stats.get("players")
    if not isinstance(players, list):
        err("player_stats.players: expected array")
        return
    for i, p in enumerate(players):
        w = f"player_stats.players[{i}]"
        for f in ("player", "team_id", "metric", "value", "window_start_utc", "window_end_utc",
                  "source_url", "observed_utc", "maps_played"):
            if f not in p:
                err(f"{w}: missing field {f}")
        for f in ("window_start_utc", "window_end_utc", "observed_utc"):
            check_iso(p.get(f), w + "." + f)
        check_url(p.get("source_url"), w + ".source_url")
        if p.get("metric") != policy.get("metric"):
            err(f"{w}: metric must match the declared policy metric")
        try:
            days = (datetime.strptime(p["window_end_utc"], "%Y-%m-%dT%H:%M:%SZ") -
                    datetime.strptime(p["window_start_utc"], "%Y-%m-%dT%H:%M:%SZ")).days
            if days != policy.get("window_days"):
                err(f"{w}: window length disagrees with policy")
        except (KeyError, TypeError, ValueError):
            err(f"{w}: invalid stat window timestamps")


def check_historical_matches(items):
    if items is None:
        err("historical_matches.json: missing")
        return
    if not isinstance(items, list) or len(items) < 10:
        err(f"historical_matches: expected >=10 entries, got {len(items) if isinstance(items, list) else type(items)}")
        return
    seen = set()
    for i, m in enumerate(items):
        w = f"historical_matches[{i}]"
        if not isinstance(m, dict):
            err(f"{w}: expected object")
            continue
        for f in ("id", "date", "event", "stage", "team_a", "team_b", "winner", "score", "sources", "verified_utc"):
            if f not in m:
                err(f"{w}: missing field {f}")
        if m.get("id") in seen:
            err(f"{w}: duplicate id {m.get('id')}")
        seen.add(m.get("id"))
        if m.get("id") and not re.match(r"^HIST-\d{3}$", m["id"]):
            err(f"{w}: id must match HIST-###, got {m['id']!r}")
        check_iso(m.get("date"), w + ".date")
        check_iso(m.get("verified_utc"), w + ".verified_utc")
        check_sources(m.get("sources"), w)
        if not m.get("team_a") or not m.get("team_b") or not m.get("winner"):
            err(f"{w}: team_a/team_b/winner required")
        # winner must be one of the two teams
        if m.get("winner") not in {m.get("team_a"), m.get("team_b")}:
            err(f"{w}: winner must be team_a or team_b")

def check_historical_odds(data):
    if data is None:
        err("historical_odds.json: missing")
        return
    if not isinstance(data, dict):
        err("historical_odds: expected object")
        return
    meta = data.get("meta") or {}
    if not meta.get("note"):
        err("historical_odds.meta: missing note")
    real = data.get("real_markets")
    if not isinstance(real, list):
        err("historical_odds.real_markets: expected array")
    else:
        for i, rm in enumerate(real):
            w = f"historical_odds.real_markets[{i}]"
            if not rm.get("id") or not rm.get("source_url"):
                err(f"{w}: missing id/source_url")
            check_url(rm.get("source_url"), w)
            if rm.get("review_url"):
                check_url(rm.get("review_url"), w)
    policy = data.get("modeled_policy") or {}
    if not policy.get("formula"):
        err("historical_odds.modeled_policy: missing formula")

def check_backtest_results(data, strategies):
    if data is None:
        err("backtest_results.json: missing")
        return
    if not isinstance(data, dict):
        err("backtest_results: expected object")
        return
    meta = data.get("meta") or {}
    for f in ("generated_utc", "matches_count", "ledger_entries"):
        if f not in meta:
            err(f"backtest_results.meta: missing {f}")
    if "generated_utc" in meta:
        check_iso(meta["generated_utc"], "backtest_results.meta.generated_utc")
    strats = data.get("strategies")
    if not isinstance(strats, list) or len(strats) < 1:
        err("backtest_results.strategies: expected non-empty array")
        return
    strat_names = {s.get("username") for s in strategies or []}
    for i, s in enumerate(strats):
        w = f"backtest_results.strategies[{i}]"
        if s.get("username") not in strat_names:
            err(f"{w}: unknown username {s.get('username')!r}")
        for f in ("total_bets", "wins", "losses", "profit", "bankroll"):
            if f not in s:
                err(f"{w}: missing field {f}")

def check_backtest_ledger(data, historical_ids):
    if data is None:
        err("backtest_ledger.json: missing")
        return
    if not isinstance(data, dict):
        err("backtest_ledger: expected object")
        return
    meta = data.get("meta") or {}
    if "generated_utc" in meta:
        check_iso(meta["generated_utc"], "backtest_ledger.meta.generated_utc")
    entries = data.get("entries")
    if not isinstance(entries, list):
        err("backtest_ledger.entries: expected array")
        return
    seen = set()
    for i, e in enumerate(entries):
        w = f"backtest_ledger.entries[{i}]"
        if not isinstance(e, dict):
            err(f"{w}: expected object")
            continue
        for f in ("entry_id", "username", "match_id", "date", "team_a", "team_b", "winner", "pick", "decimal_odds", "stake", "profit", "result", "odds_type", "sources"):
            if f not in e:
                err(f"{w}: missing field {f}")
        if e.get("entry_id") in seen:
            err(f"{w}: duplicate entry_id {e.get('entry_id')}")
        seen.add(e.get("entry_id"))
        if e.get("match_id") not in historical_ids:
            err(f"{w}: match_id {e.get('match_id')!r} not in historical_matches")
        check_iso(e.get("date"), w + ".date")
        check_sources(e.get("sources"), w, require=True)
        if e.get("odds_type") not in {"MODELED", "VERIFIED"}:
            err(f"{w}: odds_type must be MODELED or VERIFIED, got {e.get('odds_type')!r}")
        if e.get("result") not in {"win", "loss"}:
            err(f"{w}: result must be win/loss, got {e.get('result')!r}")
        # profit math
        try:
            stake = Decimal(str(e.get("stake")))
            odds = Decimal(str(e.get("decimal_odds")))
            profit = Decimal(str(e.get("profit")))
            if e.get("result") == "win":
                expected = (stake * (odds - Decimal("1"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if abs(profit - expected) > Decimal("0.02"):
                    err(f"{w}: profit {profit} does not match win math {expected}")
            else:
                if profit != -stake:
                    err(f"{w}: loss profit must be -stake, got {profit} vs {-stake}")
        except Exception:
            err(f"{w}: invalid stake/odds/profit math")

def check_html_refs():
    pages = sorted((ROOT).glob("*.html"))
    if not pages:
        err("no HTML pages found at repo root")
    for p in pages:
        text = p.read_text(encoding="utf-8")
        if "assets/app.js" not in text and p.name != "404.html":
            err(f"{p.name}: missing assets/app.js script reference")
        if "assets/style.css" not in text:
            err(f"{p.name}: missing assets/style.css reference")


def check_lab(lab_dir=None, allow_synthetic=False):
    """Real-line strategy lab: receipts (append-only shards) and the derived leaderboard/ledgers.

    Receipts: known venue, allowlisted source URLs, no quote after its checkpoint (no look-ahead) or
    older than the staleness window, prices strictly inside (0,1), winner consistent with settlement.
    Derived: every simulated user labeled, ranks/bankrolls consistent, and each published ledger's
    cost/fee/P&L recomputed with the documented venue fee formulas.
    """
    from scripts import historical_lines as hl
    from scripts import strategy_lab as sl
    lab_dir = Path(lab_dir) if lab_dir else DATA / "lab"
    if not (lab_dir / "lines_meta.json").exists() and not (lab_dir / "lines.json").exists():
        return  # lab not collected yet; nothing to check
    try:
        store = hl.load_store(lab_dir)
    except (hl.LineError, json.JSONDecodeError, KeyError) as e:
        err(f"lab lines: {e}")
        return
    if store.get("mode") not in ("live", "offline-fixture") and not allow_synthetic:
        err(f"lab lines: unexpected mode {store.get('mode')!r}")
    prefixes = (hl.KALSHI + "/", hl.GAMMA + "/", hl.CLOB + "/")
    backs = dict(hl.CHECKPOINTS)
    for line in store["lines"]:
        w = f"lab line {line.get('line_id')}"
        if line.get("venue") not in ("kalshi", "polymarket"):
            err(f"{w}: unknown venue")
            continue
        if len(line.get("teams") or []) != 2 or not ISO.match(line.get("cutoff_utc") or ""):
            err(f"{w}: teams/cutoff malformed")
            continue
        if not allow_synthetic and any(not u.startswith(prefixes) for u in line.get("price_urls") or [""]):
            err(f"{w}: price_url outside the free-source allowlist")
        cutoff = hl.parse_iso(line["cutoff_utc"]).timestamp()
        settle = [float(x) if x is not None else None for x in line.get("settlement") or []]
        win = line.get("winner")
        if win not in (0, 1, None) or (win is not None and (len(settle) != 2 or settle[win] != 1.0)):
            err(f"{w}: winner {win} inconsistent with settlement {line.get('settlement')}")
        for label, pair in (line.get("quotes") or {}).items():
            if label not in backs or not isinstance(pair, list) or len(pair) != 2:
                err(f"{w}: malformed checkpoint {label}")
                continue
            for q in pair:
                if not q:
                    continue
                decision = cutoff - backs[label]
                if not (decision - hl.MAX_STALENESS <= q["t"] <= decision):
                    err(f"{w} {label}: quote time {q['t']} outside [{decision - hl.MAX_STALENESS}, {decision}] (look-ahead/stale)")
                for f in ("ask", "bid", "p"):
                    if q.get(f) is not None and not (0 <= float(q[f]) <= 1):
                        err(f"{w} {label}: {f} {q[f]} outside [0,1]")
    board_path = lab_dir / "leaderboard.json"
    if not board_path.exists():
        return
    board = json.loads(board_path.read_text(encoding="utf-8"))
    strategies = json.loads((lab_dir / "strategies.json").read_text(encoding="utf-8"))
    rows, strats = board.get("rows", []), strategies.get("strategies", [])
    if not board.get("simulated") or not strategies.get("simulated"):
        err("lab leaderboard/strategies: must be labeled simulated")
    if len(strats) < 100 or len(rows) != len(strats):
        err(f"lab: expected >=100 strategies with one leaderboard row each, got {len(strats)}/{len(rows)}")
    if len({x["definition_hash"] for x in strats}) != len(strats) or len({x["username"] for x in strats}) != len(strats):
        err("lab strategies: duplicate definition or username")
    if any(not x["username"].startswith("sim_") for x in strats):
        err("lab strategies: simulated usernames must start with sim_")
    start = board.get("start_bankroll", 1000.0)
    last = None
    for i, r in enumerate(rows, 1):
        a = r["all"]
        if r.get("rank") != i or (last is not None and a["final_bankroll"] > last + 1e-9):
            err(f"lab leaderboard: rank/order broken at {r.get('id')}")
        last = a["final_bankroll"]
        if abs(start + a["pnl"] - a["final_bankroll"]) > 0.01 or a["final_bankroll"] < -1e-6:
            err(f"lab leaderboard {r['id']}: final bankroll != start + pnl, or negative")
    matches_path = lab_dir / "matches.json"
    if not matches_path.exists():
        return
    table = json.loads(matches_path.read_text(encoding="utf-8"))["matches"]
    cps = {x["id"]: x["params"]["cp"] for x in strats}
    for led_path in sorted((lab_dir / "ledgers").glob("S*.json")):
        led = json.loads(led_path.read_text(encoding="utf-8"))
        sid = led.get("strategy_id")
        col = {c: i for i, c in enumerate(led["columns"])}
        for b in led["bets"]:
            w = f"lab ledger {sid} match {b[col['match_idx']]}"
            m = table[b[col["match_idx"]]]
            decision = hl.parse_iso(m["cutoff_utc"]).timestamp() - backs[cps[sid]]
            if b[col["quote_t"]] > decision:
                err(f"{w}: quote after decision time (look-ahead)")
            price, n = b[col["price"]], b[col["contracts"]]
            venue = "kalshi" if b[col["venue"]] == "k" else "polymarket"
            fee = sl.kalshi_fee(int(n), price) if venue == "kalshi" else sl.poly_fee(n, price)
            if venue == "kalshi" and n != int(n):
                err(f"{w}: fractional Kalshi contracts")
            if abs(b[col["cost"]] - round(n * price, 4)) > 1e-4 or abs(b[col["fee"]] - fee) > 1e-4:
                err(f"{w}: cost/fee do not recompute")
            if abs(b[col["payout"]] - round(n * b[col["settle"]], 4)) > 1e-4 or \
                    abs(b[col["pnl"]] - (b[col["payout"]] - b[col["cost"]] - b[col["fee"]])) > 1e-3:
                err(f"{w}: payout/P&L do not recompute")
            if b[col["cost"]] > sl.MAX_STAKE + 1e-6:
                err(f"{w}: stake above the documented cap")


def main():
    master = load("master_list.json")
    teams = load("teams.json")
    matches = load("matches.json")
    market_sources = load("market_sources.json")
    strategies = load("strategies.json")
    ledger = load("ledger.json")
    changes = load("roster_changes.json")
    observations = load("observations.json")
    settlements = load("settlements.json")
    player_stats = load("player_stats.json")
    historical_matches = load("historical_matches.json")
    historical_odds = load("historical_odds.json")
    backtest_results = load("backtest_results.json")
    backtest_ledger = load("backtest_ledger.json")

    master_ids = check_master(master)
    check_teams(teams, master_ids)
    match_ids = check_matches(matches, master_ids)
    fixture_ids = {f.get("id") for f in (observations or {}).get("fixtures", []) if isinstance(f, dict)}
    check_market_sources(market_sources, master_ids)
    users = check_strategies(strategies)
    check_changes(changes, teams, master_ids)
    check_observations(observations, teams)
    paused = {s["username"] for s in (strategies or []) if s.get("status") == "paused"}
    check_ledger(ledger, users, match_ids | fixture_ids, observations, paused)
    check_settlements(settlements, ledger)
    check_player_stats(player_stats)
    check_historical_matches(historical_matches)
    check_historical_odds(historical_odds)
    historical_ids = {m.get("id") for m in (historical_matches or []) if isinstance(m, dict) and m.get("id")}
    check_backtest_results(backtest_results, strategies)
    check_backtest_ledger(backtest_ledger, historical_ids)
    check_lab()
    check_html_refs()

    # Required static assets
    for rel in ("assets/style.css", "assets/app.js", "data/schema.md",
                ".nojekyll"):
        if not (ROOT / rel).exists():
            err(f"required file missing: {rel}")

    if ERRORS:
        print(f"VALIDATION FAILED: {len(ERRORS)} error(s)")
        for e in ERRORS:
            print(" -", e)
        return 1
    n_ledger = len((ledger or {}).get("entries", []))
    n_backtest = len((backtest_ledger or {}).get("entries", []))
    print(f"OK: {len(master or [])} master entries, {len(teams or [])} teams, "
          f"{len(matches or [])} match records, {len(strategies or [])} strategies, "
          f"{n_ledger} ledger entries, {len(historical_matches or [])} historical matches, {n_backtest} backtest bets. All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
