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
from pathlib import Path

from .collect import OUTPUT, ROOT, SourceError, parse_time, verify_history

LEDGER = ROOT / "data" / "ledger.json"


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
    # Decisions are immutable. Settlements/corrections need a separate verified
    # journal before the product can change a pending decision's status.
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
    for obs, entries in ((published, published_ledger), (artifact, artifact_ledger)):
        if obs is not None:
            restore_observations(current, obs)
            restore_ledger(ledger, entries)
    if published is None:
        selected, selected_ledger, source = artifact, artifact_ledger, "Actions checkpoint"
    elif artifact is None:
        selected, selected_ledger, source = published, published_ledger, "Pages"
    elif parse_time(published["last_attempt_utc"]) >= parse_time(artifact["last_attempt_utc"]):
        restore_observations(artifact, published)
        restore_ledger(artifact_ledger, published_ledger)
        selected, selected_ledger, source = published, published_ledger, "Pages"
    else:
        restore_observations(published, artifact)
        restore_ledger(published_ledger, artifact_ledger)
        selected, selected_ledger, source = artifact, artifact_ledger, "Actions checkpoint"
    if require_live and selected.get("mode") != "live":
        raise SourceError("journal reverted to offline research seed; require a prior successful live run")
    return selected, selected_ledger, source


def artifact_json(directory: Path, name: str) -> dict:
    """Handle either artifact path layout without accepting arbitrary files."""
    paths = [directory / name, directory / "data" / name]
    found = [p for p in paths if p.is_file()]
    if len(found) != 1:
        raise SourceError(f"Actions checkpoint must contain exactly one {name}")
    return json.loads(found[0].read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, help="downloaded published data/observations.json")
    parser.add_argument("--ledger", type=Path, help="downloaded published data/ledger.json")
    parser.add_argument("--artifact-dir", type=Path, help="last successful Actions journal checkpoint")
    parser.add_argument("--require-live-history", action="store_true", help="never select the pre-launch offline seed")
    args = parser.parse_args(argv)
    if (args.observations is None) != (args.ledger is None):
        parser.error("--observations and --ledger must be supplied together")
    current = json.loads(OUTPUT.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    published = json.loads(args.observations.read_text(encoding="utf-8")) if args.observations else None
    old_ledger = json.loads(args.ledger.read_text(encoding="utf-8")) if args.ledger else None
    artifact = artifact_json(args.artifact_dir, "observations.json") if args.artifact_dir else None
    artifact_ledger = artifact_json(args.artifact_dir, "ledger.json") if args.artifact_dir else None
    result, result_ledger, source = choose_history(
        current, ledger, published, old_ledger, artifact, artifact_ledger,
        require_live=args.require_live_history,
    )
    # Both candidates and their coverage were checked BEFORE writing either file.
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LEDGER.write_text(json.dumps(result_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Restored {len(result['quotes'])} quote receipts and {len(result_ledger['entries'])} immutable paper decisions from {source}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
