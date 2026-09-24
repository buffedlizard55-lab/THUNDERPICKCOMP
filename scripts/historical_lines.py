#!/usr/bin/env python3
"""Historical CS2 match-winner lines from free, public, first-party market APIs.

Run from the repository root:
    python3 -m scripts.historical_lines                  # incremental live collection
    python3 -m scripts.historical_lines --audit 40       # re-fetch a random sample, demand exact equality
    python3 -m scripts.historical_lines --fixtures       # offline replay of recorded real responses (tests)

Sources (no key, no paid tier, documented public endpoints):
  * Kalshi series KXCS2GAME: settled match-winner markets (live + /historical tier) and
    hourly candlesticks (yes_bid / yes_ask OHLC). The yes_ask close is the top-of-book ask at
    the candle close; depth is NOT known.
  * Polymarket Gamma "Counter-Strike: A vs B" Match Winner markets + CLOB /prices-history.
    Polymarket history points are a REFERENCE price series, not a confirmed executable ask.

Nothing here invents a line. A record is written only when the venue itself returned it; every
price keeps its source timestamp and the exact request URL that reproduces it. Records whose
start time cannot be established unambiguously, whose settlement is not final, or whose
quotes are stale/illiquid are excluded or flagged, never "repaired" by guessing.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "data" / "lab"
LINES_DIR = LAB / "lines"           # monthly shards: append-friendly, small daily git diffs
META = LAB / "lines_meta.json"      # coverage, exclusions, run status, configuration
LEGACY_SINGLE_FILE = LAB / "lines.json"
AUDIT = LAB / "audit.json"
FIXTURES = ROOT / "tests" / "fixtures" / "lab"

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
SERIES = "KXCS2GAME"
POLY_TAG_IDS = ("100780", "100602")  # Gamma tags "counter strike 2" and "counter-strike"
NEW_YORK = ZoneInfo("America/New_York")
USER_AGENT = "THUNDERPICKCOMP/1.0 (+https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/issues; public research)"

# Checkpoints are measured back from the no-look-ahead cutoff (the EARLIEST credible start).
CHECKPOINTS = (("T-24h", 24 * 3600), ("T-6h", 6 * 3600), ("T-1h", 3600), ("T-0", 300))
MAX_STALENESS = 90 * 60           # a checkpoint quote older than this is "no quote"
WINDOW = 26 * 3600                # history requested before the cutoff
KALSHI_MAX_SPREAD = "0.10"        # documented liquidity gate, applied by the strategy engine
MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                      "Sep", "Oct", "Nov", "Dec"), start=1)}
FULL_MONTHS = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July",
                                           "August", "September", "October", "November", "December"), start=1)}

SOURCE_DOCS = {
    "kalshi_markets": "https://docs.kalshi.com/api-reference/market/get-markets",
    "kalshi_historical": "https://docs.kalshi.com/getting_started/historical_data",
    "kalshi_candlesticks": "https://docs.kalshi.com/api-reference/market/get-market-candlesticks",
    "kalshi_fees": "https://kalshi.com/docs/kalshi-fee-schedule.pdf",
    "polymarket_prices_history": "https://docs.polymarket.com/api-reference/markets/get-prices-history",
    "polymarket_fees": "https://docs.polymarket.com/trading/fees",
    "polymarket_rate_limits": "https://docs.polymarket.com/api-reference/rate-limits",
    "kalshi_rate_limits": "https://docs.kalshi.com/getting_started/rate_limits",
}


class LineError(ValueError):
    """A source record that cannot be used without guessing (permanent exclusion)."""


class FetchError(LineError):
    """Transient transport failure: never a permanent exclusion; retried next run."""


class NotYetFinal(LineError):
    """Market exists but is not finally settled yet: retried next run, never excluded."""


def iso(ts: int | float) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    value = value.strip().replace(" ", "T")
    if value.endswith("+00"):
        value += ":00"
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise LineError(f"naive timestamp {value!r}")
    return dt.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --------------------------------------------------------------------------- HTTP

class Fetcher:
    """Bounded GET against the two allow-listed venues only, polite pacing, 429 backoff."""

    ALLOWED = (KALSHI + "/", GAMMA + "/", CLOB + "/prices-history?")

    def __init__(self, pace: float = 0.12) -> None:
        self.calls = 0
        self.pace = pace
        self._last = 0.0

    def get(self, url: str):
        if not url.startswith(self.ALLOWED):
            raise LineError(f"unapproved source URL {url}")
        wait = self.pace - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        last: Exception | None = None
        for attempt in range(5):
            self._last = time.monotonic()
            self.calls += 1
            try:
                with urlopen(req, timeout=25) as resp:
                    payload = resp.read(8_000_001)
                    if len(payload) > 8_000_000:
                        raise LineError(f"response exceeds 8MB at {url}")
                    return json.loads(payload.decode("utf-8"))
            except HTTPError as exc:
                last = exc
                if exc.code == 404:
                    return None
                if exc.code != 429 and exc.code < 500:
                    break
            except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
                last = exc
            time.sleep(min(30, 1.5 * 2 ** attempt))
        raise FetchError(f"fetch failed for {url}: {type(last).__name__} {last}")


class FixtureFetcher:
    """Recorded real responses (tests/fixtures/lab). Partial by construction."""

    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str):
        self.calls += 1
        f = FIXTURES
        if url.startswith(KALSHI + "/historical/cutoff"):
            return {"market_settled_ts": "2026-07-25T00:00:00Z"}
        if url.startswith(KALSHI + "/historical/markets?"):
            return json.loads((f / "kalshi_historical_markets.json").read_text())
        if url.startswith(KALSHI + "/markets?"):
            return {"cursor": "", "markets": []}
        if "/candlesticks?" in url:
            ticker = re.search(r"/markets/([^/]+)/candlesticks", url).group(1)
            name = f / f"kalshi_candles_{ticker.rsplit('-', 1)[1]}.json"
            return json.loads(name.read_text()) if name.exists() else {"candlesticks": []}
        if url.startswith(GAMMA + "/markets?"):
            offset = int(re.search(r"offset=(\d+)", url).group(1))
            return json.loads((f / "poly_markets_page.json").read_text()) if offset == 0 else []
        if url.startswith(CLOB + "/prices-history?"):
            token = re.search(r"market=(\d+)", url).group(1)
            name = "poly_hist_A.json" if token.startswith("1048708") else "poly_hist_B.json"
            return json.loads((f / name).read_text())
        raise LineError(f"no recorded fixture for {url}")


# --------------------------------------------------------------------------- Kalshi parsing

KALSHI_RULE = re.compile(
    r"wins the (?P<comp>.+?): (?P<a>.+?) vs\. (?P<b>.+?) CS2 match originally scheduled for "
    r"(?P<mon>[A-Z][a-z]{2}) (?P<day>\d{1,2}), (?P<year>\d{4}) at (?P<h>\d{1,2}):(?P<m>\d{2}) "
    r"(?P<ampm>AM|PM) (?P<tz>EDT|EST)\b")
KALSHI_TICKER_TIME = re.compile(r"^KXCS2GAME-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})")


def kalshi_start(rules: str, event_ticker: str) -> tuple[datetime, str]:
    """Scheduled start from the rules text, cross-checked against the event-ticker clock (ET)."""
    m = KALSHI_RULE.search(rules)
    if not m:
        raise LineError("rules text lacks an explicit scheduled time with EDT/EST")
    hour = int(m["h"]) % 12 + (12 if m["ampm"] == "PM" else 0)
    offset = -4 if m["tz"] == "EDT" else -5
    local = datetime(int(m["year"]), MONTHS[m["mon"]], int(m["day"]), hour, int(m["m"]))
    start = (local - timedelta(hours=offset)).replace(tzinfo=timezone.utc)
    t = KALSHI_TICKER_TIME.match(event_ticker)
    if not t:
        raise LineError("event ticker lacks a date/time code")
    yy, mon, dd, hh, mm = t.groups()
    ticker_local = (2000 + int(yy), MONTHS.get(mon.title()), int(dd), int(hh), int(mm))
    if ticker_local != (local.year, local.month, local.day, local.hour, local.minute):
        raise LineError(f"rules time {local} disagrees with ticker clock {ticker_local}")
    # The stated EDT/EST label must be the real New York offset on that date (catches typos).
    real = local.replace(tzinfo=NEW_YORK).utcoffset()
    if real != timedelta(hours=offset):
        raise LineError(f"rules say {m['tz']} but New York offset on {local.date()} is {real}")
    return start, m.group(0)


def dec(value) -> str | None:
    if value is None:
        return None
    return f"{float(value):.4f}"


def candle_field(candle: dict, group: str, name: str):
    g = candle.get(group) or {}
    return g.get(name + "_dollars", g.get(name))


def kalshi_checkpoint(candles: list[dict], cutoff: int) -> dict:
    """For each checkpoint the last candle whose close is at/before it (and not stale)."""
    rows = sorted((c for c in candles if isinstance(c.get("end_period_ts"), int)),
                  key=lambda c: c["end_period_ts"])
    out = {}
    for label, back in CHECKPOINTS:
        at = cutoff - back
        pick = None
        for c in rows:
            if c["end_period_ts"] <= at:
                pick = c
            else:
                break
        if pick is None or at - pick["end_period_ts"] > MAX_STALENESS:
            out[label] = None
            continue
        ask, bid = candle_field(pick, "yes_ask", "close"), candle_field(pick, "yes_bid", "close")
        if ask is None or bid is None:
            out[label] = None
            continue
        out[label] = {"t": pick["end_period_ts"], "ask": dec(ask), "bid": dec(bid),
                      "last": dec(candle_field(pick, "price", "close")),
                      "vol": dec(pick.get("volume_fp", pick.get("volume")))}
    return out


def candle_url(ticker: str, start: int, end: int, historical: bool) -> str:
    q = urlencode({"start_ts": start, "end_ts": end, "period_interval": 60})
    if historical:
        return f"{KALSHI}/historical/markets/{ticker}/candlesticks?{q}"
    return f"{KALSHI}/series/{SERIES}/markets/{ticker}/candlesticks?{q}"


def build_kalshi_line(markets: list[dict], fetcher, cutoff_ts: str) -> dict:
    if len(markets) != 2:
        raise LineError(f"event has {len(markets)} markets, expected 2 team markets")
    a, b = sorted(markets, key=lambda m: m["ticker"])
    event = a["event_ticker"]
    if b["event_ticker"] != event:
        raise LineError("markets belong to different events")
    teams = [a.get("yes_sub_title", "").strip(), b.get("yes_sub_title", "").strip()]
    if not all(teams) or teams[0] == teams[1]:
        raise LineError("missing/duplicate team names")
    start, evidence = kalshi_start(a.get("rules_primary", ""), event)
    start_b, _ = kalshi_start(b.get("rules_primary", ""), event)
    if start_b != start:
        raise LineError("team markets disagree on scheduled time")
    rule = KALSHI_RULE.search(a["rules_primary"])
    if {rule["a"].strip(), rule["b"].strip()} != set(teams):
        raise LineError(f"rules teams {rule['a']!r}/{rule['b']!r} != yes_sub_titles {teams}")
    for m in (a, b):
        if m.get("status") not in ("finalized", "settled") or m.get("result") not in ("yes", "no"):
            raise NotYetFinal(f"{m['ticker']} not finally settled (status={m.get('status')}, result={m.get('result')})")
    sv = [dec(a.get("settlement_value_dollars")), dec(b.get("settlement_value_dollars"))]
    if None in sv:
        raise LineError("settlement value missing")
    winner = None
    if sv == ["1.0000", "0.0000"]:
        winner = 0
    elif sv == ["0.0000", "1.0000"]:
        winner = 1
    cutoff = int(start.timestamp())
    opened = int(parse_iso(a["open_time"]).timestamp())
    first = max(cutoff - WINDOW, opened - 3600)
    settled = max(parse_iso(a["settlement_ts"]), parse_iso(b["settlement_ts"]))
    # Route by the tier that actually listed the market (observed: a market settled after the
    # published cutoff was served only by /historical). Fall back to the other tier if empty.
    historical = a.get("_tier") == "historical" if a.get("_tier") else settled < parse_iso(cutoff_ts)
    quotes, urls = {label: [None, None] for label, _ in CHECKPOINTS}, []
    if first < cutoff:
        for side, m in enumerate((a, b)):
            url = candle_url(m["ticker"], first, cutoff, historical)
            payload = fetcher.get(url)
            if not (payload or {}).get("candlesticks"):  # tier boundary moved between listing and fetch
                alt = candle_url(m["ticker"], first, cutoff, not historical)
                alt_payload = fetcher.get(alt)
                if (alt_payload or {}).get("candlesticks"):
                    url, payload = alt, alt_payload
            urls.append(url)
            for label, q in kalshi_checkpoint((payload or {}).get("candlesticks") or [], cutoff).items():
                quotes[label][side] = q
    comp = rule["comp"].strip()
    flags = []
    if winner is None:
        flags.append("non_binary_settlement")
    if not any(any(q) for q in quotes.values()):
        flags.append("no_prestart_quotes")
    return {
        "line_id": f"K:{event}",
        "venue": "kalshi",
        "market_ids": [a["ticker"], b["ticker"]],
        "competition": comp,
        "format": None,
        "teams": teams,
        "cutoff_utc": iso(cutoff),
        "start_evidence": evidence,
        "settled_utc": iso(settled.timestamp()),
        "settlement": sv,
        "winner": winner,
        "volume": [dec(a.get("volume_fp", a.get("volume"))), dec(b.get("volume_fp", b.get("volume")))],
        "quotes": quotes,
        "price_urls": urls,
        "market_urls": [f"{KALSHI}/{'historical/' if historical else ''}markets/{t}" for t in (a["ticker"], b["ticker"])],
        "review_url": f"{KALSHI}/events/{event}",
        "flags": flags,
    }


def kalshi_markets(fetcher, known: set[str], coverage: dict) -> list[list[dict]]:
    """All settled KXCS2GAME markets from the live and historical tiers, grouped by event."""
    cutoff = (fetcher.get(f"{KALSHI}/historical/cutoff") or {}).get("market_settled_ts")
    if not cutoff:
        raise LineError("Kalshi historical cutoff unavailable")
    coverage["historical_cutoff"] = cutoff
    events: dict[str, list[dict]] = {}
    for tier, base, params in (("live", f"{KALSHI}/markets", {"series_ticker": SERIES, "status": "settled"}),
                               ("historical", f"{KALSHI}/historical/markets", {"series_ticker": SERIES})):
        cursor, pages = "", 0
        while True:
            q = dict(params, limit=1000)
            if cursor:
                q["cursor"] = cursor
            payload = fetcher.get(base + "?" + urlencode(q)) or {}
            pages += 1
            for m in payload.get("markets") or []:
                if m.get("event_ticker", "").startswith(SERIES + "-"):
                    rows = events.setdefault(m["event_ticker"], [])
                    if all(r["ticker"] != m["ticker"] for r in rows):
                        m["_tier"] = tier
                        rows.append(m)
            cursor = payload.get("cursor") or ""
            if not cursor or pages >= 200:
                if cursor:
                    coverage.setdefault("truncated", []).append(base)
                break
    coverage["events_listed"] = len(events)
    return [[cutoff, rows] for key, rows in sorted(events.items()) if f"K:{key}" not in known]


# --------------------------------------------------------------------------- Polymarket parsing

POLY_QUESTION = re.compile(r"^Counter-Strike: (?P<a>.+?) vs\.? (?P<b>.+?)(?: \((?P<fmt>BO\d)\))? - (?P<comp>.+)$")
POLY_SCHEDULED = re.compile(r"initially scheduled for (?P<mon>[A-Z][a-z]+) (?P<day>\d{1,2}), (?P<year>\d{4}) "
                            r"at (?P<h>\d{1,2}):(?P<m>\d{2}) (?P<ampm>AM|PM) ET\b")


def poly_scheduled(description: str) -> datetime | None:
    m = POLY_SCHEDULED.search(description or "")
    if not m or m["mon"] not in FULL_MONTHS:
        return None
    hour = int(m["h"]) % 12 + (12 if m["ampm"] == "PM" else 0)
    local = datetime(int(m["year"]), FULL_MONTHS[m["mon"]], int(m["day"]), hour, int(m["m"]))
    # "ET" is resolved with the published New York DST rules for that date. In the repeated
    # fall-back hour the EARLIER instant is used, keeping the no-look-ahead cutoff conservative.
    return min(local.replace(tzinfo=NEW_YORK, fold=0).astimezone(timezone.utc),
               local.replace(tzinfo=NEW_YORK, fold=1).astimezone(timezone.utc))


def poly_point(history: list[dict], at: int):
    pick = None
    for pt in history:
        if isinstance(pt.get("t"), (int, float)) and pt["t"] <= at:
            if pick is None or pt["t"] >= pick["t"]:
                pick = pt
    if pick is None or at - pick["t"] > MAX_STALENESS or not isinstance(pick.get("p"), (int, float)):
        return None
    return {"t": int(pick["t"]), "p": float(pick["p"])}


def poly_candidate(m: dict) -> bool:
    q = POLY_QUESTION.match(m.get("question") or "")
    title = (m.get("groupItemTitle") or "").strip()
    return bool(q) and title in ("Match Winner", "")


def history_url(token: str, start: int, end: int) -> str:
    return f"{CLOB}/prices-history?" + urlencode({"market": token, "startTs": start, "endTs": end, "fidelity": 10})


def build_poly_line(m: dict, fetcher) -> dict:
    q = POLY_QUESTION.match(m.get("question") or "")
    if not q:
        raise LineError("question is not a Counter-Strike A vs B match")
    outcomes = json.loads(m.get("outcomes") or "[]")
    prices = json.loads(m.get("outcomePrices") or "[]")
    tokens = json.loads(m.get("clobTokenIds") or "[]")
    if len(outcomes) != 2 or len(prices) != 2 or len(tokens) != 2:
        raise LineError("not a two-outcome market")
    if {o.strip() for o in outcomes} != {q["a"].strip(), q["b"].strip()}:
        raise LineError(f"outcomes {outcomes} do not match question teams")
    if not m.get("closed") or m.get("umaResolutionStatus") != "resolved":
        raise NotYetFinal("market not resolved")
    sv = [dec(p) for p in prices]
    if sv not in (["1.0000", "0.0000"], ["0.0000", "1.0000"], ["0.5000", "0.5000"]):
        raise LineError(f"non-final outcome prices {prices}")
    winner = 0 if sv[0] == "1.0000" else 1 if sv[1] == "1.0000" else None
    starts = []
    if m.get("gameStartTime"):
        starts.append(parse_iso(m["gameStartTime"]))
    scheduled = poly_scheduled(m.get("description", ""))
    if scheduled:
        starts.append(scheduled)
    if not starts:
        raise LineError("no gameStartTime or scheduled time")
    cutoff = int(min(starts).timestamp())
    created = int(parse_iso(m["createdAt"]).timestamp()) if m.get("createdAt") else cutoff - WINDOW
    first = max(cutoff - WINDOW, created - 600)
    quotes, urls = {label: [None, None] for label, _ in CHECKPOINTS}, []
    if first < cutoff:
        for side, token in enumerate(tokens):
            url = history_url(token, first, cutoff)
            urls.append(url)
            history = (fetcher.get(url) or {}).get("history") or []
            for label, back in CHECKPOINTS:
                quotes[label][side] = poly_point(history, cutoff - back)
    closed = m.get("closedTime") or m.get("umaEndDate") or m.get("endDate")
    event = (m.get("events") or [{}])[0]
    flags = []
    if winner is None:
        flags.append("resolved_50_50")
    if not any(any(x) for x in quotes.values()):
        flags.append("no_prestart_quotes")
    for label, pair in quotes.items():
        if pair[0] and pair[1] and abs(pair[0]["p"] + pair[1]["p"] - 1) > 0.05:
            flags.append(f"complement_gap_{label}")
    return {
        "line_id": f"P:{m['id']}",
        "venue": "polymarket",
        "market_ids": [str(m["id"])],
        "competition": q["comp"].strip(),
        "format": q["fmt"],
        "teams": [outcomes[0].strip(), outcomes[1].strip()],
        "cutoff_utc": iso(cutoff),
        "start_evidence": f"gameStartTime={m.get('gameStartTime')}; description={scheduled.isoformat() if scheduled else None}",
        "settled_utc": iso(parse_iso(closed).timestamp()) if closed else None,
        "settlement": sv,
        "winner": winner,
        "volume": [dec(m.get("volume")), None],
        "quotes": quotes,
        "price_urls": urls,
        "market_urls": [f"{GAMMA}/markets/{m['id']}"],
        "review_url": f"https://polymarket.com/event/{event.get('slug') or m.get('slug')}",
        "flags": flags,
    }


def poly_markets(fetcher, known: set[str], coverage: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for tag in POLY_TAG_IDS:
        offset, limit, page_ids = 0, 500, set()
        while True:
            url = f"{GAMMA}/markets?" + urlencode({"tag_id": tag, "closed": "true", "limit": limit, "offset": offset,
                                                   "order": "id", "ascending": "false"})
            page = fetcher.get(url) or []
            if not isinstance(page, list):
                raise LineError("unexpected Gamma markets payload")
            ids = {str(m.get("id")) for m in page}
            if not page or ids <= page_ids:
                break  # exhausted (or server ignored offset): stop without assuming page size
            page_ids |= ids
            for m in page:
                if poly_candidate(m):
                    seen.setdefault(str(m["id"]), m)
            offset += len(page)
            if offset >= 150_000:
                coverage.setdefault("truncated", []).append(tag)
                break
    coverage["markets_listed"] = len(seen)
    return [m for mid, m in sorted(seen.items(), key=lambda kv: int(kv[0])) if f"P:{mid}" not in known]


# --------------------------------------------------------------------------- store

def empty_store() -> dict:
    return {
        "schema_version": 1,
        "description": ("Append-only receipts of real historical CS2 match-winner prices from free public venue "
                        "APIs. Kalshi yes_ask = top-of-book ask at candle close (depth unknown); Polymarket p = "
                        "CLOB prices-history reference price (NOT a confirmed executable ask). Checkpoints are "
                        "measured back from the no-look-ahead cutoff (earliest credible scheduled start)."),
        "checkpoints": [{"label": label, "seconds_before_cutoff": back} for label, back in CHECKPOINTS],
        "max_staleness_seconds": MAX_STALENESS,
        "kalshi_max_spread_gate": KALSHI_MAX_SPREAD,
        "source_docs": SOURCE_DOCS,
        "last_run_utc": None,
        "mode": "empty",
        "coverage": {},
        "excluded": {},
        "lines": [],
    }


def save_json(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n",
                    encoding="utf-8")


def load_store(lab: Path = LAB) -> dict:
    """Meta + every monthly shard. Migrates the legacy single-file layout once."""
    meta_path, lines_dir, legacy = lab / "lines_meta.json", lab / "lines", lab / "lines.json"
    if legacy.exists() and not meta_path.exists():
        return json.loads(legacy.read_text(encoding="utf-8"))
    if not meta_path.exists():
        return empty_store()
    store = json.loads(meta_path.read_text(encoding="utf-8"))
    store["lines"] = []
    for shard in sorted(lines_dir.glob("*.json")):
        rows = json.loads(shard.read_text(encoding="utf-8"))
        if any(r["cutoff_utc"][:7] != shard.stem for r in rows):
            raise LineError(f"{shard.name} contains a line from another month")
        store["lines"].extend(rows)
    ids = [r["line_id"] for r in store["lines"]]
    if len(ids) != len(set(ids)):
        raise LineError("duplicate line_id across shards")
    return store


def save_store(store: dict, lab: Path = LAB) -> None:
    lines_dir = lab / "lines"
    months: dict[str, list] = {}
    for row in sorted(store["lines"], key=lambda r: (r["cutoff_utc"], r["line_id"])):
        months.setdefault(row["cutoff_utc"][:7], []).append(row)
    lines_dir.mkdir(parents=True, exist_ok=True)
    for month, rows in months.items():
        # One line per record keeps daily diffs reviewable and small.
        text = "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + "\n]\n"
        (lines_dir / f"{month}.json").write_text(text, encoding="utf-8")
    meta = {k: v for k, v in store.items() if k != "lines"}
    meta["shards"] = {m: len(rows) for m, rows in sorted(months.items())}
    meta["lines_total"] = len(store["lines"])
    save_json(lab / "lines_meta.json", meta)
    legacy = lab / "lines.json"
    if legacy.exists():
        legacy.unlink()


def collect(store: dict, fetcher, *, budget_seconds: float, mode: str) -> dict:
    t0 = time.monotonic()
    known = {row["line_id"] for row in store["lines"]}
    excluded = store.setdefault("excluded", {})
    coverage = {"kalshi": {}, "polymarket": {}}
    added = {"kalshi": 0, "polymarket": 0}
    pending = {"kalshi": 0, "polymarket": 0}
    not_final = {"kalshi": 0, "polymarket": 0}
    errors: list[str] = []
    transient: list[str] = []

    def exclude(venue: str, key: str, reason: str) -> None:
        bucket = excluded.setdefault(venue, {})
        bucket[key] = reason[:200]

    try:
        k_events = kalshi_markets(fetcher, known, coverage["kalshi"])
    except LineError as exc:
        k_events, errors = [], errors + [f"kalshi listing: {exc}"]
    try:
        p_markets = poly_markets(fetcher, known, coverage["polymarket"])
    except LineError as exc:
        p_markets, errors = [], errors + [f"polymarket listing: {exc}"]

    # Interleave venues so a time-bounded run still grows both datasets.
    k_queue = [(cutoff, rows) for cutoff, rows in k_events if rows[0]["event_ticker"] not in excluded.get("kalshi", {})]
    p_queue = [m for m in p_markets if str(m["id"]) not in excluded.get("polymarket", {})]
    k_queue.reverse()  # newest first
    p_queue.reverse()
    i = j = 0
    while i < len(k_queue) or j < len(p_queue):
        if time.monotonic() - t0 > budget_seconds:
            break
        if i < len(k_queue):
            cutoff, rows = k_queue[i]
            i += 1
            try:
                store["lines"].append(build_kalshi_line(rows, fetcher, cutoff))
                added["kalshi"] += 1
            except NotYetFinal:
                not_final["kalshi"] += 1
            except FetchError as exc:
                transient.append(f"kalshi {rows[0]['event_ticker']}: {exc}")
            except LineError as exc:
                exclude("kalshi", rows[0]["event_ticker"], str(exc))
        if j < len(p_queue):
            m = p_queue[j]
            j += 1
            try:
                store["lines"].append(build_poly_line(m, fetcher))
                added["polymarket"] += 1
            except NotYetFinal:
                not_final["polymarket"] += 1
            except FetchError as exc:
                transient.append(f"polymarket {m['id']}: {exc}")
            except LineError as exc:
                exclude("polymarket", str(m["id"]), str(exc))
    pending["kalshi"], pending["polymarket"] = len(k_queue) - i, len(p_queue) - j
    store["lines"].sort(key=lambda r: (r["cutoff_utc"], r["line_id"]))
    stamp = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    for venue in ("kalshi", "polymarket"):
        rows = [r for r in store["lines"] if r["venue"] == venue]
        coverage[venue].update({
            "lines_stored": len(rows),
            "added_this_run": added[venue],
            "pending_after_run": pending[venue],
            "excluded_total": len(excluded.get(venue, {})),
            "not_yet_final_this_run": not_final[venue],
            "oldest_cutoff_utc": rows[0]["cutoff_utc"] if rows else None,
            "newest_cutoff_utc": rows[-1]["cutoff_utc"] if rows else None,
            "complete": pending[venue] == 0 and not coverage[venue].get("truncated") and not errors,
        })
    if transient:
        errors.append(f"{len(transient)} transient fetch failures (retried next run); first: {transient[0][:200]}")
    store.update({"last_run_utc": stamp, "mode": mode, "coverage": coverage, "errors": errors,
                  "requests_this_run": fetcher.calls})
    return store


# --------------------------------------------------------------------------- audit

def audit(store: dict, fetcher, sample: int, seed: str) -> dict:
    """Re-derive a random sample of stored checkpoint quotes from the venue and compare exactly."""
    rng = random.Random(seed)
    usable = [r for r in store["lines"] if r["price_urls"] and "no_prestart_quotes" not in r["flags"]]
    picks = rng.sample(usable, min(sample, len(usable)))
    results = []
    for row in picks:
        status, detail = "match", ""
        try:
            cutoff = int(parse_iso(row["cutoff_utc"]).timestamp())
            for side, url in enumerate(row["price_urls"]):
                payload = fetcher.get(url) or {}
                if row["venue"] == "kalshi":
                    fresh = kalshi_checkpoint(payload.get("candlesticks") or [], cutoff)
                else:
                    hist = payload.get("history") or []
                    fresh = {label: poly_point(hist, cutoff - back) for label, back in CHECKPOINTS}
                for label, _ in CHECKPOINTS:
                    if fresh[label] != row["quotes"][label][side]:
                        status = "MISMATCH"
                        detail += f"{label}[{side}] stored={row['quotes'][label][side]} fresh={fresh[label]}; "
        except LineError as exc:
            status, detail = "error", str(exc)
        results.append({"line_id": row["line_id"], "status": status, "detail": detail[:500],
                        "urls": row["price_urls"]})
    return {
        "schema_version": 1,
        "audited_utc": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "sample_size": len(results),
        "matches": sum(r["status"] == "match" for r in results),
        "mismatches": sum(r["status"] == "MISMATCH" for r in results),
        "errors": sum(r["status"] == "error" for r in results),
        "method": ("Random sample of stored lines; each stored price URL is re-requested from the venue and the "
                   "checkpoint quotes are re-derived with the same code. Any difference is a MISMATCH."),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", action="store_true", help="offline replay of recorded responses (writes to --lab-dir)")
    ap.add_argument("--lab-dir", type=Path, default=LAB, help="directory holding lines/ shards and lines_meta.json")
    ap.add_argument("--budget-minutes", type=float, default=45.0)
    ap.add_argument("--audit", type=int, default=0, help="re-fetch N random stored lines and compare exactly")
    ap.add_argument("--audit-seed", default=None)
    args = ap.parse_args(argv)
    fetcher = FixtureFetcher() if args.fixtures else Fetcher()
    if args.audit:
        store = load_store(args.lab_dir)
        seed = args.audit_seed or now_utc().strftime("%Y%m%d%H")
        report = audit(store, fetcher, args.audit, seed)
        save_json(args.lab_dir / "audit.json", report)
        print(f"Audit: {report['matches']}/{report['sample_size']} exact matches, "
              f"{report['mismatches']} mismatches, {report['errors']} errors")
        return 1 if report["mismatches"] else 0
    store = empty_store() if args.fixtures else load_store(args.lab_dir)
    store = collect(store, fetcher, budget_seconds=args.budget_minutes * 60,
                    mode="offline-fixture" if args.fixtures else "live")
    save_store(store, args.lab_dir)
    cov = store["coverage"]
    print(json.dumps({v: {k: cov[v].get(k) for k in ("lines_stored", "added_this_run", "pending_after_run",
                                                     "excluded_total", "complete")} for v in ("kalshi", "polymarket")}))
    if store.get("errors"):
        print("SOURCE ERRORS: " + "; ".join(store["errors"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
