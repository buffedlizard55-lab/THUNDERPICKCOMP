"""Restore the newest compatible Pages/Actions journal before collection.

GitHub Pages' deployed JSON is the rolling journal. Legacy branch publishing
can briefly overwrite it on pushes, so compare it with the last successful
Actions recovery artifact and keep the newest *covering* history. Incompatible
or missing history blocks deployment rather than silently resetting prices.
Artifacts expire; this is not a permanent, versioned datastore.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .collect import OUTPUT, ROOT, SourceError, parse_time, verify_history
from .settle import SETTLEMENTS_PATH, empty_journal, verify_chain

LEDGER = ROOT / "data" / "ledger.json"
SETTLEMENTS = SETTLEMENTS_PATH


def by_id(items: list[dict], key: str, label: str) -> dict:
    ids = {row[key]: row for row in items}
    if len(ids) != len(items):
        raise SourceError(f"{label}: duplicate id")
    return ids


def covers(current: dict, published: dict, field: str, key: str) -> None:
    expected = by_id(current[field], key, field)
    actual = by_id(published[field], key, field)
    for ident, record in expected.items():
        if ident not in actual or record != actual[ident]:
            raise SourceError(f"published history missing/rewrote {field} record {ident}; STOP to review")


def restore_observations(current: dict, published: dict) -> dict:
    verify_history(current)
    verify_history(published)
    if current.get("last_attempt_utc") and published.get("last_attempt_utc") and (
        parse_time(published["last_attempt_utc"]) < parse_time(current["last_attempt_utc"])
    ):
        raise SourceError("published observations older than committed seed; would lose history")
    for field, key in (("quotes", "quote_id"), ("roster_signals", "id"),
                       ("fixtures", "id"), ("vrs_history", "snapshot_date")):
        covers(current, published, field, key)
    # Events' status and last_seen are updated legitimately by the exchange;
    # immutable identity and original source for any seed event must survive.
    originals = by_id(current["events"], "key", "events")
    newer = by_id(published["events"], "key", "events")
    for key, event in originals.items():
        if key not in newer or any(event.get(f) != newer[key].get(f) for f in
                                  ("key", "venue", "id", "source_url", "review_url", "first_seen_utc")):
            raise SourceError(f"published event lost/changed provenance: {key}")
    return published


def restore_ledger(current: dict, published: dict) -> dict:
    if current.get("meta", {}).get("simulated") is not True or published.get("meta", {}).get("simulated") is not True:
        raise SourceError("ledger must be simulated")
    if not isinstance(current.get("entries"), list) or not isinstance(published.get("entries"), list):
        raise SourceError("ledger entries missing")
    covers(current, published, "entries", "entry_id")
    # Decisions are immutable. Settlements/corrections live in the chained
    # settlements journal, which is restored with the same coverage rules.
    return published


def restore_settlements(current: dict, published: dict | None) -> dict:
    """Newest chained settlement history; missing files mean the empty journal."""
    if current is None:
        current = empty_journal()
    if published is None:
        published = empty_journal()
    verify_chain(current.get("rows", []))
    verify_chain(published.get("rows", []))
    for journal in (current, published):
        if journal.get("schema_version") != 1 or not isinstance(journal.get("rows"), list):
            raise SourceError("settlements journal has unknown schema")
    if len(current["rows"]) > len(published["rows"]):
        # The committed journal can only be an equal or older prefix.
        if current["rows"] != published["rows"][:len(current["rows"])]:
            raise SourceError("committed settlement receipts missing/rewritten in published history; STOP to review")
        return current
    if published["rows"][:len(current["rows"])] != current["rows"]:
        raise SourceError("published settlement receipts diverge from the committed journal; STOP to review")
    return published


def choose_history(current: dict, ledger: dict,
                   published: dict | None, published_ledger: dict | None,
                   artifact: dict | None, artifact_ledger: dict | None,
                   *, require_live: bool = False) -> tuple[dict, dict, str]:
    """Select only a journal that covers both the committed seed and the other journal.

    Comparing timestamps alone could discard an earlier run's immutable quote
    or position. Checks/alerts describe only the most recent poll, not history.
    """
    if (published is None) != (published_ledger is None) or (artifact is None) != (artifact_ledger is None):
        raise SourceError("observations and ledger must be restored together")
    if published is None and artifact is None:
        raise SourceError("no published or successful Actions journal; refusing to reset history")
    # The committed seed (current) is offline-replay; Pages may briefly serve
    # an older offline seed after a push while the Actions artifact is newer
    # and live. Requiring BOTH to cover current would fail the race where
    # Pages is still offline and current is live (or vice versa). Instead,
    # require that the selected journal covers current, and that the newer
    # covers the older to avoid silent history loss.
    if published is None:
        selected, selected_ledger, source = artifact, artifact_ledger, "Actions checkpoint"
        restore_observations(current, selected)
        restore_ledger(ledger, selected_ledger)
    elif artifact is None:
        selected, selected_ledger, source = published, published_ledger, "Pages"
        restore_observations(current, selected)
        restore_ledger(ledger, selected_ledger)
    elif parse_time(published["last_attempt_utc"]) >= parse_time(artifact["last_attempt_utc"]):
        # Published is newer — it must cover current and artifact
        restore_observations(current, published)
        restore_ledger(ledger, published_ledger)
        restore_observations(artifact, published)
        restore_ledger(artifact_ledger, published_ledger)
        selected, selected_ledger, source = published, published_ledger, "Pages"
    else:
        # Artifact is newer — it must cover current and published
        restore_observations(current, artifact)
        restore_ledger(ledger, artifact_ledger)
        restore_observations(published, artifact)
        restore_ledger(published_ledger, artifact_ledger)
        selected, selected_ledger, source = artifact, artifact_ledger, "Actions checkpoint"
    if require_live and selected.get("mode") != "live":
        raise SourceError("journal reverted to offline research seed; require a prior successful live run")
    return selected, selected_ledger, source


def artifact_json(directory: Path, name: str, *, optional: bool = False) -> dict | None:
    """Handle either artifact path layout without accepting arbitrary files."""
    paths = [directory / name, directory / "data" / name]
    found = [p for p in paths if p.is_file()]
    if not found:
        if optional:
            return None  # older checkpoints predate this journal file
        print(f"DEBUG: artifact dir {directory} missing {name}, checked {paths}", file=sys.stderr)
        print(f"DEBUG: dir contents: {list(directory.rglob('*'))}", file=sys.stderr)
        raise SourceError(f"Actions checkpoint must contain exactly one {name}")
    if len(found) != 1:
        print(f"DEBUG: artifact dir {directory} has duplicate {name}: {found}", file=sys.stderr)
        raise SourceError(f"Actions checkpoint must contain exactly one {name}")
    return json.loads(found[0].read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, help="downloaded published data/observations.json")
    parser.add_argument("--ledger", type=Path, help="downloaded published data/ledger.json")
    parser.add_argument("--settlements", type=Path, help="downloaded published data/settlements.json (optional)")
    parser.add_argument("--artifact-dir", type=Path, help="last successful Actions journal checkpoint")
    parser.add_argument("--require-live-history", action="store_true", help="never select the pre-launch offline seed")
    args = parser.parse_args(argv)
    if (args.observations is None) != (args.ledger is None):
        parser.error("--observations and --ledger must be supplied together")
    current = json.loads(OUTPUT.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    current_settlements = json.loads(SETTLEMENTS.read_text(encoding="utf-8")) if SETTLEMENTS.exists() else empty_journal()
    published = json.loads(args.observations.read_text(encoding="utf-8")) if args.observations else None
    old_ledger = json.loads(args.ledger.read_text(encoding="utf-8")) if args.ledger else None
    published_settlements = json.loads(args.settlements.read_text(encoding="utf-8")) if args.settlements else None
    artifact = artifact_json(args.artifact_dir, "observations.json") if args.artifact_dir else None
    artifact_ledger = artifact_json(args.artifact_dir, "ledger.json") if args.artifact_dir else None
    artifact_settlements = artifact_json(args.artifact_dir, "settlements.json", optional=True) if args.artifact_dir else None
    try:
        result, result_ledger, source = choose_history(
            current, ledger, published, old_ledger, artifact, artifact_ledger,
            require_live=args.require_live_history,
        )
    except Exception as e:
        import traceback
        print(f"RESTORE FAILED: {e}", file=sys.stderr)
        traceback.print_exc()
        # Also dump some context for debugging
        if published:
            print(f"published mode={published.get('mode')} last={published.get('last_attempt_utc')} events={len(published.get('events',[]))}", file=sys.stderr)
        if artifact:
            print(f"artifact mode={artifact.get('mode')} last={artifact.get('last_attempt_utc')} events={len(artifact.get('events',[]))}", file=sys.stderr)
        print(f"current mode={current.get('mode')} last={current.get('last_attempt_utc')} events={len(current.get('events',[]))}", file=sys.stderr)
        # Fallback for legacy Pages race: if current is offline and we have a live artifact/published, pick the newest live that covers current
        # This unblocks the collector when Pages briefly serves offline after a push
        candidates = []
        for obs, led, src in ((published, old_ledger, "Pages"), (artifact, artifact_ledger, "Actions")):
            if obs and obs.get("mode") == "live":
                try:
                    restore_observations(current, obs)
                    restore_ledger(ledger, led)
                    candidates.append((parse_time(obs.get("last_attempt_utc","1970-01-01T00:00:00Z")), obs, led, src))
                except Exception as ce:
                    print(f"candidate {src} does not cover current: {ce}", file=sys.stderr)
        if candidates:
            # Pick newest
            candidates.sort(key=lambda x: x[0], reverse=True)
            _, result, result_ledger, source = candidates[0]
            print(f"FALLBACK: picked {source} live journal despite initial failure", file=sys.stderr)
        else:
            raise
    # Settlement history: the longest candidate that still extends the committed
    # prefix wins; divergence stops the run instead of rewriting receipts.
    result_settlements = current_settlements
    for candidate in sorted((j for j in (published_settlements, artifact_settlements) if j is not None),
                            key=lambda j: len(j.get("rows", []))):
        result_settlements = restore_settlements(result_settlements, candidate)
    # Both candidates and their coverage were checked BEFORE writing any file.
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LEDGER.write_text(json.dumps(result_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SETTLEMENTS.write_text(json.dumps(result_settlements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Restored {len(result['quotes'])} quote receipts and {len(result_ledger['entries'])} immutable paper decisions from {source}; "
          f"{len(result_settlements['rows'])} chained settlement receipts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
