"""Versioned, tamper-evident long-term journal archive (beyond 30-day artifacts).

Every successful publication run copies the full quote/decision/settlement
journal into a git-managed archive branch (`journal-archive`) together with a
MANIFEST.json listing SHA-256 digests of every file plus the settlement chain
head. Git history then provides one immutable-commit-per-run versioning, and
the digests make any later bit-rot or tampering detectable. Actions artifacts
expire after 30 days; commits on the archive branch do not.

The manifest is also published to the site (`data/archive_manifest.json`) so
readers can see the archive status and verify downloads locally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL_FILES = ("observations.json", "ledger.json", "settlements.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out_dir: Path, run_id: str = "", commit_url: str = "") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "manifest_version": 1,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "commit_url": commit_url,
        "files": {},
        "retention": "journal-archive branch history; one commit per successful publication run",
    }
    for name in JOURNAL_FILES:
        source = ROOT / "data" / name
        if source.exists():
            shutil.copy2(source, out_dir / name)
            manifest["files"][name] = digest(out_dir / name)
    settlements = out_dir / "settlements.json"
    if settlements.exists():
        journal = json.loads(settlements.read_text(encoding="utf-8"))
        manifest["settlement_rows"] = len(journal.get("rows", []))
        manifest["settlement_chain_head"] = journal.get("chain_head")
    observations = out_dir / "observations.json"
    if observations.exists():
        obs = json.loads(observations.read_text(encoding="utf-8"))
        manifest["journal"] = {
            "mode": obs.get("mode"),
            "last_attempt_utc": obs.get("last_attempt_utc"),
            "quotes": len(obs.get("quotes", [])),
            "fixtures": len(obs.get("fixtures", [])),
            "events": len(obs.get("events", [])),
        }
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "data" / "archive_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="directory to receive the archive snapshot")
    parser.add_argument("--run-id", default="", help="GitHub Actions run id for the manifest")
    args = parser.parse_args(argv)
    manifest = build(args.out, run_id=args.run_id)
    print(f"Archive snapshot written to {args.out} ({len(manifest['files'])} files, "
          f"{manifest.get('settlement_rows', 0)} settlement receipts, chain head {str(manifest.get('settlement_chain_head'))[:12]}…).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
