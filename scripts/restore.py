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
                   *, require_live: bool = False,
                   archive: dict | None = None, archive_ledger: dict | None = None) -> tuple[dict, dict, str]:
    """Select the NEWEST candidate journal and require it to cover the committed seed and every
    other candidate; otherwise STOP. Nothing is ever selected by timestamp alone.

    Candidates: published Pages JSON, last successful Actions artifact, and the latest commit of
    the versioned ``journal-archive`` branch (outlives artifacts and cannot be overwritten by the
    legacy branch Pages build). The only candidate that may be left uncovered is a stale
    *offline-replay* seed that is not newer than the committed seed: that is the legacy Pages build
    republishing tracked files, and it carries no live receipts. Checks/alerts describe only the
    most recent poll, not history.
    """
    pairs = ((published, published_ledger, "Pages"), (artifact, artifact_ledger, "Actions checkpoint"),
             (archive, archive_ledger, "journal-archive"))
    for obs, led, label in pairs:
        if (obs is None) != (led is None):
            raise SourceError(f"observations and ledger must be restored together ({label})")
    candidates = [(obs, led, label) for obs, led, label in pairs if obs is not None]
    if not candidates:
        raise SourceError("no published or successful Actions journal; refusing to reset history")
    current_time = parse_time(current["last_attempt_utc"]) if current.get("last_attempt_utc") else None

    def stale_seed(obs: dict) -> bool:
        return (obs.get("mode") != "live" and current_time is not None and obs.get("last_attempt_utc")
                and parse_time(obs["last_attempt_utc"]) <= current_time)

    candidates.sort(key=lambda c: parse_time(c[0]["last_attempt_utc"]), reverse=True)
    selected, selected_ledger, source = candidates[0]
    restore_observations(current, selected)
    restore_ledger(ledger, selected_ledger)
    for obs, led, label in candidates[1:]:
        if stale_seed(obs):
            continue
        try:
            restore_observations(obs, selected)
            restore_ledger(led, selected_ledger)
        except SourceError as exc:
            raise SourceError(f"newest journal ({source}) does not cover {label}: {exc}") from exc
    if require_live and selected.get("mode") != "live":
        raise SourceError("journal reverted to offline research seed; require a prior successful live run")
    return selected, selected_ledger, source


PROVENANCE_IDENTITY = ("key", "venue", "id", "source_url", "review_url")


def repair_first_seen(result: dict, history: list[dict]) -> list[str]:
    """Move an event's first_seen_utc EARLIER only when a versioned journal-archive snapshot shows
    the identical event (same key/venue/id/source_url/review_url) was already seen earlier.

    Repairs the 2026-09-24 incident where a since-removed restore fallback republished the offline
    seed and reset first_seen_utc for 19 events. Never moves a timestamp later, never invents one.
    """
    earliest: dict[str, tuple[str, str]] = {}
    for snap in history:
        for event in snap.get("events", []):
            key, seen = event.get("key"), event.get("first_seen_utc")
            if not key or not seen:
                continue
            ident = json.dumps([event.get(f) for f in PROVENANCE_IDENTITY])
            if key not in earliest or parse_time(seen) < parse_time(earliest[key][0]):
                earliest[key] = (seen, ident)
    notes = []
    for event in result.get("events", []):
        found = earliest.get(event.get("key"))
        if not found:
            continue
        seen, ident = found
        if ident == json.dumps([event.get(f) for f in PROVENANCE_IDENTITY]) and \
                parse_time(seen) < parse_time(event["first_seen_utc"]):
            notes.append(f"{event['key']}: first_seen_utc {event['first_seen_utc']} -> {seen} (journal-archive evidence)")
            event["first_seen_utc"] = seen
    return notes


def artifact_json(directory: Path, name: str, *, optional: bool = False) -> dict | None:
    """Handle either artifact path layout without accepting arbitrary files."""
    paths = [directory / name, directory / "data" / name]
    found = [p for p in paths if p.is_file()]
    if not found:
        if optional:
            return None  # older checkpoints predate this journal file
        raise SourceError(f"Actions checkpoint must contain exactly one {name}")
    if len(found) != 1:
        raise SourceError(f"Actions checkpoint must contain exactly one {name}")
    return json.loads(found[0].read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, help="downloaded published data/observations.json")
    parser.add_argument("--ledger", type=Path, help="downloaded published data/ledger.json")
    parser.add_argument("--settlements", type=Path, help="downloaded published data/settlements.json (optional)")
    parser.add_argument("--artifact-dir", type=Path, help="last successful Actions journal checkpoint")
    parser.add_argument("--archive-dir", type=Path, help="latest journal-archive branch snapshot (durable)")
    parser.add_argument("--provenance-history", type=Path,
                        help="directory of older journal-archive observations snapshots (first_seen repair evidence)")
    parser.add_argument("--debug-dir", type=Path, default=Path("/tmp/restore-debug"),
                        help="where to write diagnostics on failure (never inside data/)")
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
    archive = artifact_json(args.archive_dir, "observations.json") if args.archive_dir else None
    archive_ledger = artifact_json(args.archive_dir, "ledger.json") if args.archive_dir else None
    archive_settlements = artifact_json(args.archive_dir, "settlements.json", optional=True) if args.archive_dir else None
    history = []
    if args.provenance_history and args.provenance_history.is_dir():
        for snap in sorted(args.provenance_history.glob("*.json")):
            try:
                history.append(json.loads(snap.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                print(f"skipping unreadable provenance snapshot {snap.name}", file=sys.stderr)
    # The repair is deterministic and idempotent, so apply it to EVERY candidate before comparing:
    # a repaired checkpoint and a not-yet-repaired Pages copy must not look like a rewrite.
    for label, doc in (("committed", current), ("Pages", published), ("Actions checkpoint", artifact),
                       ("journal-archive", archive)):
        if doc is not None:
            for note in repair_first_seen(doc, history):
                print(f"PROVENANCE REPAIRED ({label}): {note}")
    try:
        result, result_ledger, source = choose_history(
            current, ledger, published, old_ledger, artifact, artifact_ledger,
            require_live=args.require_live_history, archive=archive, archive_ledger=archive_ledger,
        )
        # Settlement history: the longest candidate that still extends the committed
        # prefix wins; divergence stops the run instead of rewriting receipts.
        result_settlements = current_settlements
        for candidate in sorted((j for j in (published_settlements, artifact_settlements, archive_settlements)
                                 if j is not None), key=lambda j: len(j.get("rows", []))):
            result_settlements = restore_settlements(result_settlements, candidate)
    except SourceError as exc:
        # Fail visibly. Diagnostics go to a temp dir for the workflow's debug artifact; NOTHING in
        # data/ is modified, so a failed restore can never publish the offline seed as "history".
        summary = {"error": str(exc)}
        for label, doc in (("current", current), ("published", published), ("artifact", artifact), ("archive", archive)):
            summary[label] = None if doc is None else {
                "mode": doc.get("mode"), "last_attempt_utc": doc.get("last_attempt_utc"),
                "events": len(doc.get("events", [])), "quotes": len(doc.get("quotes", []))}
        try:
            args.debug_dir.mkdir(parents=True, exist_ok=True)
            (args.debug_dir / "restore_failure.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except OSError:
            pass
        print(f"RESTORE REFUSED (history protected, nothing written): {json.dumps(summary)}", file=sys.stderr)
        return 1
    # All candidates and their coverage were checked BEFORE writing any file.
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LEDGER.write_text(json.dumps(result_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SETTLEMENTS.write_text(json.dumps(result_settlements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Restored {len(result['quotes'])} quote receipts and {len(result_ledger['entries'])} immutable paper decisions from {source}; "
          f"{len(result_settlements['rows'])} chained settlement receipts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
