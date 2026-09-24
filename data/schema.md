# Data schema — THUNDERPICKCOMP (v1)

All data files are JSON (UTF-8). They are the single source of truth rendered by
the static site (`assets/app.js`). Every factual record must carry provenance so a
reviewer can re-check it without trusting this repository.

## Common provenance block

Every record that states a real-world fact includes:

| Field | Required | Meaning |
| --- | --- | --- |
| `sources` | yes (fact records) | Non-empty list of `{label, url, accessed_utc, type}` |
| `accessed_utc` / `verified_utc` | yes | ISO-8601 UTC timestamp of retrieval / verification |
| `type` | yes (per source) | `primary` (organizer/team/player/Valve/market operator), `official-data` (HLTV/Liquipedia event pages, exchange APIs), `secondary` (reputable press) |

`type` values:

- `primary` — the organizer, a team/player official channel, Valve, or the market
  operator itself (e.g. Thunderpick press releases, Valve VRS repo).
- `official-data` — structured event/market records (HLTV event/match pages,
  Liquipedia tournament pages, Kalshi/Polymarket public APIs).
- `secondary` — reputable editorial reporting (used only with attribution and only
  where primary confirmation is unavailable).

## Status values

`verified` — checked against the cited source itself (not a snippet/rumor).
`flagged` — verified but with a caveat in `flags` (conflict, naming variance,
volatile value). Still citable; caveat must be shown.
`unverified` — collected but not yet checked; must never be presented as fact.
`stale` — previously verified but past its `valid_until_utc` (if set).

Missing data is `null` / `"unknown"` — never guessed.

## Files

- `master_list.json` — every verified claim. Fields: `id` (ML-###), `category`,
  `claim`, `detail`, `sources[]`, `verified_utc`, `status`, `flags[]`, `notes`.
- `teams.json` — the 8 finalists. Fields: `id`, `name`, `route`,
  `vrs_rank_2026_09_16` (+source), `hltv_rank_observed` (+`hltv_rank_observed_utc`),
  `roster[{handle, nation}]`, `coach{handle, nation}`, `sources[]`, `flags[]`.
  Real names only where verified against a fetched source.
- `matches.json` — matches/standings records. `status`: `scheduled` | `final` |
  `tbd`. Finals matches stay `tbd` until the group draw + results are published.
- `market_sources.json` — free public price sources. Each has `access` (how to
  query without payment/auth), `coverage`, `last_checked_utc`, `status`.
  No price is stored without `ticker`/`market_id`, `price`, `observed_utc`, source.
- `strategies.json` — SIMULATED competition users. `username`, `strategy`,
  `rules` (deterministic, human-readable), `bankroll_start`, `status`.
- `ledger.json` — SIMULATED bet/trade ledger. Empty until real, verified market
  prices exist. Entry fields: `entry_id`, `username`, `match_id`, `market`,
  `selection`, `decimal_odds`, `stake`, `placed_utc`, `price_source{...}`,
  `settlement{rule, result, settled_utc, result_source}`, `payout`, `profit`.

## Money math (ledger)

- `payout = stake * decimal_odds` on win, `0` on loss, `stake` on void.
- `profit = payout - stake`.
- Leaderboard: `pnl = Σ profit`, `roi = pnl / Σ stake`, `bankroll = start + pnl`.
- `scripts/validate.py` recomputes all of this and fails on mismatch.

## Staleness

- Live ranks/odds are volatile: any rank/price older than 7 days is shown with a
  "may be stale" badge; older than 30 days is `stale`.
- Tournament facts are re-checked on every data update; `verified_utc` moves only
  when a human/agent actually re-opens the source.
