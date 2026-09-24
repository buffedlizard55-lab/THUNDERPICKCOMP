#!/usr/bin/env python3
"""Forward-only collection from free, public, first-party/official-data endpoints.

Run from the repository root: python3 -m scripts.collect [--fixtures]

The published JSON records the *scope* of each check. No query can prove that a
market does not exist outside its scope. A price observation is NOT a trade or a
backdated bet. Settlement is deliberately not automatic without independent result
verification. See data/schema.md and README.md for the limits of this pipeline.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "observations.json"
TEAMS_FILE = ROOT / "data" / "teams.json"
FIXTURES = ROOT / "tests" / "fixtures"
GITHUB_LIST = "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/invitation/2026"
VRS_RAW = "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/main/invitation/2026/"
POLY = "https://gamma-api.polymarket.com"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
LIQUIPEDIA_API = ("https://liquipedia.net/counterstrike/api.php?" + urlencode({
    "action": "parse", "page": "Thunderpick/World_Championship/2026", "prop": "wikitext", "format": "json"
}))
POLY_ACTIVE = POLY + "/public-search?" + urlencode({"q": "Thunderpick", "limit_per_type": 25, "events_status": "active"})
POLY_TAG = POLY + "/events?" + urlencode({"closed": "false", "limit": 60, "order": "startDate", "ascending": "false", "tag_slug": "counter-strike"})
POLY_HISTORY = POLY + "/public-search?" + urlencode({"q": "thunderpick", "limit_per_type": 20})
KALSHI_SERIES = ("KXCS2GAME", "KXCS2")  # official series; map markets not yet monitored
KALSHI_LIMIT = 200
KALSHI_MAX_PAGES = 3  # bounded calls; mark partial if cursor continues
MAX_MARKETS = 120  # bounded parsing; fail visibly instead of silently dropping data
MAX_QUOTE_AGE = timedelta(minutes=10)
SOURCE_IDS = ("valve_vrs", "liquipedia_fixtures", "polymarket_search", "polymarket_tag", "polymarket_history", "kalshi_game", "kalshi_outright")


class SourceError(ValueError):
    """A network, schema, or source-content problem that must be shown publicly."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def observed_at(mode: str, reference: datetime) -> datetime:
    # Timestamp each HTTP receipt AFTER it arrives. The run start is not the
    # same as the exchange book time or HTTP receipt time.
    return utc_now() if mode == "live" else reference


def stamp(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise SourceError("timezone missing")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("no UTC offset")
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError) as e:
        raise SourceError(f"invalid source timestamp {value!r}") from e


def money(value: object, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise InvalidOperation()
    except (InvalidOperation, TypeError, ValueError) as e:
        raise SourceError(f"invalid {name}: {value!r}") from e
    return number


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def jdump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


class Fetcher:
    """Bounded HTTP GET; no credentials, no paid source, no browser-side CORS."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, *, text: bool = False):
        self.calls.append(url)
        if not url.startswith((GITHUB_LIST, VRS_RAW, POLY + "/", "https://clob.polymarket.com/book?", KALSHI + "/", LIQUIPEDIA_API)):
            raise SourceError("unapproved source URL")
        req = Request(url, headers={
            "Accept": "application/json" if not text else "text/plain",
            "User-Agent": "THUNDERPICKCOMP/1.0 (+https://github.com/buffedlizard55-lab/THUNDERPICKCOMP; public research)",
        })
        last_error = None
        for attempt in range(3):
            try:
                with urlopen(req, timeout=18) as resp:
                    if resp.status != 200:
                        raise SourceError(f"HTTP {resp.status} for {url}")
                    # Do not download arbitrarily large or unexpected responses.
                    payload = resp.read(4_000_001)
                    if len(payload) > 4_000_000:
                        raise SourceError(f"response exceeds 4MB at {url}")
                    decoded = payload.decode("utf-8")
                    return decoded if text else json.loads(decoded)
            except (HTTPError, URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
                last_error = exc
                if isinstance(exc, HTTPError) and exc.code < 500 and exc.code != 429:
                    break
                if attempt < 2:
                    time.sleep(attempt + 1)
        raise SourceError(f"fetch failed for {url}: {type(last_error).__name__} {last_error}") from last_error


class FixtureFetcher:
    """Recorded, PARTIAL source responses for offline replay. Never used to bet."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, *, text: bool = False):
        self.calls.append(url)
        mapping = {
            GITHUB_LIST: "vrs_listing_2026.json",
            VRS_RAW + "standings_global_2026_09_07.md": "vrs_global_2026_09_07.md",
            POLY_ACTIVE: "polymarket_search_thunderpick_active.json",
            POLY_TAG: "polymarket_events_counter_strike_open.json",
            POLY_HISTORY: "polymarket_event_twc26_qualifier_closed.json",
            KALSHI + "/events?" + urlencode({"series_ticker": "KXCS2GAME", "status": "open", "limit": KALSHI_LIMIT}): "kalshi_events_game_open.json",
            KALSHI + "/events?" + urlencode({"series_ticker": "KXCS2", "status": "open", "limit": KALSHI_LIMIT}): "kalshi_events_outright_open.json",
            LIQUIPEDIA_API: "liquipedia_current_wikitext.json",
        }
        if url not in mapping:
            raise SourceError(f"no recorded fixture for {url}; offline discovery is not exhaustive")
        contents = (FIXTURES / mapping[url]).read_text(encoding="utf-8")
        return contents if text else json.loads(contents)


def empty() -> dict:
    return {
        "schema_version": 1,
        "last_attempt_utc": None,
        "last_completed_utc": None,
        "mode": "not-run",
        "checks": [],
        "vrs_history": [],
        "roster_signals": [],
        "fixtures": [],
        "events": [],
        "quotes": [],
        "alerts": [],
    }


def check(doc: dict, source: str, url: str, now: datetime, status: str, scope: str, count: int = 0, detail: str = "") -> None:
    doc["checks"].append({
        "source": source, "url": url, "checked_utc": stamp(now),
        "status": status, "scope": scope, "records_checked": count, "detail": detail,
    })


def alert(doc: dict, code: str, message: str, url: str = "") -> None:
    # Alerts describe limited coverage/errors, NOT claims that no market exists.
    doc["alerts"].append({"code": code, "message": message, "source_url": url})


def source_failure(doc: dict, source: str, url: str, now: datetime, exc: Exception) -> None:
    msg = str(exc)[:320]
    check(doc, source, url, now, "error", "No conclusion: source could not be checked.", detail=msg)
    alert(doc, "source_error", source + ": " + msg, url)


def parse_vrs(markdown: str, date: str, teams: list[dict]) -> list[dict]:
    if not re.search(rf"Standings as of {date.replace('-', '_')}", markdown):
        raise SourceError("Valve snapshot date does not match file name")
    rows = {}
    for line in markdown.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6 or not re.fullmatch(r"\d+", parts[1]):
            continue
        rank, points = int(parts[1]), int(parts[2])
        name, names = parts[3], [p.strip() for p in parts[4].split(",")]
        if name.casefold() in rows or len(names) != 5 or len(set(names)) != 5 or points <= 0:
            raise SourceError("duplicate or malformed Valve VRS row: " + name)
        rows[name.casefold()] = {"rank": rank, "points": points, "roster": names}
    result = []
    for t in teams:
        key = {"falcons": "Falcons", "9z": "9z", "aurora": "Aurora", "betboom": "BetBoom"}.get(t["id"], t["name"])
        key = key.casefold()
        # A missing ranked team is not rank=unranked: it may be beyond the
        # downloaded excerpt. Reject the whole snapshot until verified.
        if key not in rows:
            raise SourceError(f"Valve snapshot missing finalist: {key} (possibly truncated)")
        r = rows[key]
        result.append({"team_id": t["id"], **r})
    return result


def collect_vrs(doc: dict, fetcher, now: datetime, teams: list[dict], mode: str) -> None:
    try:
        listing = fetcher.get(GITHUB_LIST)
        if not isinstance(listing, list):
            raise SourceError("GitHub contents API returned a non-list")
        names = [p["name"] for p in listing if p.get("type") == "file" and
                 re.fullmatch(r"standings_global_2026_\d{2}_\d{2}\.md", p.get("name", ""))]
        if not names:
            raise SourceError("no Global VRS standings files in GitHub listing")
        latest = max(names)
        date = latest.removeprefix("standings_global_").removesuffix(".md").replace("_", "-")
        if date > observed_at(mode, now).date().isoformat():
            raise SourceError("Valve listing has a future-dated snapshot")
        url = VRS_RAW + latest
        raw = fetcher.get(url, text=True)
        checked = observed_at(mode, now)
        ranking = parse_vrs(raw, date, teams)
        if doc["vrs_history"] and doc["vrs_history"][-1]["snapshot_date"] > date:
            raise SourceError("Valve ranking moved backwards; keep the prior snapshot")
        snapshot = {"snapshot_date": date, "observed_utc": stamp(checked), "url": url, "teams": ranking}
        if not doc["vrs_history"] or doc["vrs_history"][-1]["snapshot_date"] != date:
            old = doc["vrs_history"][-1] if doc["vrs_history"] else None
            doc["vrs_history"].append(snapshot)
            if old:
                previous = {r["team_id"]: r for r in old["teams"]}
                for row in ranking:
                    old_names = set(previous[row["team_id"]]["roster"])
                    new_names = set(row["roster"])
                    if old_names == new_names:
                        continue
                    signal = {
                        "id": sha("vrs:" + row["team_id"] + ":" + old["snapshot_date"] + ":" + date),
                        "team_id": row["team_id"], "old_snapshot_date": old["snapshot_date"],
                        "new_snapshot_date": date, "removed": sorted(old_names - new_names),
                        "added": sorted(new_names - old_names), "old_url": old["url"], "new_url": url,
                        "note": "Valve VRS ranking-roster difference between two dated snapshots; NOT a confirmed roster transfer or its effective date.",
                    }
                    doc["roster_signals"].append(signal)
        # Do NOT advance a historical observation timestamp just because we re-fetched it.
        check(doc, "valve_vrs", url, checked, "partial" if mode != "live" else "ok", "Latest published Valve Global VRS snapshot (ranked roster; not necessarily today's starting five). Offline replay contains only finalist rows.", len(ranking), "Snapshot date " + date)
    except (SourceError, KeyError, TypeError, IndexError, AttributeError, ValueError) as exc:
        source_failure(doc, "valve_vrs", GITHUB_LIST, observed_at(mode, now), exc)


def parse_liquipedia_fixtures(wikitext: str, teams: list[dict]) -> list[dict]:
    """Parse only unambiguous Match templates with a cited HLTV match id and UTC date.

    We intentionally reject novel template/date formats and do not infer results.
    Empty TBD placeholders are ignored. This parser is conservative by design.
    """
    results = wikitext.split("==Results==", 1)
    if len(results) != 2:
        raise SourceError("Liquipedia wikitext missing Results section")
    text = results[1]
    matches = []
    # A Match template contains nested Map/TeamOpponent templates. Match ends
    # at next |{{Match or closing matchlist; restrict to fields before |map1.
    for block in re.split(r"(?=\|\s*\{\{Match\s*\n)", text)[1:]:
        header = block.split("|map1=", 1)[0]
        a = re.search(r"\|opponent1=\{\{TeamOpponent\|([^}|]+)", header)
        b = re.search(r"\|opponent2=\{\{TeamOpponent\|([^}|]+)", header)
        date = re.search(r"\|date=([^\n|}]*)", header)
        # Matches may not have an HLTV id at all yet. Never infer from bracket.
        match_id = re.search(r"\|hltv=\s*(\d{6,9})\s*(?:\n|\||})", block)
        if not a or not b or not date or not match_id:
            continue
        raw_date = date.group(1).strip()
        # Require an explicit UTC offset or Z. Liquipedia's bare dates often
        # mean local tournament time; never guess the offset.
        try:
            dt = parse_time(raw_date)
        except SourceError:
            continue
        if not (datetime(2026, 10, 14, tzinfo=timezone.utc) <= dt < datetime(2026, 10, 20, tzinfo=timezone.utc)):
            continue
        aliases = {re.sub(r"[^a-z0-9]", "", t["name"].lower()): t["id"] for t in teams}
        aliases.update({"falcons": "falcons", "teamfalcons": "falcons", "9z": "9z", "9zteam": "9z", "aurora": "aurora", "auroragaming": "aurora", "betboom": "betboom", "betboomteam": "betboom", "virtuspro": "virtuspro"})
        ta = aliases.get(re.sub(r"[^a-z0-9]", "", a.group(1).lower()))
        tb = aliases.get(re.sub(r"[^a-z0-9]", "", b.group(1).lower()))
        if not ta or not tb or ta == tb:
            continue
        mid = "HLTV-" + match_id.group(1)
        matches.append({
            "id": mid, "team_a": ta, "team_b": tb, "scheduled_utc": stamp(dt),
            "source_url": "https://www.hltv.org/matches/" + match_id.group(1),
            "liquipedia_url": "https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026",
            "observed_utc": None,  # set only when fetched in this run
            "status": "scheduled-unconfirmed",  # HLTV page content not independently checked
            "note": "Liquipedia fixture template; HLTV match id present, but source page content not cross-checked yet. Not eligible for paper trading.",
        })
    ids = [x["id"] for x in matches]
    if len(ids) != len(set(ids)):
        raise SourceError("same HLTV fixture id repeated in Liquipedia Results")
    return matches


def collect_liquipedia(doc: dict, fetcher, now: datetime, teams: list[dict], mode: str) -> None:
    try:
        payload = fetcher.get(LIQUIPEDIA_API)
        checked = observed_at(mode, now)
        raw = payload["parse"]["wikitext"]["*"]
        if not isinstance(raw, str) or "Thunderpick World Championship 2026" not in raw[:500]:
            raise SourceError("unexpected Liquipedia page identity")
        fixtures = parse_liquipedia_fixtures(raw, teams)
        results = raw.split("==Results==", 1)[1]
        if not fixtures and re.search(r"\|team[1-4]=\s*(?!tbd\b)[A-Za-z0-9]", results, re.I):
            alert(doc, "draw_without_fixtures", "Liquipedia group table appears populated, but strict fixture parser found no cross-referenced UTC match. Review source format.", LIQUIPEDIA_API)
        existing = {m["id"]: m for m in doc["fixtures"]}
        for row in fixtures:
            row["observed_utc"] = stamp(checked)
            # Preserve earliest observation; schedule alterations become alerts,
            # never retroactively change a historical pre-match cutoff.
            if row["id"] in existing:
                old = existing[row["id"]]
                if old["scheduled_utc"] != row["scheduled_utc"] or {old["team_a"], old["team_b"]} != {row["team_a"], row["team_b"]}:
                    alert(doc, "fixture_changed", "Fixture " + row["id"] + " has changed; review before any settlement.", LIQUIPEDIA_API)
                continue
            doc["fixtures"].append(row)
        check(doc, "liquipedia_fixtures", LIQUIPEDIA_API, checked, "partial", "Matches with explicit UTC date, both finalist names and HLTV id in Liquipedia Results. HLTV match content has NOT been verified by this job.", len(fixtures), "Other templates/dates deliberately skipped; no paper bets on unconfirmed fixtures.")
    except (SourceError, KeyError, TypeError, IndexError, AttributeError, ValueError) as exc:
        source_failure(doc, "liquipedia_fixtures", LIQUIPEDIA_API, observed_at(mode, now), exc)


def twc_event(event: dict) -> bool:
    title = str(event.get("title") or "").lower()
    # No 'Thunderpick' substring alone (could be another year or regional series).
    years = set(re.findall(r"\b20\d{2}\b", title))
    if years and years != {"2026"}:
        return False
    return bool(re.search(r"thunderpick world championship(?: 2026)?", title) and (
        "2026" in title or re.search(r"\b2026[-/ ]", str(event.get("ticker") or event.get("slug") or "")) or
        "2026" in str(event.get("description") or "")
    ))


def stage_of(title: str) -> str:
    t = title.lower()
    if "qualifier" in t or "series" in t:
        return "qualifier/series"
    if "finals" in t or "final" in t:
        return "finals"
    return "tournament-unspecified"


def save_event(doc: dict, row: dict) -> None:
    old = {e["key"]: e for e in doc["events"]}
    if row["key"] in old:
        # New status reflects the latest first-party API response. Prices remain
        # immutable and are never replaced with a closing/settlement price.
        target = old[row["key"]]
        target.update({k: v for k, v in row.items() if k in {"status", "last_seen_utc", "title", "stage"}})
    else:
        doc["events"].append(row)


def quote(doc: dict, item: dict, now: datetime) -> None:
    price = money(item["raw_price"], "ask")
    if not 0 < price < 1:
        raise SourceError("ask must be between 0 and 1 (exclusive)")
    size = money(item["ask_size"], "ask_size") if item.get("ask_size") is not None else None
    if size is not None and size < 0:
        raise SourceError("negative ask_size")
    updated = parse_time(item["source_updated_utc"]) if item.get("source_updated_utc") else None
    if updated and updated > now + timedelta(seconds=60):
        raise SourceError("market updated in the future")
    status = "fresh" if updated and now - updated <= MAX_QUOTE_AGE and size and size > 0 else "indicative-only"
    item = {**item,
            "quote_id": sha("|".join([item["venue"], item["market_id"], item["selection"], stamp(now), str(price), str(item.get("ask_size")), str(item.get("source_updated_utc"))])),
            "observed_utc": stamp(now), "quote_status": status,
            "note": "Observed public best ask; not an actual fill. Gross payout only; fees, slippage, and execution not modeled."}
    if item["quote_id"] not in {q["quote_id"] for q in doc["quotes"]}:
        doc["quotes"].append(item)


def safe_outcomes(market: dict) -> list[tuple[str, str]]:
    outcomes = market.get("outcomes")
    tokens = market.get("clobTokenIds")
    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    if not isinstance(outcomes, list) or not isinstance(tokens, list) or len(outcomes) != len(tokens) or not 1 <= len(outcomes) <= 20:
        raise SourceError("Polymarket outcomes and CLOB token IDs mismatch")
    if len(set(tokens)) != len(tokens):
        raise SourceError("duplicate CLOB token")
    return list(zip(outcomes, tokens))


def poly_events(payload: object) -> tuple[list[dict], bool]:
    if isinstance(payload, list):
        return payload, False
    if isinstance(payload, dict):
        # Null events is valid only when search explicitly returns zero hits.
        events = payload.get("events")
        page = payload.get("pagination") or {}
        if events is None and page.get("totalResults") == 0:
            return [], False
        if isinstance(events, list):
            return events, bool(page.get("hasMore"))
    raise SourceError("Polymarket events response shape changed")


def collect_poly(doc: dict, fetcher, now: datetime, mode: str) -> None:
    for source, url, scope in (
        ("polymarket_search", POLY_ACTIVE, "Search Thunderpick active events, first 25 only; not a complete market enumeration."),
        ("polymarket_tag", POLY_TAG, "First 60 currently open events in the counter-strike tag; other tags/matches may be missed."),
        ("polymarket_history", POLY_HISTORY, "First 20 search results, including historical qualifier events; never use post-match settlement prices as pre-match quotes."),
    ):
        saved_events, saved_quotes, saved_checks, saved_alerts = copy.deepcopy(doc["events"]), list(doc["quotes"]), len(doc["checks"]), len(doc["alerts"])
        try:
            payload = fetcher.get(url)
            checked = observed_at(mode, now)
            items, more = poly_events(payload)
            # A partial offline excerpt must not become an assertion of market absence.
            count = sum(twc_event(e) for e in items)
            capped = more or (source == "polymarket_tag" and len(items) >= 60)
            check(doc, source, url, checked, "partial" if capped or mode != "live" else "ok",
                  scope, len(items), f"{count} TWC 2026 events found in this query" + ("; more pages may exist" if capped else ""))
            if capped:
                alert(doc, "truncated_search", source + " may have more pages/results; scope limited to this query.", url)
            for e in items:
                if not twc_event(e):
                    continue
                eid = str(e.get("id") or "")
                slug = str(e.get("slug") or "")
                if not eid or not re.fullmatch(r"[a-z0-9-]+", slug):
                    raise SourceError("relevant Polymarket event missing id/slug")
                event_key = "polymarket:" + eid
                closed = e.get("closed") is True
                save_event(doc, {
                    "key": event_key, "venue": "Polymarket (international)", "id": eid,
                    "title": e["title"], "stage": stage_of(e["title"]),
                    "status": "closed" if closed else "open", "first_seen_utc": stamp(checked),
                    "last_seen_utc": stamp(checked), "source_url": url,
                    "review_url": POLY.replace("gamma-api.", "") + "/event/" + slug,
                })
                if closed or mode != "live":  # Never quote a resolved market, nor paper-trade fixtures.
                    continue
                markets = e.get("markets")
                if not isinstance(markets, list) or len(markets) > MAX_MARKETS:
                    raise SourceError("invalid/oversized Polymarket markets list")
                for m in markets:
                    if m.get("closed") is True or m.get("active") is not True:
                        continue
                    mid = str(m.get("id") or "")
                    if not mid or not m.get("description"):
                        raise SourceError("Polymarket market missing id or resolution rules")
                    # Every outcome needs its own CLOB ask; Gamma outcomePrices
                    # are NOT executable best asks and must never be used for bets.
                    for selection, token in safe_outcomes(m):
                        book_url = "https://clob.polymarket.com/book?" + urlencode({"token_id": token})
                        # book host is approved separately by Fetcher.
                        book = fetcher.get(book_url)
                        received = observed_at(mode, now)
                        if (str(book.get("asset_id")) != str(token) or not book.get("timestamp") or
                                str(book.get("market")) != str(m.get("conditionId"))):
                            raise SourceError("CLOB book returned wrong outcome token/condition or no timestamp")
                        asks = book.get("asks")
                        if not isinstance(asks, list) or not asks:
                            continue  # no ask means no quoted price
                        sorted_asks = sorted(asks, key=lambda x: money(x["price"], "ask"))
                        best = sorted_asks[0]
                        book_time = datetime.fromtimestamp(int(book["timestamp"]) / 1000, tz=timezone.utc)
                        quote(doc, {
                            "venue": "Polymarket (international)", "event_key": event_key,
                            "market_id": mid, "market_type": "match / map / outright (per question)",
                            "market_title": m["question"], "selection": str(selection),
                            "raw_price": str(best["price"]), "ask_size": str(best["size"]),
                            "price_unit": "USD per $1 winning share", "source_updated_utc": stamp(book_time),
                            "source_url": book_url, "event_url": POLY + "/events/" + eid,
                            "resolution_rule": m["description"],
                            "book_token": str(token),
                        }, received)
        except (SourceError, KeyError, TypeError, IndexError, AttributeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
            doc["events"], doc["quotes"] = saved_events, saved_quotes
            doc["checks"] = doc["checks"][:saved_checks]
            doc["alerts"] = doc["alerts"][:saved_alerts]
            source_failure(doc, source, url, observed_at(mode, now), exc)


def finalist_pair(title: str, teams: list[dict]) -> bool:
    names = re.split(r"\s+vs\.?\s+", title, flags=re.I)
    if len(names) != 2:
        return False
    canon = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    valid = {canon(t["name"]) for t in teams} | {"falcons", "aurora", "betboom", "9z", "virtuspro"}
    return all(canon(n) in valid for n in names) and canon(names[0]) != canon(names[1])


def collect_kalshi(doc: dict, fetcher, now: datetime, teams: list[dict], mode: str) -> None:
    for series, source in zip(KALSHI_SERIES, ("kalshi_game", "kalshi_outright")):
        base = KALSHI + "/events?" + urlencode({"series_ticker": series, "status": "open", "limit": KALSHI_LIMIT})
        page_url = base
        pages = 0
        scanned = 0
        found = 0
        saved_events, saved_quotes, saved_alerts = copy.deepcopy(doc["events"]), list(doc["quotes"]), len(doc["alerts"])
        try:
            while True:
                pages += 1
                response = fetcher.get(page_url)
                events = response.get("events")
                if not isinstance(events, list) or len(events) > KALSHI_LIMIT or not isinstance(response.get("cursor"), str):
                    raise SourceError("Kalshi events response shape/cursor changed")
                scanned += len(events)
                if mode != "live" and response.get("cursor"):
                    # Offline excerpts are incomplete by construction.
                    break
                for e in events:
                    candidate = ("thunderpick" in str(e.get("title") or "").lower() or
                                 (series == "KXCS2GAME" and finalist_pair(e.get("title", ""), teams)))
                    if not candidate:
                        continue
                    event_ticker = str(e.get("event_ticker") or "")
                    if not re.fullmatch(r"[A-Za-z0-9-]+", event_ticker):
                        raise SourceError("Kalshi event missing ticker")
                    markets_url = KALSHI + "/markets?" + urlencode({"event_ticker": event_ticker, "limit": 200})
                    response_markets = fetcher.get(markets_url)
                    received = observed_at(mode, now)
                    markets = response_markets.get("markets")
                    if not isinstance(markets, list) or len(markets) > 200 or response_markets.get("cursor"):
                        raise SourceError("Kalshi markets list malformed or paginated; no silent truncation")
                    relevant = [m for m in markets if twc_event({
                        "title": str(m.get("rules_primary") or "") + " " + str(m.get("rules_secondary") or ""),
                        "ticker": m.get("ticker", "")
                    })]
                    if not relevant:
                        continue
                    found += 1
                    ev_key = "kalshi:" + event_ticker
                    rule_context = relevant[0].get("rules_primary", "")
                    save_event(doc, {
                        "key": ev_key, "venue": "Kalshi", "id": event_ticker,
                        "title": e.get("title") or rule_context,
                        "stage": stage_of(rule_context), "status": "open", "first_seen_utc": stamp(received),
                        "last_seen_utc": stamp(received), "source_url": markets_url,
                        "review_url": KALSHI + "/events/" + event_ticker,
                    })
                    if mode != "live":
                        continue
                    for m in relevant:
                        if m.get("status") not in {"active", "open"}:
                            continue
                        tick = str(m.get("ticker") or "")
                        if not tick or not m.get("rules_primary") or not m.get("rules_secondary"):
                            raise SourceError("Kalshi market missing id or full settlement rules")
                        price = m.get("yes_ask_dollars")
                        if price in (None, "", "0.0000"):
                            continue
                        quote(doc, {
                            "venue": "Kalshi", "event_key": ev_key, "market_id": tick,
                            "market_type": "match winner" if series == "KXCS2GAME" else "tournament winner",
                            "market_title": m.get("title") or "Yes",
                            "selection": m.get("yes_sub_title") or m.get("title") or "Yes",
                            "raw_price": str(price), "ask_size": m.get("yes_ask_size_fp"),
                            "price_unit": "USD per $1 Yes contract", "source_updated_utc": m.get("updated_time"),
                            "source_url": markets_url, "event_url": KALSHI + "/markets/" + tick,
                            "resolution_rule": m["rules_primary"] + "\n" + m["rules_secondary"],
                        }, received)
                cursor = response.get("cursor")
                if not cursor:
                    break
                if pages >= KALSHI_MAX_PAGES:
                    break
                page_url = base + "&" + urlencode({"cursor": cursor})
            partial = mode != "live" or bool(cursor)
            check(doc, source, base, observed_at(mode, now), "partial" if partial else "ok",
                  f"First {pages} page(s) of OPEN events in {series}; match details checked only when both finalists are named or title says Thunderpick. Does not cover map series/closed events.",
                  scanned, f"{found} TWC 2026 events confirmed from market rules" + ("; pagination not exhausted" if cursor else ""))
            if cursor:
                alert(doc, "pagination_limit", f"{series}: more open event pages than scanned; cannot claim no market.", base)
        except (SourceError, KeyError, TypeError, IndexError, AttributeError, ValueError) as exc:
            doc["events"], doc["quotes"] = saved_events, saved_quotes
            doc["alerts"] = doc["alerts"][:saved_alerts]
            source_failure(doc, source, page_url, observed_at(mode, now), exc)


def verify_history(previous: dict) -> None:
    if previous.get("schema_version") != 1:
        raise SourceError("previous published observations use unknown schema; refuse to reset history")
    required_lists = ("checks", "vrs_history", "roster_signals", "fixtures", "events", "quotes", "alerts")
    if any(not isinstance(previous.get(f), list) for f in required_lists):
        raise SourceError("previous published history is invalid; refuse to overwrite")
    if len(previous["quotes"]) > 50000:
        raise SourceError("history exceeds 50,000 quotes; investigate before publishing")
    for f, key in (("quotes", "quote_id"), ("events", "key"), ("fixtures", "id"), ("roster_signals", "id")):
        values = [row.get(key) for row in previous[f]]
        if not all(values) or len(set(values)) != len(values):
            raise SourceError(f"previous {f} history contains missing/duplicate ids")


def collect(previous: dict, fetcher, now: datetime, teams: list[dict], mode: str) -> dict:
    verify_history(previous)
    doc = json.loads(json.dumps(previous))  # never modify the caller's history
    if doc["last_attempt_utc"] and parse_time(doc["last_attempt_utc"]) > now:
        raise SourceError("clock moved backwards since the previous published update")
    doc["last_attempt_utc"] = stamp(now)
    doc["mode"] = mode
    doc["checks"] = []
    doc["alerts"] = []
    collect_vrs(doc, fetcher, now, teams, mode)
    collect_liquipedia(doc, fetcher, now, teams, mode)
    collect_poly(doc, fetcher, now, mode)
    collect_kalshi(doc, fetcher, now, teams, mode)
    doc["last_completed_utc"] = stamp(observed_at(mode, now))
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", action="store_true", help="Replay PARTIAL captured sources offline; never makes simulated trades")
    parser.add_argument("--as-of", help="UTC ISO time for fixture replay (required with --fixtures)")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if args.fixtures != bool(args.as_of):
        parser.error("--fixtures and --as-of must be used together")
    now = parse_time(args.as_of) if args.as_of else utc_now()
    if args.as_of and now > utc_now() + timedelta(seconds=10):
        parser.error("fixture time cannot be in the future")
    if args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
    else:
        previous = empty()
    if args.fixtures and previous.get("mode") == "live":
        parser.error("offline fixture replay must not overwrite a live observation journal")
    teams = json.loads(TEAMS_FILE.read_text(encoding="utf-8"))
    doc = collect(previous, FixtureFetcher() if args.fixtures else Fetcher(), now, teams,
                  "offline-replay" if args.fixtures else "live")
    if not args.fixtures and all(c["status"] == "error" for c in doc["checks"]):
        print("WARNING: all external checks failed; publishing explicit errors and old history, not a zero-result market check", file=sys.stderr)
    # Atomically write only when the entire document is valid. The caller runs
    # scripts/validate.py before deploy; a malformed document never goes live.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(".json.tmp")
    temp.write_text(jdump(doc), encoding="utf-8")
    temp.replace(args.output)
    print(f"Collected {len(doc['checks'])} source checks, {len(doc['vrs_history'])} VRS snapshots, "
          f"{len(doc['fixtures'])} fixtures, {len(doc['events'])} events, {len(doc['quotes'])} immutable quotes; "
          f"{len(doc['alerts'])} alerts ({doc['mode']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
