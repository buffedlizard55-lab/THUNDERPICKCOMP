#!/usr/bin/env python3
"""Validate THUNDERPICKCOMP data files: schema, provenance, references, money math.

Fails (exit 1) on any violation. Run: python3 scripts/validate.py
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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


def check_sources(sources, where, require=True):
    if not sources:
        if require:
            err(f"{where}: missing required sources[]")
        return
    for i, s in enumerate(sources):
        w = f"{where}.sources[{i}]"
        if not s.get("label"):
            err(f"{w}: missing label")
        if not s.get("url") or not URL.match(s["url"]):
            err(f"{w}: url must be https, got {s.get('url')!r}")
        if "accessed_utc" not in s:
            err(f"{w}: missing accessed_utc")
        else:
            check_iso(s["accessed_utc"], w)
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
        if s.get("status") not in {"active", "paused", "retired"}:
            err(f"{w}: bad status {s.get('status')!r}")
    return users


def check_ledger(ledger, users, match_ids):
    if ledger is None:
        return
    w0 = "ledger"
    meta = ledger.get("meta") or {}
    for f in ("simulated", "currency", "settlement_policy", "last_updated_utc"):
        if f not in meta:
            err(f"{w0}.meta: missing field {f}")
    if meta.get("simulated") is not True:
        err(f"{w0}.meta: simulated must be true")
    if "last_updated_utc" in meta:
        check_iso(meta["last_updated_utc"], w0 + ".meta")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        err(f"{w0}: entries must be a list")
        return
    seen = set()
    for i, e in enumerate(entries):
        w = f"{w0}.entries[{i}]"
        for f in ("entry_id", "username", "match_id", "market", "selection",
                  "decimal_odds", "stake", "placed_utc", "price_source",
                  "settlement", "payout", "profit"):
            if f not in e:
                err(f"{w}: missing field {f}")
        if e.get("entry_id") in seen:
            err(f"{w}: duplicate entry_id {e.get('entry_id')}")
        seen.add(e.get("entry_id"))
        if e.get("username") not in users:
            err(f"{w}: unknown username {e.get('username')!r}")
        if e.get("match_id") not in match_ids:
            err(f"{w}: unknown match_id {e.get('match_id')!r}")
        try:
            odds = float(e.get("decimal_odds", 0))
            stake = float(e.get("stake", -1))
        except (TypeError, ValueError):
            err(f"{w}: decimal_odds/stake must be numeric")
            continue
        if odds < 1.01:
            err(f"{w}: decimal_odds must be >= 1.01, got {odds}")
        if stake <= 0:
            err(f"{w}: stake must be > 0, got {stake}")
        if "placed_utc" in e:
            check_iso(e["placed_utc"], w)
        ps = e.get("price_source") or {}
        if not ps.get("venue"):
            err(f"{w}: price_source.venue missing")
        if not (ps.get("ticker") or ps.get("market_id") or ps.get("url")):
            err(f"{w}: price_source needs ticker/market_id/url")
        st = e.get("settlement") or {}
        if st.get("result") not in {"win", "loss", "void", "pending", None}:
            err(f"{w}: bad settlement.result {st.get('result')!r}")
        if st.get("result") in {"win", "loss", "void"} and not st.get("rule"):
            err(f"{w}: settled entry needs settlement.rule")
        # Money math
        try:
            payout = float(e.get("payout"))
            profit = float(e.get("profit"))
        except (TypeError, ValueError):
            err(f"{w}: payout/profit must be numeric")
            continue
        if st.get("result") == "win":
            expect = round(stake * odds, 2)
        elif st.get("result") == "loss":
            expect = 0.0
        elif st.get("result") == "void":
            expect = round(stake, 2)
        else:
            expect = None
        if expect is not None:
            if abs(payout - expect) > 0.01:
                err(f"{w}: payout {payout} != expected {expect} (settlement math)")
            if abs(profit - round(payout - stake, 2)) > 0.01:
                err(f"{w}: profit {profit} != payout - stake")


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


def main():
    master = load("master_list.json")
    teams = load("teams.json")
    matches = load("matches.json")
    market_sources = load("market_sources.json")
    strategies = load("strategies.json")
    ledger = load("ledger.json")

    master_ids = check_master(master)
    check_teams(teams, master_ids)
    match_ids = check_matches(matches, master_ids)
    check_market_sources(market_sources, master_ids)
    users = check_strategies(strategies)
    check_ledger(ledger, users, match_ids)
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
    print(f"OK: {len(master or [])} master entries, {len(teams or [])} teams, "
          f"{len(matches or [])} match records, {len(strategies or [])} strategies, "
          f"{n_ledger} ledger entries. All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
