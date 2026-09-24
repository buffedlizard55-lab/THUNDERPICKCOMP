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
import gzip
import hashlib
import io
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

from .hltv import hltv_match_url, parse_hltv_match

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
POLY_TEAM_SEARCH = POLY + "/public-search?limit_per_type=10&events_status=active&q="
POLY_TEAM_LIMIT = 10  # bounded first page per finalist team name


def _finalist_search_names() -> list[str]:
    """Bounded per-team market-search queries derived from data/teams.json.

    Each finalist contributes its committed display name plus, when different,
    a short form with the "Team "/" Team" or " Gaming" org affix removed,
    because prediction-market titles use the short form ("Falcons",
    "Aurora", "BetBoom") rather than the registered org name. The result is a
    small literal list so the per-team discovery pass stays bounded (at most
    13 first-page searches, and it runs only when the keyed searches found no
    open TWC 2026 event)."""
    try:
        names = [str(t.get("name") or "").strip()
                 for t in json.loads(TEAMS_FILE.read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        names = []
    out: list[str] = []
    for name in names:
        if name and name not in out:
            out.append(name)
        short = name
        if short.startswith("Team "):
            short = short[len("Team "):]
        if short.endswith(" Team"):
            short = short[: -len(" Team")]
        if short.endswith(" Gaming"):
            short = short[: -len(" Gaming")]
        if short and short != name and short not in out:
            out.append(short)
    return out or ["FURIA", "Falcons", "Legacy", "Aurora", "BetBoom", "9z", "PARIVISION", "Virtus.pro"]


TEAM_NAMES = _finalist_search_names()
HLTV_MATCH_PATTERN = re.compile(r"^https://www\.hltv\.org/matches/\d{6,9}/?$")
HLTV_MAX_FETCHES = 8  # bounded per run; robots.txt disallows /matches?* listings only
SOURCE_IDS = ("valve_vrs", "liquipedia_fixtures", "hltv_crosscheck", "polymarket_search", "polymarket_tag",
              "polymarket_history", "polymarket_teams", "kalshi_game", "kalshi_outright")


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
        if not url.startswith((GITHUB_LIST, VRS_RAW, POLY + "/", "https://clob.polymarket.com/book?", KALSHI + "/", LIQUIPEDIA_API)) and not HLTV_MATCH_PATTERN.match(url):
            raise SourceError("unapproved source URL")
        headers = {
            "Accept": "application/json" if not text else "text/plain",
            "User-Agent": "THUNDERPICKCOMP/1.0 (+https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/issues; public research)",
        }
        # Liquipedia's MediaWiki API requires gzip-capable clients. urllib does
        # not decompress it for us; other sources keep the default encoding.
        if url == LIQUIPEDIA_API:
            headers["Accept-Encoding"] = "gzip"
        req = Request(url, headers=headers)
        last_error = None
        for attempt in range(3):
            try:
                with urlopen(req, timeout=18) as resp:
                    if resp.status != 200:
                        raise SourceError(f"HTTP {resp.status} for {url}")
                    # Bound both wire bytes and inflated bytes (no gzip bombs).
                    payload = resp.read(4_000_001)
                    if len(payload) > 4_000_000:
                        raise SourceError(f"response exceeds 4MB at {url}")
                    encoding = resp.headers.get("Content-Encoding", "").strip().lower()
                    if encoding == "gzip" and url == LIQUIPEDIA_API:
                        try:
                            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                                payload = stream.read(4_000_001)
                        except (OSError, EOFError) as exc:
                            raise SourceError(f"invalid gzip response at {url}") from exc
                        if len(payload) > 4_000_000:
                            raise SourceError(f"decompressed response exceeds 4MB at {url}")
                    elif encoding not in ("", "identity"):
                        raise SourceError(f"unsupported content encoding {encoding!r} at {url}")
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
        if HLTV_MATCH_PATTERN.match(url):
            # Trimmed, verified-marker excerpt of one real match page; see tests/fixtures/manifest.json.
            match_id = url.rstrip("/").rsplit("/", 1)[-1]
            return (FIXTURES / f"hltv_match_{match_id}.html").read_text(encoding="utf-8")
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
    aliases = {"falcons": "Falcons", "9z": "9z", "aurora": "Aurora", "betboom": "BetBoom"}
    wanted = {aliases.get(t["id"], t["name"]).casefold() for t in teams}
    if len(wanted) != len(teams):
        raise SourceError("finalist VRS team names are ambiguous")
    rows = {}
    for line in markdown.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6 or not re.fullmatch(r"\d+", parts[1]):
            continue
        name = parts[3]
        if name.casefold() not in wanted:
            # Valve ranks rosters, not unique organizations: its full Sep 7
            # file has two different "Just Players" entries, one with four
            # names. Neither is a finalist; only validate rows we publish.
            continue
        try:
            rank, points = int(parts[1]), int(parts[2])
        except ValueError as exc:
            raise SourceError("malformed Valve VRS row: " + name) from exc
        names = [p.strip() for p in parts[4].split(",")]
        if (name.casefold() in rows or len(names) != 5 or not all(names)
                or len(set(names)) != 5 or rank <= 0 or points <= 0):
            raise SourceError("duplicate or malformed finalist Valve VRS row: " + name)
        rows[name.casefold()] = {"rank": rank, "points": points, "roster": names}
    result = []
    for t in teams:
        key = aliases.get(t["id"], t["name"]).casefold()
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


# Timezone abbreviations seen in Liquipedia date templates. Ambiguous tokens
# (CST, IST, ACT...) are deliberately absent: an ambiguous offset is skipped,
# never guessed. Liquipedia writes "|date=September 9, 2026 - 13:15 {{Abbr/CEST}}"
# (the wikitext capture keeps the leading "{{Abbr/" of the token).
LIQUIPEDIA_TZ = {
    "UTC": 0, "GMT": 0, "CET": 1, "CEST": 2, "WET": 0, "WEST": 1, "EET": 2, "EEST": 3,
    "MSK": 3, "TRT": 3, "AST": 3, "GST": 4, "PKT": 5, "BD": 6, "ICT": 7,
    "HKT": 8, "SGT": 8, "JST": 9, "KST": 9, "AEST": 10, "AEDT": 11,
    "NZST": 12, "NZDT": 13, "BRT": -3, "ART": -3, "CLT": -4, "CLST": -3,
    "EDT": -4, "EST": -5, "CDT": -5, "MDT": -6, "MST": -7, "PDT": -7, "PST": -8, "AKDT": -8,
}
LIQUIPEDIA_DATE = re.compile(
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})(?:\s*[-\u2013]\s*(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::\d{2})?)?"
    r"\s*(?:\{\{Abbr/)?(?P<tz>[A-Za-z]{2,9})?",
)
# Alternate stored form: "2026-10-14 13:00 (UTC)"/"...Z" — the explicit UTC
# marker is REQUIRED; a bare ISO timestamp is treated as unspecified local time.
LIQUIPEDIA_ISO_DATE = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[ T]+(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::\d{2})?(?:\s*(?:\(\s*)?(?:UTC|Z)\)?)",
)
MONTH_NUMBERS = {name.lower(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"), start=1)}

TEAM_ALIASES = {
    "falcons": "falcons", "teamfalcons": "falcons", "9z": "9z", "9zteam": "9z",
    "aurora": "aurora", "auroragaming": "aurora", "betboom": "betboom", "betboomteam": "betboom",
    "virtuspro": "virtuspro", "vp": "virtuspro",
}


def canonical_team(token: str, teams: list[dict]) -> str | None:
    """Canonical finalist id for a free-form team token, else None."""
    key = re.sub(r"[^a-z0-9]", "", token.lower())
    if key in TEAM_ALIASES:
        return TEAM_ALIASES[key]
    aliases = {re.sub(r"[^a-z0-9]", "", t["name"].lower()): t["id"] for t in teams}
    return aliases.get(key)


def parse_liquipedia_date(raw: str):
    """Return an aware UTC datetime for a Liquipedia template date, else None.

    A date without an explicit time+offset is NOT scheduled precisely enough
    for a pre-start betting cutoff, so it is skipped (never guessed).
    """
    text = (raw or "").strip()
    match = LIQUIPEDIA_DATE.search(text)
    if match:
        tz_name = (match.group("tz") or "").upper()
        if tz_name in ("", "ABBR/"):
            return None
        if tz_name == "CST":  # ambiguous: China vs US Central
            return None
        if match.group("hh") is None:
            return None
        offset = LIQUIPEDIA_TZ.get(tz_name)
        if offset is None:
            return None
        try:
            dt = datetime(int(match.group("year")), MONTH_NUMBERS[match.group("month").lower()],
                          int(match.group("day")), int(match.group("hh")), int(match.group("mm")),
                          tzinfo=timezone(timedelta(hours=offset)))
        except ValueError:
            return None
        return dt.astimezone(timezone.utc)
    match = LIQUIPEDIA_ISO_DATE.search(text)
    if match:
        try:
            return datetime(int(match.group("year")), int(match.group("month")), int(match.group("day")),
                            int(match.group("hh")), int(match.group("mm")), tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def parse_liquipedia_map_scores(block: str) -> list[list[int]]:
    """Decided-map round totals [[t1,t2], ...] for maps with finished=true.

    Walk-away/forfeit maps (`finished=skip`) are excluded; they do not
    establish a rounds-won result.
    """
    decided = []
    for m in re.finditer(r"\|map\d*=\{\{Map\|map=[^|}]*\|finished=([A-Za-z0-9]+)(.*?)(?=\|map\d*=|\|hltv=|\}\}\n)", block, re.S):
        if m.group(1).lower() != "true":
            continue
        body = m.group(2)
        t1 = re.findall(r"\|(?:o\d)?t1(?:t|ct)=(\d+)", body)
        t2 = re.findall(r"\|(?:o\d)?t2(?:t|ct)=(\d+)", body)
        if not t1 or not t2 or len(t1) > 2 or len(t2) > 2:
            continue
        try:
            total1, total2 = sum(int(x) for x in t1), sum(int(x) for x in t2)
        except ValueError:
            continue
        if total1 == total2 == 0:
            continue
        decided.append([total1, total2])
    return decided


def derive_series_result(decided: list[list[int]]) -> dict:
    """Winner only when decided maps give one side a strict majority; else unknown."""
    wins1 = sum(1 for a, b in decided if a > b)
    wins2 = sum(1 for a, b in decided if b > a)
    if wins1 == wins2 or (wins1 == 0 and wins2 == 0):
        return {"winner": None, "score": None}
    if wins1 > wins2:
        return {"winner": "team_a", "score": [wins1, wins2]}
    return {"winner": "team_b", "score": [wins1, wins2]}


def parse_liquipedia_fixtures(wikitext: str, teams: list[dict]) -> list[dict]:
    """Parse only unambiguous Match templates with a cited HLTV match id and UTC date.

    We intentionally reject novel template/date formats and do not infer results
    beyond counting finished map scores. Empty TBD placeholders are ignored.
    This parser is conservative by design.
    """
    results = wikitext.split("==Results==", 1)
    if len(results) != 2:
        raise SourceError("Liquipedia wikitext missing Results section")
    text = results[1]
    matches = []
    # Track section context so each fixture carries its group/stage label; the
    # main page nests groups under ===Group Stage=== and playoffs after it.
    sections: list[tuple[int, str | None, str]] = []
    for heading in re.finditer(r"(?m)^(=+)([^=\n]+=+)\s*$", text):
        level, label = len(heading.group(1)), heading.group(2).strip().rstrip("=").strip()
        label = re.sub(r"\{\{HiddenSort\|([^}]*)\}\}", r"\1", label).strip()
        if level >= 3 and "group" in label.lower():
            sections.append((heading.start(), re.sub(r"(?i)group\s*", "", label).strip() or "?", "groups"))
        elif "playoff" in label.lower() or "bracket" in label.lower() or "final" in label.lower():
            sections.append((heading.start(), None, "playoffs"))
    # A Match template contains nested Map/TeamOpponent templates. Match ends
    # at next |{{Match or closing matchlist; restrict to fields before |map1.
    offsets = [m.start() for m in re.finditer(r"(?=\|\s*\{\{Match\s*\n)", text)]
    for index, offset in enumerate(offsets):
        block = text[offset:offsets[index + 1] if index + 1 < len(offsets) else len(text)]
        context = ("?", "groups")
        for h_offset, group, stage in sections:
            if h_offset <= offset:
                context = (group, stage)
        header = block.split("|map1=", 1)[0]
        a = re.search(r"\|opponent1=\{\{TeamOpponent\|([^}|]+)", header)
        b = re.search(r"\|opponent2=\{\{TeamOpponent\|([^}|]+)", header)
        date = re.search(r"\|date=([^\n|}]*)", header)
        # Matches may not have an HLTV id at all yet. Never infer from bracket.
        match_id = re.search(r"\|hltv=\s*(\d{6,9})\s*(?:\n|\||\})", block)
        finished = re.search(r"\|finished\s*=\s*([A-Za-z0-9]+)", header)
        if not a or not b or not date or not match_id:
            continue
        raw_date = date.group(1).strip()
        # Require an explicit timezone offset and time; Liquipedia's bare dates
        # are often local tournament time; never guess the offset.
        dt = parse_liquipedia_date(raw_date)
        if dt is None:
            continue
        if not (datetime(2026, 10, 14, tzinfo=timezone.utc) <= dt < datetime(2026, 10, 20, tzinfo=timezone.utc)):
            continue
        ta = canonical_team(a.group(1), teams)
        tb = canonical_team(b.group(1), teams)
        if not ta or not tb or ta == tb:
            continue
        mid = "HLTV-" + match_id.group(1)
        decided = parse_liquipedia_map_scores(block)
        derived = derive_series_result(decided)
        matches.append({
            "id": mid, "hltv_id": match_id.group(1), "team_a": ta, "team_b": tb,
            "scheduled_utc": stamp(dt), "group": context[0], "stage_label": context[1],
            "finished": bool(finished and finished.group(1).lower() == "true"),
            "derived_winner": derived["winner"], "series_score": derived["score"],
            "map_scores": decided,
            "source_url": "https://www.hltv.org/matches/" + match_id.group(1),
            "liquipedia_url": "https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026",
            "observed_utc": None,  # set only when fetched in this run
            "status": "scheduled-unconfirmed",  # HLTV page content not independently checked
            "result_status": "none" if not derived["winner"] else "liquipedia-derived-unconfirmed",
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
            old = existing.get(row["id"])
            if old:
                # Preserve earliest observation; schedule alterations become alerts,
                # never retroactively change a historical pre-match cutoff.
                if old["scheduled_utc"] != row["scheduled_utc"] or {old["team_a"], old["team_b"]} != {row["team_a"], row["team_b"]}:
                    alert(doc, "fixture_changed", "Fixture " + row["id"] + " has changed; review before any settlement.", LIQUIPEDIA_API)
                    continue
                if old.get("result_status") == "confirmed" and (
                    old.get("derived_winner") != row.get("derived_winner") or old.get("series_score") != row.get("series_score")
                ):
                    alert(doc, "fixture_result_changed", "Liquipedia result for " + row["id"] + " changed after confirmation; review before any settlement.", LIQUIPEDIA_API)
                    continue
                # Results may only move toward more information; a confirmed
                # outcome is never downgraded by a re-parse.
                if old.get("result_status") != "confirmed":
                    for field in ("group", "stage_label", "finished", "derived_winner", "series_score", "map_scores", "result_status"):
                        old[field] = row.get(field)
                continue
            doc["fixtures"].append(row)
        check(doc, "liquipedia_fixtures", LIQUIPEDIA_API, checked, "partial", "Matches with explicit UTC date+time, both finalist names and HLTV id in Liquipedia Results. HLTV match content has NOT been verified by this job.", len(fixtures), "Other templates/dates deliberately skipped; no paper bets on unconfirmed fixtures.")
    except (SourceError, KeyError, TypeError, IndexError, AttributeError, ValueError) as exc:
        source_failure(doc, "liquipedia_fixtures", LIQUIPEDIA_API, observed_at(mode, now), exc)


def collect_hltv_crosscheck(doc: dict, fetcher, now: datetime, teams: list[dict], mode: str) -> None:
    """Cross-check Liquipedia fixture rows against HLTV match-page content.

    A fixture is only `scheduled-confirmed` when the HLTV page for the SAME
    match id names the same two teams and the same UTC date. A result is only
    `confirmed` when HLTV's finished series score and Liquipedia's derived map
    result agree. Any disagreement becomes a `conflict` + alert and is
    permanently ineligible for paper trading. Individual /matches/<id> pages
    are robots-permitted and bounded per run; listing pages are never fetched.
    """
    fetched = confirmed = conflicts = 0
    budget = HLTV_MAX_FETCHES
    scope = ("HLTV /matches/<id> pages for Liquipedia-cited fixtures only (max 8/run; robots.txt disallows /matches?* "
             "listing URLs, single match pages are permitted). Confirm needs same HLTV id, both teams and the same UTC date; "
             "results need HLTV series score + Liquipedia map-score agreement. HLTV start clock is viewer-localized and unused.")
    checked_url = "https://www.hltv.org/matches/"
    try:
        for row in doc["fixtures"]:
            if budget <= 0:
                alert(doc, "crosscheck_budget", "HLTV cross-check budget exhausted; some fixtures remain unconfirmed this run.", checked_url)
                break
            if row.get("result_status") == "confirmed":
                continue  # immutable once double-confirmed; no refetch churn
            hltv_id = row.get("hltv_id")
            if not hltv_id:
                continue
            # Fetch only when it adds information: unknown schedule, or a
            # Liquipedia-finished match without a confirmed result.
            if row["status"] == "scheduled-confirmed" and not row.get("finished"):
                continue
            url = hltv_match_url(hltv_id)
            try:
                page = parse_hltv_match(fetcher.get(url, text=True), hltv_id)
            except ValueError as exc:
                alert(doc, "crosscheck_fetch_error", f"HLTV page for {row['id']} unavailable: {str(exc)[:200]}", url)
                continue
            checked = observed_at(mode, now)
            budget -= 1
            fetched += 1
            t1 = canonical_team(page["team1"].split("/", 1)[1].replace("-", " "), teams)
            t2 = canonical_team(page["team2"].split("/", 1)[1].replace("-", " "), teams)
            if not t1 or not t2 or t1 == t2:
                alert(doc, "crosscheck_team_unrecognized", f"HLTV page for {row['id']} names non-finalist or unresolved teams; fixture left unconfirmed.", url)
                continue
            same_teams = {t1, t2} == {row["team_a"], row["team_b"]}
            same_date = bool(page["date_utc"]) and page["date_utc"] == row["scheduled_utc"][:10]
            if same_teams and same_date:
                if row["status"] == "scheduled-unconfirmed":
                    row["status"] = "scheduled-confirmed"
                    row["hltv_verified_utc"] = stamp(checked)
                    confirmed += 1
            else:
                row["status"] = "conflict"
                row["result_status"] = "conflict"
                conflicts += 1
                alert(doc, "crosscheck_conflict",
                      f"Fixture {row['id']}: Liquipedia ({row['team_a']} vs {row['team_b']} on {row['scheduled_utc'][:10]}) disagrees with HLTV "
                      f"(teams {sorted([t1, t2])}, date {page['date_utc']}); excluded from all paper decisions.", url)
                continue
            if page["status"] == "finished" and page["score_team1"] is not None and same_teams:
                if page["score_team1"] == page["score_team2"]:
                    continue  # no series winner established; nothing to confirm
                winner = "team_a" if (t1 == row["team_a"]) == (page["score_team1"] > page["score_team2"]) else "team_b"
                hltv_score = ([page["score_team1"], page["score_team2"]] if t1 == row["team_a"]
                              else [page["score_team2"], page["score_team1"]])
                lp_winner, lp_score = row.get("derived_winner"), row.get("series_score")
                if lp_winner == winner and lp_score == hltv_score:
                    row["result_status"] = "confirmed"
                    row["result"] = {
                        "winner": row["team_a"] if winner == "team_a" else row["team_b"],
                        "series_score": hltv_score,
                        "confirmed_utc": stamp(checked),
                        "sources": [row["liquipedia_url"], url],
                        "note": "Double-sourced: Liquipedia map scores and HLTV series score agree. Derived from scores, not an official ruling.",
                    }
                    confirmed += 1
                elif lp_winner and lp_winner != winner:
                    row["result_status"] = "conflict"
                    conflicts += 1
                    alert(doc, "result_conflict",
                          f"Result conflict for {row['id']}: Liquipedia says {lp_winner} {lp_score}, HLTV says {winner} {hltv_score}. Pending manual review; nothing settles.", url)
                else:
                    row["result_status"] = "hltv-only-unconfirmed"
                    row["hltv_pending_result"] = {"winner": winner, "series_score": hltv_score, "observed_utc": stamp(checked)}
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        source_failure(doc, "hltv_crosscheck", checked_url, observed_at(mode, now), exc)
        return
    check(doc, "hltv_crosscheck", checked_url, observed_at(mode, now),
          "ok" if mode == "live" and not conflicts else "partial", scope, fetched,
          "0 fixtures parsed means the strict Liquipedia parser found no cross-checkable matches yet; an empty result is not proof of absence.")


def collect_poly_teams(doc: dict, fetcher, now: datetime, mode: str) -> None:
    """Bounded second-discovery pass: search each finalist team name for markets.

    Finals match markets may be titled "A vs B" without the word Thunderpick,
    so the Thunderpick-keyed searches alone cannot bound the unknown. This pass
    makes one bounded search per finalist (first 10 active results only) and
    runs ONLY when the Thunderpick-keyed live searches found no OPEN TWC 2026
    event in this same run, keeping request volume bounded.
    """
    url = POLY_TEAM_SEARCH
    checked = observed_at(mode, now)
    if mode != "live":
        check(doc, "polymarket_teams", url, checked, "partial",
              "Per-finalist bounded active searches (first 10 each); runs only in live mode after the Thunderpick-keyed searches found no open TWC 2026 event.",
              0, "Skipped in offline replay: recorded fixtures would fabricate live discovery.")
        return
    saved_events, saved_quotes, saved_checks, saved_alerts = copy.deepcopy(doc["events"]), list(doc["quotes"]), len(doc["checks"]), len(doc["alerts"])
    try:
        # Events seen this run carry last_seen_utc >= this run's attempt stamp.
        open_found = any(e.get("status") == "open" and str(e.get("last_seen_utc") or "") >= str(doc.get("last_attempt_utc") or "")
                         for e in doc["events"])
        if open_found:
            check(doc, "polymarket_teams", url, checked, "ok",
                  "Per-finalist bounded active searches (first 10 each); runs only after the Thunderpick-keyed searches found no open TWC 2026 event.",
                  0, "Open TWC 2026 event already discovered by the keyed searches this run; extra queries skipped.")
            return
        scanned = 0
        for team in TEAM_NAMES:
            team_url = POLY_TEAM_SEARCH + urlencode({"q": team})
            payload = fetcher.get(team_url)
            items, more = poly_events(payload)
            scanned += len(items)
            if more:
                alert(doc, "truncated_search", f"polymarket_teams[{team}]: more pages may exist; scope limited.", team_url)
            for e in items[:POLY_TEAM_LIMIT]:
                if not twc_event(e):
                    continue
                eid = str(e.get("id") or "")
                slug = str(e.get("slug") or "")
                if not eid or not re.fullmatch(r"[a-z0-9-]+", slug):
                    raise SourceError("relevant Polymarket event missing id/slug")
                save_event(doc, {
                    "key": "polymarket:" + eid, "venue": "Polymarket (international)", "id": eid,
                    "title": e["title"], "stage": stage_of(e["title"]),
                    "status": "closed" if e.get("closed") is True else "open",
                    "first_seen_utc": stamp(checked), "last_seen_utc": stamp(checked),
                    "source_url": team_url,
                    "review_url": POLY.replace("gamma-api.", "") + "/event/" + slug,
                })
        check(doc, "polymarket_teams", url, checked, "partial",
              "Per-finalist bounded active searches (first 10 each); runs only after the Thunderpick-keyed searches found no open TWC 2026 event.",
              scanned, f"Searched {len(TEAM_NAMES)} finalist names; first-page results only, not a complete enumeration.")
    except (SourceError, KeyError, TypeError, IndexError, AttributeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
        doc["events"], doc["quotes"] = saved_events, saved_quotes
        doc["checks"] = doc["checks"][:saved_checks]
        doc["alerts"] = doc["alerts"][:saved_alerts]
        source_failure(doc, "polymarket_teams", url, observed_at(mode, now), exc)


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
    collect_hltv_crosscheck(doc, fetcher, now, teams, mode)
    collect_poly(doc, fetcher, now, mode)
    collect_poly_teams(doc, fetcher, now, mode)
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
