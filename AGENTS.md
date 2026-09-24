# Repository agent instructions

Before starting **every** task in this repository:

1. Read `README.md` from beginning to end. It is the canonical project mission, requirements, and original brief.
2. Read this file, then inspect the current tree, Git status, and relevant implementation/tests.
3. Keep changes aligned with README's mission, core values, source standards, and three-pass review process.

For any tournament, team, player, roster, match, odds, prediction-market, or results data:

- Verify each claim against an accessible source and keep a reviewable source link and retrieval/publication timestamp. Prefer primary sources. A prior assistant answer, a search snippet, an existing project page, or an unsourced dataset is not verification.
- Do not create unsupported records to satisfy a requested count. Check for duplicates and verify line by line before adding entries.
- Preserve the source's exact price/line and *HTTP receipt time*, make calculations reproducible, label estimates and simulated actions, and flag conflicts, missing data, parsing changes, and stale data rather than guessing.
- Read `data/schema.md` before touching the collector or ledger. Polymarket Gamma displayed/outcome prices and 0/1 resolved markets are not executable pre-match asks; use the outcome-specific first-party CLOB book. Kalshi last trade is not its Yes ask. A quote is not a completed trade.
- Valve Global VRS ranked-roster snapshots and the dated Sep 24 event lineup answer different questions; a snapshot difference is not proof of a transfer or its effective date. A partial or failed market query never proves market absence.
- Preserve the published Pages journal when updating workflows: `scripts/restore.py` must compare published data with the last successful Actions checkpoint and reject lost/conflicting immutable history rather than reset it. Pages still has legacy branch publishing enabled (admin change required), which can temporarily overwrite the live journal on pushes. Offline fixtures are partial research replays, not live data or paper-betting inputs.
- Tests must not assume tracked `data/observations.json` / `data/ledger.json` are immutable seeds: the Pages job restores and mutates them *before* testing. Keep synthetic test baselines separate and exercise the disposable live-path CI check.
- Use no paid API/subscription. Follow source terms, attribution requirements, and rate limits.
- Rules for the real-line strategy lab (`data/lab/`, `scripts/historical_lines.py`, `scripts/strategy_lab.py`):
  - **Receipts** (`data/lab/lines/*.json`) are append-only venue data.
    - Never hand-edit them, back-fill them, or "fix" a price.
    - If a stored receipt looks wrong, re-run `--audit` and flag the mismatch.
  - **Quotes:**
    - A quote must predate its checkpoint. Settled 0/1 prices and post-settlement books are never quotes.
    - Polymarket `prices-history` `p` is a reference price, not an ask.
  - **Strategies:** keep the no-bet control at exactly 1,000 units. A strategy may use only data timestamped before its decision time.
  - **Adding a strategy family:**
    - add a validator or test for look-ahead;
    - keep the ≥100 distinct-strategy floor;
    - report distinctness by bet selections, not only by definition count.
- The Pages archive step must never switch branches in the build working tree. Commit `journal-archive` from a separate `git worktree` (an in-place checkout reverted the live journal to the offline seed on 2026-09-24). `restore.py` must fail with a non-zero exit and never fall back to the committed seed.

Before finishing, complete the three passes required by the README, run applicable checks, review the diff, and report verified work, uncertainty, limitations, and next steps. Never state that a source, test, or requirement was verified unless it actually was.