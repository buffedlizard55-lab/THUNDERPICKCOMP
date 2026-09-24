# Evidence and money schema — THUNDERPICKCOMP (v2)

Read [README.md](../README.md) first. The site is static HTML/JS over the JSON files
in `data/`. **A source URL and observation time are receipts, not a guarantee that
reopening the URL will reproduce a historical live order book.** Collection is
forward-only; missing information is unknown rather than guessed.

## Stable sourced facts

- `master_list.json` — `ML-###`, category, one checkable claim, detail,
  `sources[{label,url,accessed_utc,type}]`, `verified_utc`, status, flags, notes.
- `teams.json` — eight Sep 24 event-lineup *snapshots* with players, coach,
  dated organizer VRS reveal rank, dated HLTV observed rank and direct sources.
  It is not a continuously verified live roster or a reserve-player register.
- `matches.json` — sourced tournament state, including `TWC26-FINALS-CHAMPION`
  (an **outright reference, not a fixture**), the TBD group draw and final
  qualifier placements. Match fixtures require two real teams, time and source.
- `roster_changes.json` — only team-announced moves individually verified from
  their primary posts: `RC-###`, team, player, kind, fact, impact, posted UTC,
  checked UTC, sources and `master_list` reference. This is not a complete history.
- `market_sources.json` — access paths and coverage caveats, not a price feed.

`type`: `primary` (organizer/team/player/Valve/market operator), `official-data`
(structured independent event or market records such as HLTV/Liquipedia),
`secondary` (editorial press, attributed). `verified` means checked at the
recorded UTC time, not guaranteed true forever. `flagged` requires explanatory
flags; `stale` and `unverified` must not be promoted to current fact.

## Forward observation journal — `observations.json`

`schema_version=1`, `mode` = `offline-replay` (dated research snapshot, **not** a
live poll) or `live` (scheduled/CLI polling), `last_attempt_utc` (run start),
`last_completed_utc` (run finish); individual receipt timestamps are taken
**after** each HTTP response, not forged from the run start, and:

- `checks[]` — one per source, with exact queried URL, checked UTC, status
  (`ok`, `partial`, `error`), query **scope**, number scanned and detail. An
  empty result means *nothing found in those checks*, never no market anywhere.
- `vrs_history[]` — one snapshot for each new Valve Global VRS file. Each
  finalist has exact dated Valve rank, points and ranked roster; source URL and
  observation UTC are retained. **Ranked roster != event starting five.**
- `roster_signals[]` — append-only differences between *two Valve snapshots*,
  never described as a confirmed transfer or effective date. URLs of both
  original files retained. Team announcements remain a separate data type.
- `fixtures[]` — conservative Liquipedia wikitext parser signals requiring two
  known finalists, an explicit UTC date and an HLTV match ID. Status remains
  `scheduled-unconfirmed` until HLTV page content is independently checked;
  no simulation uses these signals. Unrecognized templates are skipped/flagged.
- `events[]` — events explicitly naming TWC 2026, primary-API URL, human review
  URL, capture UTC, venue, stage and open/closed status. A closed qualifier
  market is evidence of market coverage, **not** a pre-event price.
- `quotes[]` — append-only first-party best-ask observations of *open*
  tournament markets, one per outcome. `quote_id`, `event_key`, `market_id`,
  `market_title`, `selection`, `raw_price` (exact decimal string, 0<p<1),
  `ask_size` (top-of-book shares/contracts), `source_updated_utc` (exchange
  timestamp), `observed_utc` (retrieval timestamp), `source_url` (exact API
  query), `event_url`, `resolution_rule` (original market text), freshness and
  venue. `indicative-only` quotes cannot create decisions. **Gamma
  `outcomePrices`, Kalshi `last_price` and post-settlement 0/1 values are never
  used as executable asks.** A best ask is still not a real fill or fair odds.
- `alerts[]` — query failures, pagination caps, unexpected fixture changes.
  Per-source failures do not erase old quotes or masquerade as zero hits.

Two series (`KXCS2GAME` game winner and `KXCS2` outright), first 3 × 200 open
events per series and finalist-pair candidates are currently monitored for
Kalshi. Polymarket search looks at first 25 Thunderpick active results and
first 60 open counter-strike-tagged events; historical search looks at first 20.
These limits are deliberate for free API/terms/rate safety; absence beyond them
is *unknown*. No scraped sportsbook is used.

## Paper decision journal — `ledger.json`

Eight entries in `strategies.json` are *simulated users/published policies* with
1,000 starting units each. Only `sim_champ_correlation` (atomic pair of 50 units
on FURIA and Falcons outright) and `sim_flat_observer` (no bets) are active.
Six match policies are `paused`, not secretly running.

A paper entry includes `entry_id`, `username`, `match_id` (the explicit outright
reference, not a fixture), `event_key`, market/outcome, `stake`, `decimal_odds`,
`placed_utc` (paper decision UTC), `simulated=true`, explicit `fill_policy`,
`price_source{venue,market_id,url,event_url,raw_price,ask_size,quote_id,
observed_utc,source_updated_utc}`, `settlement{rule,result,settled_utc,
result_source}`, payout and profit. The referenced `quote_id` must exactly
match a first-party snapshot. Current `result` is `pending` with **null**
payout/profit. The decision is simulated; no exchange order was placed.

A decision requires both eligible tournament-winner Yes asks in the *same live
collection run*, from an open Finals event before Oct 14 UTC, market book time
within 10 minutes, and top-of-book size at least `50 / ask` contracts/shares.
At decision time (collection finish), each receipt must be no older than 2
minutes and the two receipt times at most 60 seconds apart. We choose the
lowest eligible best ask per outcome (market ID breaks ties), place both
positions or neither, and never backdate or change a decision.

## Gross accounting and settlements

For first-party raw ask `p`, gross decimal factor = `1/p`. Only once
**independently verified**: win gross payout = `round_half_up(stake/p, 2)`,
loss = 0, verified void = stake, partial payout =
`round_half_up(stake × venue_payout_fraction / p, 2)`. Profit = payout − stake.
Real venue fees, spreads beyond the top ask, slippage, taxes and execution risk
are **not** modeled. Never assume canceled/forfeit = void: Kalshi/Polymarket
rules may settle at fair-market-price or 50/50. Settlement automation and its
append-only correction journal do **not** yet exist; positions stay pending.

Leaderboard rank = starting units + **settled** profit. Pending stakes reduce
*available* units but do not change realized profit. ROI = settled P/L divided
by settled stake, shown as `—` until a settlement exists. `scripts/validate.py`
uses `Decimal` and rejects NaN/Infinity, duplicate IDs, wrong source refs,
undersized asks and incorrect payout/profit.

## Persistence, tests and staleness

Pages is deployed by GitHub Actions on pushes to `main` and hourly best-effort
cron. Every deploy retrieves the prior published `observations.json` and
`ledger.json` over HTTPS, checks immutable history, appends new observations,
runs validation/tests, and deploys only on success. A missing/corrupted prior
publication blocks all later deploys, except the **one-time bootstrap from the
known initial main commit**. An Actions artifact is a short-lived recovery
copy. This rolling Pages journal is **not yet permanent archival storage**.

Published `mode=offline-replay` records are PARTIAL, documented in
`tests/fixtures/manifest.json`, and cannot cause a simulated position. Offline
unit tests use synthetic future quotes only in test memory, never in data/.

A UI timestamp is the last *attempt*, not necessarily a successful price query.
Client code flags the feed as stale after 2 hours (hourly job may be delayed)
and marks quote observations as historical after 30 minutes. Old Valve snapshots
stay labelled with their own publication date. Historic organizer and HLTV
ranks are never silently updated or labeled as live.
