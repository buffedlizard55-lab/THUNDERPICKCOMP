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

## Highest-value next steps

1. Choose a maintainable static-site/data architecture that can publish through GitHub Pages without exposing secrets or relying on a paid API.
2. Define a source and record schema (including provenance, observed-at time, validity/staleness, and conflict flags) before collecting a master list.
3. Research and test a small end-to-end data path for official tournament facts, roster changes, match results, and free/public odds or prediction-market snapshots. Document coverage and any source terms or access constraints.
4. Build the site and automated validation around that schema; do not populate it with unverified example facts.
5. Add tests, scheduled refresh/monitoring, failure alerts or visible stale states, and a documented review workflow for irregularities.
