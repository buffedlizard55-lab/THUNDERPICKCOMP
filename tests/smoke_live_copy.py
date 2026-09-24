#!/usr/bin/env python3
"""CI-only synthetic live-journal replay in a disposable copy, NEVER published.

Pages restores/mutates data/*.json before testing. PR CI checks the committed
offline seed; run the same checks with a synthetic live-mode journal in a
separate temporary directory so tests cannot accidentally depend on the seed.
This exercise does NOT fetch real sources or record any prices or decisions.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # allow `python3 tests/smoke_live_copy.py`
    sys.path.insert(0, str(ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="thunderpick-synthetic-live-") as tmp:
        copy = Path(tmp)
        for folder in ("assets", "data", "scripts", "tests", ".github"):
            shutil.copytree(ROOT / folder, copy / folder,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for html in ROOT.glob("*.html"):
            shutil.copy2(html, copy / html.name)
        shutil.copy2(ROOT / ".nojekyll", copy / ".nojekyll")

        observations = copy / "data" / "observations.json"
        # Build the synthetic live journal WITH the real collector (offline
        # fixture replay inside the disposable copy) so its shape always
        # matches scripts.collect.SOURCE_IDS. Mutating the committed seed
        # instead would silently rot whenever the collector's check set grows
        # (this exact drift broke CI when the ninth check rule was added).
        # If the committed seed is already live (checked in to unblock legacy
        # Pages publishing), remove it so fixture replay can run — collect.py
        # refuses to overwrite a live journal with fixtures.
        if observations.exists():
            try:
                _doc = json.loads(observations.read_text(encoding="utf-8"))
                if _doc.get("mode") == "live":
                    observations.unlink()
            except Exception:
                observations.unlink()
        from scripts.collect import SOURCE_IDS
        subprocess.run(
            ("python3", "-m", "scripts.collect", "--fixtures", "--as-of", "2026-09-24T18:12:00Z"),
            cwd=copy, check=True,
        )
        doc = json.loads(observations.read_text(encoding="utf-8"))
        if sorted(c["source"] for c in doc["checks"]) != sorted(SOURCE_IDS):
            raise SystemExit("fixture replay did not produce one check per SOURCE_IDS; smoke test basis invalid")
        # Synthetic timestamps and mode live solely to exercise the dynamic
        # Pages test path. Keep the original repository's journal untouched.
        doc["mode"] = "live"
        doc["last_attempt_utc"] = "2026-09-24T18:12:00Z"
        doc["last_completed_utc"] = "2026-09-24T18:12:12Z"
        for check in doc["checks"]:
            check["checked_utc"] = "2026-09-24T18:12:11Z"
        observations.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")

        for command in (("python3", "scripts/validate.py"),
                        ("python3", "-m", "unittest", "discover", "-s", "tests", "-q"),
                        ("node", "tests/test_ui.cjs")):
            subprocess.run(command, cwd=copy, check=True)
    print("Synthetic live-path checks passed. No live records were published.")


if __name__ == "__main__":
    main()
