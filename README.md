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

## Repository map (as of 2026-09-24 — this session's baseline)

The repository already contained a static, responsive, nine-page Pages site, a
56-entry sourced ledger after this session (36 + 20 new), eight simulated policy definitions and an empty
paper ledger when this continuation began. **That earlier site was not an
up-to-date daily feed**: it had static timestamps and no collector. The first continuation added the forward-only, scoped, free-source monitoring pipeline; this session ports the reference-site design and expands verified coverage.

- `index.html`, `teams.html`, `guide.html`, `markets.html`, `leaderboard.html`,
  `ledger.html`, `changes.html`, `master-list.html`, `methodology.html` — nine-page
  public hub (copied/adapted from [THUNDERPICK-WC-2026](https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/) design — navy/gold hero, better tables/cards — with source-verified content).
- `assets/app.js`, `assets/style.css` — accessible static UI over JSON, including
  actual UTC freshness/source-error status and links for manual review. Style now mirrors reference site's polished system (hero gradient, badges, card grids) while preserving audit-feed readability.
- `data/master_list.json` — **56 dated sourced claims (ML-001–ML-056)**. This session added 20 new entries (ML-037–ML-056) covering: roll of honour, 2026 regional winners, VRSDelivery→DragonClaw rename, HLTV Top-20 2025 pedigree (6 TWC players), NiKo/m0NESY milestones, karrigan move, Cologne Major records, Legacy arT/try, Aurora rebuild, BetBoom visa chain, full PARIVISION saga, VP academy rebuild, map-pool Cache history, core-roster rule, veto/OT servers, EPL S24 clash, StarSeries Fall, FURIA calling change, and org closures — each with source links for manual review, verified line by line, no hallucinations.
- `data/teams.json`, `data/matches.json`, `data/roster_changes.json` — dated
  team/event snapshot, an outright reference + draw status and 2 primary-verified moves (RC-001/002). Historical moves (arT, try, kyxsan etc.) are now secondary-sourced in ML-043–ML-049 and surfaced on `changes.html` + `teams.html` with source-type labels; reserves remain partial by design.
- `data/observations.json` — forward, append-only quote/VRS/signal journal with
  exact query scopes, timestamps, alerts and source links. Initially an
  **offline, partial research replay**; it is NOT a successful scheduled feed
  until Pages' first live deployment completes. The UI now emphasizes solving manual checking via hourly checks + visible staleness.
- `data/ledger.json`, `data/strategies.json` — 8 simulated accounts: one active
  conditional outright policy, one no-bet control, and six match policies that
  are active **with gates** (double-sourced fixture + strictly pre-start fresh
  first-party ask + top-of-book depth + unambiguous association + pending
  budget; the TBD draw means nothing can be papered yet). Ledger is
  intentionally empty until forward, first-party eligible quotes;
  betting-strategy theses are documented on `guide.html#betting-strategies`
  with a sourced-facts vs labeled-heuristics research table.
- `data/settlements.json` — append-only, SHA-256-chained settlement journal
  (venue-resolution receipts + independent result confirmation + decision
  rows + holds). Void is never assumed; 50/50 settles as partial at the
  venue's fraction; conflicts stay pending.
- `data/player_stats.json` — the dated player-stat window policy (HLTV Rating
  3.0, trailing 90 days, ≥40 maps) required before any rating is published.
  Ships empty: no compliant collection has run yet.
- `data/schema.md` — exact provenance, limitations, source scope and money math.
- `scripts/collect.py` — bounded read-only collection from Valve GitHub API,
  Liquipedia wiki API (fixture *signals* only), Kalshi and Polymarket Gamma/CLOB.
  Does not use a paid API or a sportsbook scraper. Does not claim exhaustive
  coverage from a zero-result query.
- `scripts/competition.py` — forward-only two-position outright paper strategy,
  dependent on same-run first-party best asks, sizes and source timestamps.
- `scripts/restore.py` — refuses to reset the prior published Pages quote/ledger
  journal; immutable receipts survive scheduled deployments.
- `scripts/validate.py`, `tests/` — schema/source/duplicate/gross-money checks,
  unit tests and documented **partial** real-response excerpts for offline
  replay (not betting inputs). All 56 claims, 19 Python tests and UI smoke tests pass locally; remote live run still must be verified post-merge.
- `.github/workflows/ci.yml`, `.github/workflows/pages.yml`,
  `.github/workflows/watchdog.yml` — test on PR; collect, validate, record
  settlement receipts, deploy Pages on main + hourly schedule, append the
  versioned `journal-archive` branch, and fail loudly when the hourly job
  stalls. A cron is best effort, not a tick-by-tick live feed.

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

### 2026-09-24 — Prompt re-alignment, design port & 20-claim expansion

- Re-read README + AGENTS.md as the every-session starting point; elevated **Maximize P(Win)** and **Own the Outcome** as the focal decision filter and made the daily-feed mission (“solve manual checking”) unmissable at the top of the README. Preserved the full original prompt verbatim.
- Ported polished visual system from [THUNDERPICK-WC-2026](https://buffedlizard55-lab.github.io/THUNDERPICK-WC-2026/) (navy/gold hero gradient, better tables/cards/badge palette) into `assets/style.css` while retaining audit-feed readability and dark-mode. Improved `index.html` hero to emphasize its daily-use purpose and 56-claim audit coverage; updated `teams.html`/`guide.html`/`changes.html`/`methodology.html` to surface new roster history, map-pool drama, CS2 veto/OT rules and four concrete betting-strategy theses for market-experienced readers.
- Added **20 new verified master-list entries ML-037–ML-056** line by line with source URLs + retrieval timestamps for manual review: past winners/regional series, rename disambiguation, HLTV Top-20 pedigree, player milestones, karrigan/Cologne Major records, Legacy/arT/try, Aurora rebuild, BetBoom visa chain, full PARIVISION saga, VP academy rebuild, Cache/Anubis map history, core-roster rule, MR12/MR3 veto, EPL S24 fatigue flag, StarSeries Fall, FURIA calling change, and Complexity/ODDIK closures. No hallucinations; secondary vs primary source types are labeled. Updated secondary-sourced roster history on `changes.html` with a table linking to those entries; `roster_changes.json` remains strictly primary-verified (2 RCs) per validator.
- Three passes: **(1)** implement 20 claims + design port + feed messaging and run offline validation; **(2)** catch and fix duplicate HLTV URL in ML-038, validator failure from adding secondary-sourced RCs, stale 36-count labels, and missing betting-strategy context; **(3)** re-check all 56 claims, run `validate.py` + 19 Python tests + UI smoke (all pass locally), verify no placeholder leaks, and ensure methodology/limitations reflect new coverage and remaining gaps. Remote live collection still requires a successful post-merge Actions run before the feed is considered recovered.

## Next highest-value work / limitations

1. **Verify the first run with the new pipeline after this merge:** nine scoped
   checks (now including `hltv_crosscheck` and `polymarket_teams`), the
   settle/archive steps, and watchdog scheduling. **Admin:** switch Pages
   publishing to GitHub Actions (Settings → Pages → Source) — the app token
   gets HTTP 403 on this setting, and legacy builds transiently republish the
   offline seed on every push.
2. **Fixture watch:** when the group draw is published, confirm the
   Liquipedia/HLTV cross-check confirms schedules and, after matches, results;
   then watch the six gated match strategies receive their first eligible
   pre-start asks with depth (no invented opponents/results/prices).
3. **Settlement exercise:** the settlement journal is built but unproven
   against a real resolution; verify its first win/loss/50-50/partial receipts
   and holds before trusting realized P/L on the leaderboard.
4. **Archive monitoring:** confirm the first `journal-archive` commits land and
   watchdog runs stay green; keep an eye on archive growth.
5. **Coverage:** implement robots-compliant player-stat collection under the
   defined window before publishing any rating; keep hunting primary posts for
   the BetBoom chain (ML-047) and new roster moves; broaden bounded market
   discovery further (more series/tags) as the event approaches.
