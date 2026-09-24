"""Restore the previous *published* Pages history before the next collection.

GitHub Pages' deployed JSON is the rolling journal. CI refuses to overwrite it
if unavailable or if committed seed records would disappear/change. The job
also uploads an Actions artifact as a short-lived recovery checkpoint. This is
not a substitute for a permanent, versioned datastore; see README limitations.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True, help="downloaded published data/observations.json")
    parser.add_argument("--ledger", type=Path, required=True, help="downloaded published data/ledger.json")
    args = parser.parse_args(argv)
    current = json.loads(OUTPUT.read_text(encoding="utf-8"))
    published = json.loads(args.observations.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    old_ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    result = restore_observations(current, published)
    result_ledger = restore_ledger(ledger, old_ledger)
    # Both checks must pass BEFORE writing either file.
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LEDGER.write_text(json.dumps(result_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Restored {len(result['quotes'])} quote receipts and {len(result_ledger['entries'])} immutable paper decisions from Pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
