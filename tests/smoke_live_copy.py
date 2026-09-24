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
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="thunderpick-synthetic-live-") as tmp:
        copy = Path(tmp)
        for folder in ("assets", "data", "scripts", "tests"):
            shutil.copytree(ROOT / folder, copy / folder,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for html in ROOT.glob("*.html"):
            shutil.copy2(html, copy / html.name)
        shutil.copy2(ROOT / ".nojekyll", copy / ".nojekyll")

        observations = copy / "data" / "observations.json"
        doc = json.loads(observations.read_text(encoding="utf-8"))
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
