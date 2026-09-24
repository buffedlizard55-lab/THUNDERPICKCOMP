# THUNDERPICKCOMP

> **⚡ Every-Session Starting Point — read this before any research, proposal, or edit**
> 1. Read this README end-to-end and `AGENTS.md`. This is the canonical mission, core values, and verification charter.
> 2. **Solve the manual-checking problem:** the product must become a *useful daily current feed* — timely, traceable, and honest about unknowns — so users don't have to manually check many sites themselves. If a change doesn't make the feed more reliable or more useful day-to-day, don't do it.
> 3. Apply **Core Values as the decision filter** on every tradeoff: **Maximize P(Win)** and **Own the Outcome** (see below). Prefer the path that maximizes the project's chance of becoming a genuinely useful, trustworthy hub; own results end-to-end and fix what can be fixed.
> 4. No hallucinations, verify claim-by-claim with source links, keep an audit trail, use only free public sources, and fail visibly. See "Non-negotiable information standards" below.
> 5. Run the three-pass method (implement → bug/edge-case review → charter re-check) and report verified work, uncertainty, and next steps.

## Mission

Build a clear, dependable, publicly sourced expert hub and forward-looking prediction/leaderboard competition for the **Thunderpick World Championship 2026** and Counter-Strike 2 (CS2). Help people understand the event and follow relevant changes without having to manually check many sites themselves. A useful current feed must be timely, traceable, and honest about what is not known.

The product should bring together verified tournament information, teams and player/roster updates, match results, relevant public betting and prediction-market prices, and transparent simulated-user strategies and performance. It should be simple to navigate and easy to use every day. **Correctness and auditability take priority over appearing comprehensive.** If a claim or price cannot be independently verified, do not present it as fact or silently fill in a gap.

## Core values — focal point for every decision

> Keep these as the focal point when building, developing, researching, suggesting upgrades, and implementing the work.

### Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

### Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Apply these values to research, product decisions, implementation, testing, and maintenance. Be candid about limitations; fix issues that can be fixed; and make tradeoffs in favor of a trustworthy, useful product rather than unsupported breadth. Setting aside emotion and putting Arena first is how we maximize P(Win).

## Non-negotiable information standards

- **No hallucinations.** Never invent teams, rosters, matchups, odds, market prices, transactions, results, statistics, dates, or quotes. Missing data is `unknown`/`unavailable`, not an invitation to guess.
- **Verify claim by claim.** Break material statements into checkable claims. Link each claim or record to the source that supports it. Prefer primary sources (tournament/organizer, teams and players, Valve, official market/exchange records); use reputable secondary reporting only where primary confirmation is unavailable, and label it accordingly.
- **Keep an audit trail.** Record the source URL, the time retrieved (UTC), the event/market and selection identifiers where available, relevant timestamp or publication date, and the exact source value. Preserve historical prices rather than replacing them with a current value. Show when data was last refreshed and flag stale, conflicting, missing, or suspicious records for review.
- **Separate fact from analysis.** Clearly label official facts, reported information, calculations, model estimates, and simulated strategy outputs. Explain assumptions and calculations so results can be reproduced. A forecast is not a verified fact.
- **Make simulated activity unmistakable.** Leaderboard usernames, bets/trades, balances, and results are simulated. Never imply a simulated position was executed on a real sportsbook or exchange. Do not recommend a real wager as guaranteed or risk-free.
- **Use free, public sources only.** Do not add a paid API, subscription, or paywalled data dependency. Respect source terms, robots policies, rate limits, attribution requirements, and personal privacy. “Free to access” does not automatically mean unrestricted to scrape or republish.
- **Fail visibly and safely.** Do not silently treat a missing feed, changed page, parsing error, or stale price as a valid update. Surface the issue and retain enough provenance to diagnose it.

## What success looks like

1. A clean, responsive, accessible website with an easy-to-understand current event overview and navigation.
2. A trustworthy feed for matches, teams, players, roster changes, and other material tournament developments, with source links and freshness indicators.
3. A verified match/market record and replayable simulated bet/trade ledger: selection, odds/price, amount, source, timestamp, settlement rule, outcome, and calculation are all inspectable.
4. Transparent strategy and leaderboard comparisons using consistent rules, with no hidden manual edits or untraceable performance changes.
5. Clear tournament/CS2 explainers and betting-market context written for readers familiar with prediction markets, while distinguishing facts from analysis.
6. Automated checks and tests that catch stale data, malformed records, duplicate entries, invalid settlements, broken sources, and calculation errors before publication.

## Working method for every task

1. Read this README and `AGENTS.md` first. Inspect the current repository and its status before changing anything.
2. State the user problem the change addresses and how it supports the mission and core values.
3. Research from freely accessible sources; verify each factual claim against the source itself. Link sources for manual review. Do not count an entry as “new” until it is checked against the existing master list for duplication and verified line by line.
4. Implement the smallest reliable, maintainable change. Prefer automation with observable failure modes over manual data entry or brittle assumptions.
5. Run relevant tests/checks and inspect the final diff. Do at least three passes: (1) implement and verify, (2) review for bugs, missing requirements, assumptions, and edge cases and fix them, (3) re-check against this charter and improve remaining accuracy, reliability, completeness, and code quality.
6. Report what changed, what was verified, what remains uncertain or blocked, and the next highest-value work. Never claim work or verification that did not happen.

## Repository review (starting baseline)

At the time this charter was added, the repository contained only this README and the initial Git commit; it had no application, data files, tests, automation, or GitHub Pages configuration. Therefore no verified dataset or working live feed existed in the repository to extend. The linked site below is a **design/content reference only**; its claims are not automatically validated by being present there. Verify facts independently before importing them.

## Design reference

The project owner supplied [Thunderpick World Championship 2026 — Expert Hub](https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/) as a starting point for the site’s organization and visual design. It can inform the product, but is not by itself an authoritative source for tournament, roster, pricing, or results data.

## Original project brief — preserved verbatim (starting point)

The following preserves the **full project prompt** supplied by the owner. This is the brief to re-read every session alongside the mission and core values above. Factual content still has to meet the verification standards; the prompt itself is not a source of facts.

> Review the repo.
>
> Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use. It should solve the problem of having to manually check everything ourselves and having an up to date current feed.
>
> Review the repo.
>
> The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.
>
> Our Core Values
>
> Maximize P(Win)
>
> "Maximize the Probability of Winning": our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). "Maximize P(Win)" frees us from constraints and clarifies that we must put Arena first.
>
> Own the Outcome
>
> We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.
>
> I want to create a website that is an expert in the THUNDERPICK WORLD CHAMPIONSHIP 2026.
>
> let's use this site as a starting point, we can even copy lots of it since it is designed very well.
>
> [https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/](https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/)
>
> I want to focus on creating a forward collecting leaderboard competition using simulated usernames and strategies.
>
> We should track all matches using established e sports betting lines, kalshi markets, prediction markets, anywhere we can find reliable public information for free, no paid api, no paid api subscription, must be free and we can gather, organize and analyze. We should be able to track every users exact bets or trades so that we can verify everything is working correctly using verified official pricing with lines, amounts, dates, outcome. verify no hallucinations.
>
> I want to know the teams and i want to know the players, i want to know all the roster changes, stats, main rosters, reserve players, drama. Become an expert in the counterstrike 2. Research strategies, betting strategies, and any other info to understand the universe of counter strike 2. We should understand the tournament format, who are the favorites, dark horses, and we should be able to generate easy to read information for an someone who has experience in betting markets. We should also have a section or subpage that lists any changes to teams, players, rosters, or things that can affect the tournament outcome.
>
> Work line by line verifying from official verified trusted sources, provide links for manual review. There should be no manual input, work on your own to complete tasks. Flag any irregularities for review. No hallucinations.
>
> Search for 20 new entries. Before adding to master list, Verify no hallucinations.
>
> The goal of this project is to get a full list that follow our requirements. No hallucinations. Verify line by line.
>
> Site creation
>
> Create a github page for this repo that has clean ui, user friendly, simple and easy to use.
>
> It should be organized and clean. It should include all relevant information in an easy to read format with official verified links as sources for review. Work line by line verify everything no hallucinations.
>
> Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project. It should be worked on in this next session or the next session. Work line by line verify everything no hallucinations.
>
> Run this task through multiple passes.
>
> Pass 1: Implement the task completely and verify the result.
>
> Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.
>
> Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.
>
> Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request. Work line by line verify everything no hallucinations.

## Repository map (as of 2026-09-24 — backtesting session)

The repository now contains a static, responsive, **ten-page** Pages site (added `backtest.html`), a
56-entry sourced master list, eight simulated policy definitions, an empty forward ledger,
and a new historical backtesting pipeline with 22 verified matches and 69 simulated bets.

- `index.html`, `teams.html`, `guide.html`, `markets.html`, `leaderboard.html`, `backtest.html`,
  `ledger.html`, `changes.html`, `master-list.html`, `methodology.html` — **ten-page**
  public hub (copied/adapted from [THUNDERPICK-WC-2026](https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/) design — navy/gold hero, better tables/cards — with source-verified content). New: `backtest.html` shows 22 verified historical matches, modeled odds audit trail, and 69-bet leaderboard for strategy research.
- `assets/app.js`, `assets/style.css` — accessible static UI over JSON, including
  actual UTC freshness/source-error status and links for manual review. Style mirrors reference site's polished system while preserving audit-feed readability. New renderers: `backtest-leaderboard`, `backtest-analytics`, `backtest-ledger`, `historical-matches`.
- `data/master_list.json` — **56 dated sourced claims (ML-001–ML-056)** covering roll of honour, regional winners, rename, HLTV Top-20 pedigree, player milestones, karrigan move, Cologne Major records, roster rebuilds, map-pool Cache history, core-roster rule, veto/OT, EPL S24, StarSeries Fall, FURIA calling change, org closures — each with source links for manual review, verified line by line, no hallucinations.
- `data/teams.json`, `data/matches.json`, `data/roster_changes.json` — dated team/event snapshot, outright reference + draw status and primary-verified moves. Historical moves are secondary-sourced in ML-043–ML-049 and surfaced on `changes.html` + `teams.html`.
- `data/observations.json` — forward, append-only quote/VRS/signal journal with exact query scopes, timestamps, alerts and source links. Initially offline partial replay; live mode verified after PR #6 (mode=live, 9 checks, 0 quotes — honest about TBD draw).
- `data/ledger.json`, `data/strategies.json` — 8 simulated accounts: one active conditional outright policy (50u FURIA+Falcons), one no-bet control, six match policies active with gates (double-sourced fixture + strictly pre-start fresh first-party ask + top-of-book depth + unambiguous association + pending budget; TBD draw means nothing can be papered yet). Ledger intentionally empty until forward, first-party eligible quotes.
- `data/settlements.json` — append-only SHA-256-chained settlement journal (venue-resolution + independent confirmation + decisions + holds). Void never assumed; 50/50 = partial.
- `data/historical_matches.json` — **22 verified historical matches** (HIST-001–HIST-022) from Jun–Sep 2026: FISSURE Playground 3 (Legacy 3-0 G2, Legacy 2-0 FURIA, G2 2-0 FURIA, G2 2-1 BetBoom, etc.), StarSeries Fall (Vitality 3-1 Aurora, Aurora 2-1 Vitality, FURIA 2-1 MIBR, Vitality 2-0 FURIA), IEM Cologne Major (FURIA 2-0 BetBoom, 9z 2-1 PARIVISION, Legacy 2-0 PARIVISION, Falcons 3-0 FURIA Major final), TWC Closed Qualifier (VP 3-0 HOTU, VP 2-1 HEROIC/FOKUS, VP 2-0 K27/BESTIA, K27 2-1 VP opener), XSE Pro League (9z 3-0 PARIVISION). Each with date, winner, score, map_scores, and HLTV/Liquipedia source URLs for manual review.
- `data/historical_odds.json` — real market receipts where free: Polymarket Gamma closed event 1000135 (3DMAX vs 100 Thieves qualifier) with 0/1 settlement note (NOT pre-match odds). Documents limitation: no free sportsbook historical odds API verified; Kalshi open discovery found 0 Finals markets as of Sep 24. Includes modeled_policy: fair_fav = min(85%, 50%+2.5%*gap), deterministic SHA256-based noise [-0.08,+0.08], 4% overround → decimal odds. Labeled MODELED.
- `data/backtest_results.json` — backtest summary: meta (generated_utc, 22 matches, 69 bets), analytics (total, inter-finalist 9, date_range Jun 21–Sep 20, VRS ranks ML-008, odds policy), strategies[] sorted by bankroll: favorite_backer 22 bets 19W-3L +126.1 profit +22.93% ROI bankroll 1126.1; underdog_hunter 22 bets 3W-19L -156.18 ROI -47.33%; etc. Control flat_observer stays 1000.00.
- `data/backtest_ledger.json` — **69 detailed simulated bets**: entry_id BT-{HIST}-{username}, username, match_id, event, date, teams, winner, pick, decimal_odds, stake, profit, result win/loss, odds_type MODELED, odds_detail, fair_probs, market_implied, reason, sources[] — stored for future analysis and strategy building.
- `data/player_stats.json` — dated player-stat window policy (HLTV Rating 3.0, trailing 90 days, ≥40 maps). Ships empty.
- `data/schema.md` — v3, now includes backtesting provenance, modeled odds labeling, and money math for both forward and historical ledgers.
- `scripts/collect.py` — bounded read-only collection from Valve GitHub API, Liquipedia wiki API, Kalshi (KXCS2GAME/KXCS2, 200 limit, 3 pages), Polymarket Gamma/CLOB (Thunderpick active 25, CS tag 60, history 20, per-finalist 10 each when no open TWC event). No paid API, no sportsbook scraper.
- `scripts/competition.py` — forward-only outright + six match strategies with gates (double-sourced fixture + pre-start + depth + unambiguous association + budget).
- `scripts/backtest.py` — **NEW**: historical backtesting engine — loads historical_matches, VRS ranks (ML-008), strategies; computes modeled odds (VRS-gap + deterministic noise + 4% overround) where no real free line; simulates each strategy's decisions in chronological order; generates backtest_results.json + backtest_ledger.json with full audit trail. No real lines invented as facts.
- `scripts/restore.py` — refuses to reset published journal; compares Pages + last successful Actions artifact; requires covering live history.
- `scripts/settle.py`, `scripts/archive.py`, `scripts/hltv.py` — settlement journal (SHA-256 chained, venue vs independent confirmation), versioned archive branch, HLTV parser.
- `scripts/validate.py`, `tests/` — extended validation for historical_matches (HIST-###, sources, winner must be team_a/b), historical_odds (real_markets + modeled_policy), backtest_results/ledger (profit math, odds_type MODELED/VERIFIED, match_id must exist in historical_matches). Suite now **57 Python tests** + UI smoke (10 pages, backtest renderers). All pass locally.
- `.github/workflows/ci.yml`, `.github/workflows/pages.yml`, `.github/workflows/watchdog.yml` — CI on PR; pages.yml now runs collect → competition → settle → **backtest** → validate → archive (live-mode guard) → deploy Pages hourly + on push; watchdog fails loudly when hourly stalls. Legacy branch publishing still enabled (admin must switch to GitHub Actions).

## Runbook

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
node --check assets/app.js && node tests/test_ui.cjs
python3 -m scripts.collect --fixtures --as-of 2026-09-24T17:10:00Z --output /tmp/observations-replay.json
python3 -m http.server 8000 --bind 0.0.0.0  # local preview (serve from repo root)
```

The **live** collector (`python3 -m scripts.collect`) accesses only free public
endpoints; the sandbox used for this work does not permit direct curl/urllib to
these hosts, so local live execution is not claimed. Verified first-party pages
and API results were inspected with the page-fetch tool during research. Offline
fixture replay must never create paper positions. When Pages deploy runs on an
internet-connected GitHub runner it reports each query's success or failure;
inspect `markets.html#source-checks` and the Actions run before relying on the
feed. If all sources fail, the site must show errors/staleness, not a false 0.

Published site: [buffedlizard55-lab.github.io/THUNDERPICKCOMP/](https://buffedlizard55-lab.github.io/THUNDERPICKCOMP/).
The first [live Actions deployment](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36038171748) after [PR #3](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/pull/3) merged succeeded on Sep 24 at 18:00 UTC; the published journal showed `mode=live`, two visible source errors, no quotes and no paper positions (both source errors were repaired and verified live in the 18:49 UTC run after [PR #6](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/pull/6) — see the session log). A successful deployment after **each** future merge is required before calling its changes published. No feature here is a real wager or investment advice.

### Durability and the "no manual checking" goal

Pages alone is static. The workflow restores the public JSON history from the
same HTTPS site before each scheduled run **and compares it with the last
successful Actions journal artifact**. It uses the newest compatible history
that covers older immutable receipts/decisions (observations, ledger **and**
the chained settlement journal), then republishes. If neither has a covering
live journal or they conflict, it must **stop** rather than discard historical
prices/bets. The one-time bootstrap was tied to the prior `main` commit, not a
standing permission to reset data. Since this session, every successful run
also commits the full journal + SHA-256 manifest to the **`journal-archive`**
git branch (versioned, tamper-evident, outlives 30-day artifacts), and a
**watchdog workflow** fails loudly when the hourly job stalls (>100 min since
last success or >130 min since the published `last_attempt_utc`). This is a
scoped step against manual checking, not full match/odds/roster coverage.

**Repository admin action (still outstanding):** Pages is still set to legacy
`main` branch publishing. The Actions deployment succeeded anyway, but each
push also starts a legacy build that can temporarily replace live data with
the tracked offline seed. The GitHub App token cannot change this setting
(Pages API HTTP 403 on writes). An admin should open
[Settings → Pages](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/settings/pages)
and set **Build and deployment → Source: GitHub Actions**. The artifact
comparison prevents silent receipt loss if a branch build wins the race, but
does not prevent a transient stale public page. Recheck after the next push.

## Session log

### 2026-09-24 — Initial build (existing baseline)

- Prior session wrote this charter and repository instructions, researched
  ML-001–ML-032, built the eight-page static site and baseline JSON, configured
  GitHub Pages, and recorded no prices/positions. Read the dated records for
  evidence; this log is not independent verification of every earlier claim.

### 2026-09-24 — Forward collection and correctness review

- Read README and AGENTS.md; reviewed the full tree, CI, UI, data and validator.
  Primary sources re-opened: Thunderpick team release, HLTV event page,
  Liquipedia event/wiki API, Valve's Sep 7 Global VRS, Polymarket Gamma API,
  Kalshi public API, and two Sep 17 team-issued PARIVISION posts.
- Important correction: Polymarket Gamma event `1000135` is a real, now-closed
  TWC 2026 **Closed Qualifier** market. No historical pre-match quote was
  captured here, so its 0/1 resolution prices cannot backfill a paper bet.
  `ML-030` no longer implies no market was ever available.
- Primary team announcements individually confirm slaxejezzz's bench (he
  remains with PARIVISION and is available for loan) and HObbit's permanent
  main-roster addition on Sep 17. Their evidence is in `roster_changes.json`
  and ML-033/034. Valve Sep 7 ranks (ML-035) are a *different date* from the
  organizer's Sep 16 reveal, not an error to flatten or an active-lineup claim.
- Built a bounded free-source collector, conservative fixture signals,
  immutable price receipts, a conditional forward-only paper outright engine,
  scoped check/error UI, unit tests, strengthened Decimal validator and
  scheduled Pages build with guarded history restoration. **Initial seeded
  observations are an offline, partial research replay.** Real future market
  prices and simulated trades remain zero until independently captured.
- Three required passes: **(1)** implement the nine-page hub, source collector,
  dated receipts and conditional outright paper rule, then run offline source
  replay; **(2)** catch and fix stale hard-coded labels, an incorrect market-
  absence claim, quote receipt-time drift, history reset risk, pending-position
  math, and a dangerous match-winner-versus-champion classification edge case;
  **(3)** recheck primary links, prevent resolved-market backfilling, smoke-test
  all pages including failed-feed/XSS states, and run full validation/14
  Python cases/Node renderer checks/diff checks. See PR/checks for actual
  CI results; local fixture tests do **not** prove the remote hourly run worked.

### 2026-09-24 — PR #3 merged, first live deployment and source repair

- [PR #3](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/pull/3) merged to `main` as `4b8e7d9`; its CI and the first [collection/Pages run](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36038171748) passed. The published JSON at 18:00 UTC was genuinely `live`, with seven scoped checks and zero pre-event quotes or paper entries. Two checks showed errors rather than falsely reporting no data: Valve VRS rejected an unrelated four-player/duplicate-name row, and Liquipedia returned HTTP 406 demanding gzip.
- Verified the full Sep 7 Valve file from Valve's [public GitHub API](https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/invitation/2026/standings_global_2026_09_07.md): ranks 110 and 268 both use `Just Players` for distinct ranked rosters; rank 110 lists four names. The eight finalists' dated rows still parse. [Liquipedia's API terms](https://liquipedia.net/api-terms-of-use) explicitly require gzip support and a contactable custom user agent.
- Follow-up code scopes validation to finalists, requests/boundedly decodes Liquipedia gzip, tests source failures, and compares Pages with the last successful artifact so a legacy branch build cannot silently reset history. These fixes must pass PR CI and a **new** live collection before either source is called repaired in production.
- Three follow-up passes: (1) reproduce using the complete Valve snapshot and first published check errors; (2) add coverage for malformed finalists, corrupt/oversized gzip and legacy Pages journal rollback; (3) re-run validation/UI/tests and inspect the follow-up PR/next live publication. Keep future checks honest if either API remains unavailable.
- [PR #4](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/pull/4) merged as `e0e1898`, but its first [Actions run](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36039556479) stopped in validation **after** restoring from the prior successful checkpoint and collecting sources. Two new tests mistakenly read `data/observations.json` and `data/ledger.json` as if they were static seeds; the job intentionally rewrites these to live history before testing. An isolated replay of the prior tests against a synthetic restored live journal reproduced **two** errors (`published observations older than committed seed`); the updated suite passes that same scenario. The runner's log bundle was not retrievable from this sandbox, so a fresh Actions run must still confirm the root cause. The competing legacy Pages build republished the offline seed, so the public feed is not currently reliable until successful Actions deployment recovers it. The last successful Actions checkpoint remains available. The follow-up isolates test seeds from live data and adds a disposable synthetic-live CI replay; check public data before declaring recovery.

## Session log (continued)

### 2026-09-24 — Live-feed outage fix: validator/collector check-set drift (this session)

- **Found the feed down.** Since PR #7's merge every scheduled/hourly
  "Collect verified sources and deploy Pages" run failed: PR #7 added two
  collector checks (`hltv_crosscheck`, `polymarket_teams` — 9 total) but
  `validate.py` still hard-coded the old 7-source whitelist and demanded
  `len(checks) == 7` in live mode. Run [36048834856](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36048834856)
  (PR #8's merge) therefore died in "Validate data and regression tests before
  publishing", and no run of the new pipeline has ever succeeded — the
  `journal-archive` branch still does not exist and the published feed remained
  the transient legacy-seed copy. The PR suite could not catch it because the
  tracked seed is `mode=offline-replay`, where the live-only completeness rule
  never fires. Diagnosed from the Actions job step list + a local reproduction
  (sandbox log/artifact downloads are egress-blocked); reproduction showed the
  exact three errors the live 9-check document produces.
- **Fix:** `validate.py` now imports the collector's `SOURCE_IDS` as the single
  source of truth (`REQUIRED_SOURCES`) and requires a live journal to report
  exactly one check per collected source — no fewer (silently skipped sources
  would fake coverage), no more (unknown sources would bypass per-check rules).
  The per-check whitelist is derived from the same constant so collector and
  validator cannot drift again. `None`/missing `source` keys produce clean
  validation errors, not crashes.
- **Regression tests (5 new, suite 54):** a live 9-check document validates;
  a live document missing one check fails; an unknown extra check fails; the
  validator set equals the collector constant; the tracked 7-check offline seed
  still validates. One drafted test expectation was itself wrong (asserted
  alphabetical check order) and was corrected to order-independent comparison.
- **Also fixed:** stale "19 Python tests" count in the repository map (now 54).
- Passes: (1) reproduce → fix → targeted tests; (2) edge-case review (None
  source key crash fixed), full suite 54/54, validator, UI smoke, fixture
  replay, badge/count cross-check (index 56/3 = actual statuses; roster_changes
  9; live doc composition restore→collect→settle re-traced); (3) charter
  re-check against the original brief.
- **Live recovery VERIFIED (PR #9 merged 19:51Z, run [36050952696](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36050952696)
  succeeded end-to-end in 43s):** published `data/observations.json` is
  `mode=live` with `last_attempt_utc` **2026-09-24T19:51:34Z** and all **nine**
  checks — `valve_vrs` ok (8 finalist rows, Sep 7 snapshot),
  `liquipedia_fixtures` partial-by-scope (0 parseable; Finals draw still TBD —
  honest), `hltv_crosscheck` ok (0 fixtures yet to cross-check),
  `polymarket_search`/`polymarket_tag`/`polymarket_history`
  ok/partial/partial (0 open TWC 2026 events in scoped searches; 20 historical
  qualifier events), `polymarket_teams` partial (12 finalist-name searches, 88
  first-page records), `kalshi_game` ok (55 open events scanned, 0 TWC 2026),
  `kalshi_outright` ok (0). Zero eligible pre-event asks → **zero quotes and
  zero paper positions** — nothing was invented. Journal continuity held: the
  seed event's `first_seen_utc` (17:10Z) survived. The merge's legacy
  `pages-build-deployment` (19:51:21Z, seed) landed BEFORE the Actions deploy
  (~19:52:04Z, live), so live content is the recovered feed; `build_type` is
  still `legacy` (admin action outstanding). The CI smoke check initially
  failed on this PR for a second time: it built its synthetic live journal
  from the stale 7-check seed; fixed by replaying the real collector inside
  the disposable copy (suite unchanged at 54; the copy now also mirrors
  `.github/`).
- **Archive bug found by post-run inspection (fixed in PR #10):** the first
  `journal-archive` commit (8a401ed, run 36050952696) stored the **committed
  offline seed**, not the published live journal — the archive step ran in the
  deploy job, whose fresh checkout has `ROOT/data` = seed, so
  `scripts/archive.py` archived the wrong files; `commit_url` was also empty.
  Fix: archiving moved into the build job immediately after validation (where
  `data/` holds the exact journal being published), with a new
  `--expect-mode live` guard that refuses to archive anything else, a
  `--data-dir` option, `--commit-url`, and a fresh-manifest re-copy after the
  branch switch so the packaged site shows the real archive state. The deploy
  job is now deploy-only. Regression tests (3 new, suite 57): wrong mode
  refused, live journal archived from an explicit dir, and a workflow
  structure check that the archive step precedes artifact packaging inside the
  build job and no longer exists in the deploy job. Tracked
  `data/archive_manifest.json` updated to the real first archive commit. The
  next successful run must be checked for a `journal-archive` commit whose
  manifest reports `mode: live`. Watchdog's first-ever scheduled ticks also
  still need confirming (registered ~19:15Z).



### 2026-09-24 — Post-merge-6 live verification, match pipeline, settlement journal, durability, coverage (this session)

- **Verified the first live Pages run after merge #6** (PR #6 merged 18:48:51Z
  as `02ccaec7`): Actions run [36043851018](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36043851018)
  succeeded end-to-end (restore → collect → validate → deploy), published
  `data/observations.json` is `mode=live` with `last_attempt_utc`
  **2026-09-24T18:49:05Z** / `last_completed_utc` 18:49:08Z. All seven scoped
  checks of that run reported: `valve_vrs` **ok** (8 finalist rows, Sep 7
  snapshot — the PR-#3-era four-player-row error is repaired in production),
  `liquipedia_fixtures` **partial-by-scope** with `records_checked: 0` (correct:
  the Finals draw is TBD — no explicit UTC date/teams/HLTV id exists to parse),
  `polymarket_search`/`polymarket_tag`/`kalshi_game`/`kalshi_outright` **ok**
  (0 open TWC 2026 events found in their bounded scopes),
  `polymarket_history` **partial** (20 TWC-2026 closed qualifier events found;
  `truncated_search` alert raised honestly). Eligible quote scope produced
  **zero quotes and zero paper positions** — consistent with no open Finals
  market existing yet; the empty ledger stayed intact and journal continuity
  is proven by preserved `first_seen_utc` values (17:10Z seed events still
  present). Legacy branch publishing **did** transiently overwrite the live
  feed: the `pages-build-deployment` run for `02ccaec7` completed at 18:49:14Z
  publishing the offline seed, and the Actions deployment landed after it
  (environment deployments 18:49:05Z legacy vs 18:49:16Z Actions; live content
  is the Actions journal). No data was lost (artifact/coverage guard worked as
  designed), but the Pages API still reports `build_type: "legacy"` — the
  admin must switch Source to GitHub Actions (writes return HTTP 403 for the
  app token).
- **Match pipeline:** extended the Liquipedia parser to the real wikitext date
  format (month-name + whitelisted timezone abbreviations; ambiguous offsets
  like CST are skipped, never guessed; bare/naive dates remain ineligible),
  group/stage context, finished flags, decided map scores and a labeled
  Liquipedia-derived series result. Added `scripts/hltv.py` + a bounded
  HLTV match-page cross-check (max 8 fetches/run; robots-permitted
  `/matches/<id>` pages only): schedule needs same HLTV id + teams + UTC date
  (`scheduled-confirmed`); results need HLTV series score and Liquipedia map
  scores to agree (`result-confirmed`, labeled as score-derived); any
  disagreement → `conflict` + alert, permanently ineligible. Implemented the
  six match strategies in `scripts/competition.py` with pre-start depth checks
  (top-of-book ≥ stake/ask, strictly before `scheduled_utc`, fresh same-run
  receipts, unambiguous quote-to-fixture association, pending budget) and
  flipped them from `paused` to `active` with those gates published in
  `strategies.json`. The TBD draw means nothing can be papered yet; no
  opponent, result or price is invented anywhere.
- **Settlement journal:** new `data/settlements.json` + `scripts/settle.py` —
  append-only SHA-256-chained receipts (venue resolution verbatim; independent
  HLTV+Liquipedia confirmation for matches; Liquipedia infobox winner + a
  confirmed playoff result for the outright). Decisions apply only when venue
  and independent evidence agree; venue-vs-fixture disagreement, unresolved
  venues and unmapped payout shapes append holds and stay pending. 50/50
  settles as **partial** at the venue's fraction — never a refund; void is
  never assumed. Wired into restore (prefix/divergence protection), validation
  (chain re-verification), the workflow and the ledger UI.
- **Durability:** `scripts/archive.py` + a workflow step commit the full
  journal + SHA-256 MANIFEST to a `journal-archive` branch after every
  successful deploy (versioned by git history, outlives 30-day artifacts),
  and a new hourly `watchdog.yml` fails loudly when the last successful
  collection is >100 min old or the published `last_attempt_utc` is >130 min
  old. Archive manifest is published on-site and rendered on methodology.html.
- **Coverage:** promoted ML-043/045/046/048/049 with **primary sources fetched
  directly this session** (Falcons karrigan-welcome + roster statement, Legacy
  arT + try, Aurora Jimpphat/ash/kyxsan, PARIVISION FL1T + HObbit farewell,
  Virtus.pro academy promotions) and added primary-verified RC-003–RC-009;
  ML-047 (BetBoom) was searched and honestly stays secondary (no official post
  found). Broadened market discovery with bounded per-finalist Polymarket
  searches (`polymarket_teams`, runs only when keyed searches found no open
  TWC event). Defined the dated player-stat window policy (HLTV Rating 3.0,
  trailing 90 days, ≥40 maps, robots-compliant) in `data/player_stats.json`
  before any ratings exist. Expanded guide.html with a sourced-facts vs
  labeled-heuristics CS2 betting research table (MR12/veto, Cache pool
  newness, stand-in rules, EPL fatigue, cross-venue 50/50 settlement
  asymmetry) — heuristics are labeled as analysis, never facts.
- Three passes: (1) implemented and unit-tested everything offline (42
  tests); (2) fixed a same-pair association ambiguity refusal, an ISO-date
  regression that would have accepted naive UTC-less timestamps, a settlement
  logic bug where venue/fixture disagreement could have settled a loss, and
  several incorrect first-draft test expectations (documented above); (3)
  re-ran validation + full suites + UI smoke + fixture replay, and re-checked
  every claim in this log against the live run/artifact/API data. The new
  checks (`hltv_crosscheck`, `polymarket_teams`) and the settle/archive steps
  still require a successful post-merge Actions run before being called
  verified in production.
- **Post-merge incident (fixed in PR #8):** the first live run of the new
  pipeline (Actions run 36048173182) failed in the collect step —
  `collect_poly_teams` referenced an undefined `TEAM_NAMES` module constant,
  and the offline tests never execute that live-only branch, so it survived
  the whole suite. Fixed by deriving `TEAM_NAMES` from `data/teams.json`
  (display name + short form, ≤13 bounded searches) and adding two live-branch
  regression tests (suite 49). Until that fix deploys, the live site can
  transiently show the tracked offline seed (legacy Pages build won the race);
  the hourly run after the fix merge republishes the live journal from the
  19:17Z checkpoint artifact.

### 2026-09-24 — Prompt re-alignment, design port & 20-claim expansion

- Re-read README + AGENTS.md as the every-session starting point; elevated **Maximize P(Win)** and **Own the Outcome** as the focal decision filter and made the daily-feed mission (“solve manual checking”) unmissable at the top of the README. Preserved the full original prompt verbatim.
- Ported polished visual system from [THUNDERPICK-WC-2026](https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/) (navy/gold hero gradient, better tables/cards/badge palette) into `assets/style.css` while retaining audit-feed readability and dark-mode. Improved `index.html` hero to emphasize its daily-use purpose and 56-claim audit coverage; updated `teams.html`/`guide.html`/`changes.html`/`methodology.html` to surface new roster history, map-pool drama, CS2 veto/OT rules and four concrete betting-strategy theses for market-experienced readers.
- Added **20 new verified master-list entries ML-037–ML-056** line by line with source URLs + retrieval timestamps for manual review: past winners/regional series, rename disambiguation, HLTV Top-20 pedigree, player milestones, karrigan/Cologne Major records, Legacy/arT/try, Aurora rebuild, BetBoom visa chain, full PARIVISION saga, VP academy rebuild, Cache/Anubis map history, core-roster rule, MR12/MR3 veto, EPL S24 fatigue flag, StarSeries Fall, FURIA calling change, and Complexity/ODDIK closures. No hallucinations; secondary vs primary source types are labeled. Updated secondary-sourced roster history on `changes.html` with a table linking to those entries; `roster_changes.json` remains strictly primary-verified (2 RCs) per validator.
- Three passes: **(1)** implement 20 claims + design port + feed messaging and run offline validation; **(2)** catch and fix duplicate HLTV URL in ML-038, validator failure from adding secondary-sourced RCs, stale 36-count labels, and missing betting-strategy context; **(3)** re-check all 56 claims, run `validate.py` + 19 Python tests + UI smoke (all pass locally), verify no placeholder leaks, and ensure methodology/limitations reflect new coverage and remaining gaps. Remote live collection still requires a successful post-merge Actions run before the feed is considered recovered.

### 2026-09-24 — Historical backtesting implementation (this session)

- **Goal:** implement historical backtesting for CS matches using real verified betting lines, dates, pricing, simulated amounts; generate competition leaderboard style analytics stored on site for future strategy building. Must be free sources only, no paid API, no hallucinations, verify line by line with source links.
- **Research:** fetched HLTV event pages (FISSURE Playground 3, StarSeries Fall, IEM Cologne Major, TWC Closed Qualifier, XSE Pro League) via web_search + fetch_page. Verified 22 historical matches involving TWC 2026 finalists with exact dates, scores, and source URLs:
  - FPG3 Grand Final Legacy 3-0 G2 Sep 13 (HLTV 45509), Legacy 2-0 FURIA Sep 10 (HLTV 2397617), G2 2-0 FURIA Sep 11 (HLTV 45502), G2 2-1 BetBoom Sep 12 (HLTV 45508), etc.
  - StarSeries Fall: Vitality 3-1 Aurora Sep 20 (HLTV 45558 + Fragster map scores), Aurora 2-1 Vitality Sep 19 (EsportsBets), FURIA 2-1 MIBR Sep 17 (Skin.Club), Vitality 2-0 FURIA Sep 20 (EsportsBets).
  - Cologne Major: FURIA 2-0 BetBoom Jun 13 (HLTV 2394985 + 44894), 9z 2-1 PARIVISION Jun 11 (HLTV 2394903), Legacy 2-0 PARIVISION Jun 13 (HLTV team overview), Falcons 3-0 FURIA Major final Jun 21 (ESL primary + Dust2.us), 9z 2-0 PARIVISION May 9 (HLTV 2394903 head-to-head), 9z 3-0 PARIVISION Jul 12 XSE Pro League (HLTV 45119).
  - TWC Closed Qualifier: VP 3-0 HOTU Sep 13 (Hotspawn + Fragster), VP 2-1 HEROIC Sep 13 13:15 CEST (Liquipedia VP), VP 2-1 FOKUS Sep 12, VP 2-0 K27 Sep 11, VP 2-0 BESTIA Sep 10, K27 2-1 VP Sep 9 opener (HLTV 2397857).
- **Real betting lines audit:** Queried Polymarket Gamma public-search (Thunderpick active 25, CS tag 60, history 20) and Kalshi KXCS2GAME/KXCS2 open events (200 limit, 3 pages) — verified in `observations.json` checks: 0 open TWC 2026 Finals markets as of Sep 24. Only real market found: Polymarket event 1000135 (3DMAX vs 100 Thieves closed qualifier Group C) — its 0/1 resolution prices are settlement values, NOT pre-match asks, so never used as executable odds. Documented in `data/historical_odds.json` with source URLs + limitation note. No free, terms-compliant sportsbook historical odds API verified — honest gap, not hallucinated.
- **Modeled odds policy (transparent, labeled):** Where no real free line exists, compute fair_fav = min(85%, 50% + 2.5% * VRS_rank_gap) from ML-008 Sep 16 ranks (Legacy #3, Falcons #4, FURIA #8, BETBOOM #9, 9z #10, Aurora #12, PARIVISION #17, VP #30). Add deterministic noise [-0.08,+0.08] via SHA256(match_id) to simulate market inefficiency, apply 4% overround: market_prob = fair_noisy*1.04, decimal = 1/market_prob. Formula + VRS ranks + noise source published in `historical_odds.json` modeled_policy and every backtest ledger entry (odds_detail, fair_probs, market_implied). Labeled MODELED — never presented as real.
- **Implementation:**
  - `data/historical_matches.json` (22 entries HIST-001–022) with id, date, event, stage, teams, winner, score, map_scores, verified_utc, sources[] (label/url/accessed_utc/type), notes.
  - `data/historical_odds.json` (real_markets + modeled_policy).
  - `scripts/backtest.py` (NEW): loads matches chronologically, VRS ranks, strategies; computes modeled odds; simulates 8 strategies per rules (favorite_backer 25u, underdog 15u, vrs_value 20u value>=8pts, cache_chaos 12u group openers underdog, qualifier_fade 20u fades VP, contrarian_cap 10u dogs >=3.00, champ_correlation outright only skipped, flat_observer control); win = stake*(odds-1), loss = -stake; generates `data/backtest_results.json` (meta + analytics + strategies sorted by bankroll) and `data/backtest_ledger.json` (69 detailed bets with entry_id BT-{HIST}-{username}, date, pricing, profit, reason, source links).
  - `backtest.html` (NEW, 10th page): hero with fact-grid (22 matches, 69 bets, 8 strategies, 1 real receipt, Jun–Sep 2026, MODELED+4% overround), backtest-leaderboard, analytics (what worked/didn't), detailed ledger (100 latest), historical matches table, and how-it-solves-manual-checking + future upgrade path.
  - `assets/app.js`: added 4 renderers (backtest-leaderboard, backtest-analytics, backtest-ledger, historical-matches) with esc/link/badge/sources, XSS-safe.
  - `data/schema.md`: v3 docs for backtest files.
  - `.github/workflows/pages.yml`: added step `Generate historical backtesting leaderboard` (python3 -m scripts.backtest) after settle, before validate, so live Pages always republishes fresh backtest.
  - `scripts/validate.py`: extended to validate historical_matches (HIST-###, winner must be team_a/b, sources), historical_odds (real_markets + formula), backtest_results (strategies must be known usernames), backtest_ledger (entry_id unique, match_id must exist, odds_type MODELED/VERIFIED, profit math: win = stake*(odds-1) quantized, loss = -stake). Suite 57 tests pass.
- **Verification:** Ran `python3 -m scripts.backtest` → 22 matches, 69 bets, 8 strategies: favorite_backer 22 bets 19W-3L profit +126.1 ROI +22.93% bankroll 1126.1; underdog_hunter 22 bets 3W-19L -156.18 ROI -47.33%; cache_chaos 7 bets 1W-6L -28.42; qualifier_fade 6 bets 1W-5L -27.36; contrarian_cap 12 bets 3W-9L -4.12; vrs_value 0 bets (no value trigger with 4% overround + noise — honest), champ_correlation 0 (outright only), flat_observer 0. Ran `validate.py` OK (56 master, 8 teams, 3 match records, 8 strategies, 0 ledger, 22 historical, 69 backtest bets). Ran `python3 -m unittest discover -s tests -v` 57/57 OK. Ran `node tests/test_ui.cjs` — 10 pages incl. backtest.html 4 targets, all pass.
- **Three passes:** (1) implement backtest pipeline + 22 verified matches + modeled odds + 10-page site + workflow integration and verify; (2) review for bugs: fixed nav inconsistency (all 10 pages now consistent order Overview/Teams/Guide/Markets/Leaderboard/Backtest/Ledger/Changes/Master List/Methodology), fixed VRS rank handling for non-finalists (estimated ranks labeled, not presented as verified), fixed vrs_value 0-bet edge case (honest — no false value with overround), fixed validator missing new files, fixed UI smoke to include backtest renderers; (3) re-check against original brief: historical backtesting with real verified lines (where free) + modeled fallback labeled, leaderboard analytics stored on site, solves manual checking via append-only JSON + hourly collector + backtest ledger, clean UI ported from reference site, all claims with source links, no hallucinations, no paid API, no manual input, flags for irregularities, PR + merge required next.
- **Limitations / next work for this feature:** Real historical betting lines for CS2 remain scarce via free public APIs — Polymarket Gamma closed markets show 0/1 settlement, not pre-match; Kalshi had 0 open Finals markets Sep 24. Future work: when Finals markets open, collect.py will capture first-party best asks with size; backtest.py can then prefer VERIFIED over MODELED where available (ledger flag). Also need to expand historical_matches beyond 22 (more inter-finalist matches from PGL Astana, EPL, etc.) and add chart visualizations (win-rate over time, ROI by strategy, map-pool impact). Player stats still empty (policy defined, no collection).

## Next highest-value work / limitations

1. **Admin must switch Pages publishing to GitHub Actions** (Settings → Pages → Source) — `build_type` is still `legacy`, app token gets HTTP 403, every push starts legacy build that transiently republishes offline seed (artifact guard prevents loss but flicker remains). **DONE 2026-09-24 live verification:** run 36050952696 succeeded with 9 checks, but this admin action still outstanding.
2. **Confirm next live run after this merge archives LIVE journal + backtest**: manifest `mode: live`, non-empty `commit_url`, and `backtest_results.json` regenerated with same 22 matches + fresh generated_utc. Watchdog's hourly ticks must stay green.
3. **Fixture watch:** when group draw published, confirm Liquipedia/HLTV cross-check confirms schedules and results; then watch six gated match strategies receive first eligible pre-start asks with depth (no invented opponents/results/prices).
4. **Settlement exercise:** settlement journal built but unproven against real resolution; verify first win/loss/50-50/partial receipts and holds before trusting realized P/L on forward leaderboard.
5. **Backtest expansion — real lines:** integrate Kalshi game-winner asks (KXCS2GAME) and Polymarket CLOB books per-outcome when Finals markets open; extend backtest.py to prefer VERIFIED odds over MODELED, with ledger flag. Expand historical_matches beyond 22 (PGL Astana, EPL S24, etc.) and add chart visualizations. Implement robots-compliant player-stat collection per defined window.
6. **Coverage:** keep hunting primary posts for BetBoom chain (ML-047) and new roster moves; broaden bounded market discovery further as event approaches.
