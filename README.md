# THUNDERPICKCOMP

> **Project starting point:** At the beginning of every task in this repository, read this README before researching, proposing changes, or editing files. `AGENTS.md` makes this a repository-level working instruction. Use this charter to keep the product useful, reliable, and aligned with its purpose.

## Mission

Build a clear, dependable, publicly sourced expert hub and forward-looking prediction/leaderboard competition for the **Thunderpick World Championship 2026** and Counter-Strike 2 (CS2). Help people understand the event and follow relevant changes without having to manually check many sites themselves. A useful current feed must be timely, traceable, and honest about what is not known.

The product should bring together verified tournament information, teams and player/roster updates, match results, relevant public betting and prediction-market prices, and transparent simulated-user strategies and performance. It should be simple to navigate and easy to use every day. **Correctness and auditability take priority over appearing comprehensive.** If a claim or price cannot be independently verified, do not present it as fact or silently fill in a gap.

## Core values

### Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

### Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Apply these values to research, product decisions, implementation, testing, and maintenance. Be candid about limitations; fix issues that can be fixed; and make tradeoffs in favor of a trustworthy, useful product rather than unsupported breadth.

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

## Original project brief

The following preserves the project requirements supplied by the owner. Treat it as the product brief; factual content still has to meet the verification standards above.

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

## Repository map (as of 2026-09-24)

The repository already contained a static, responsive, eight-page Pages site, a
32-entry sourced baseline, eight simulated policy definitions and an empty
paper ledger when this continuation began. **That earlier site was not an
up-to-date feed**: it had static timestamps and no collector. This session
adds the first forward-only, scoped, free-source monitoring pipeline.

- `index.html`, `teams.html`, `guide.html`, `markets.html`, `leaderboard.html`,
  `ledger.html`, `changes.html`, `master-list.html`, `methodology.html` — nine-page
  public hub (including sourced CS2/market explainers).
- `assets/app.js`, `assets/style.css` — accessible static UI over JSON, including
  actual UTC freshness/source-error status and links for manual review.
- `data/master_list.json` — 36 dated sourced claims (ML-001–ML-036). Four new
  primary-source entries cover a Sep 17 PARIVISION bench/signing, Valve VRS
  Sep 7 and an actual **closed** Polymarket qualifier market; an older absence
  statement was corrected, not silently left in place.
- `data/teams.json`, `data/matches.json`, `data/roster_changes.json` — dated
  team/event snapshot, an outright reference + draw status and verified moves.
- `data/observations.json` — forward, append-only quote/VRS/signal journal with
  exact query scopes, timestamps, alerts and source links. Initially an
  **offline, partial research replay**; it is NOT a successful scheduled feed
  until Pages' first live deployment completes.
- `data/ledger.json`, `data/strategies.json` — 8 simulated accounts: one active
  conditional outright policy, one no-bet control, six paused match policies.
  Ledger is intentionally empty until forward, first-party eligible quotes.
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
  replay (not betting inputs).
- `.github/workflows/ci.yml`, `.github/workflows/pages.yml` — test on PR,
  and attempt live collection, validation and Pages deployment on main + hourly
  schedule. A cron is best effort, not a tick-by-tick live feed.

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
The first [live Actions deployment](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/actions/runs/36038171748) after [PR #3](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/pull/3) merged succeeded on Sep 24 at 18:00 UTC; the published journal showed `mode=live`, two visible source errors, no quotes and no paper positions. A successful deployment after **each** future merge is required before calling its changes published. No feature here is a real wager or investment advice.

### Durability and the "no manual checking" goal

Pages alone is static. The workflow restores the public JSON history from the
same HTTPS site before each scheduled run **and compares it with the last
successful Actions journal artifact**. It uses the newest compatible history
that covers older immutable receipts/decisions, then republishes. If neither
has a covering live journal or they conflict, it must **stop** rather than
discard historical prices/bets. The one-time bootstrap was tied to the prior
`main` commit, not a standing permission to reset data. Artifacts expire after
30 days; a long-term, versioned free archive is **not implemented**. This is a
scoped first step against manual checking, not full match/odds/roster coverage.

**Repository admin action:** Pages is still set to legacy `main` branch
publishing. The Actions deployment succeeded anyway, but each push also starts
a legacy build that can temporarily replace live data with the tracked offline
seed. The GitHub App token cannot change this setting (Pages API HTTP 403). An
admin should open [Settings → Pages](https://github.com/buffedlizard55-lab/THUNDERPICKCOMP/settings/pages)
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

## Next highest-value work / limitations

1. **Verify the next scheduled/dispatch Pages run:** both Valve and Liquipedia checks, eligible quote scope, rolling journal recovery and UTC freshness. Switch Pages publishing to GitHub Actions (admin setting) to eliminate competing legacy builds; the recovery artifact is not permanent storage.
2. **Match pipeline:** cross-check *both* official-data fixture pages/results,
   dates and outcome IDs (HLTV + Liquipedia), then implement and unpause the
   six match strategies with reproducible pre-start depth checks. No invented
   opponent, fixture, result or price.
3. **Settlement journal:** append-only venue-resolution receipts and independent
   result confirmation, including canceled/forfeit/partial cases. Never turn
   a 50/50 resolution into a presumed refund.
4. **Durability:** versioned public storage for rolling quote/decision history
   beyond Pages plus alerting when jobs stall. Actions artifacts expire.
5. **Coverage:** broader free, terms-compliant market discovery, researched
   reserve players and additional primary team-change statements, sourced
   player stats with a clearly specified time window, and sourced CS2 analysis.
