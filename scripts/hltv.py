"""HLTV match-page signals for fixture/result cross-checking.

Fetch policy (2026-09-24 review of https://www.hltv.org/robots.txt):
`Disallow: /matches?*` covers only the *listing* URL with query parameters.
Individual match pages (`/matches/<id>`) are not disallowed, so this pipeline
fetches single match pages, bounded per run, with a contactable user agent.

Parser policy: only plain-text markers that were verified against a real HLTV
match page on 2026-09-24 (match 2397860, 3DMAX vs Acend) are used:

- page <title> "A vs. B at <event> | HLTV.org"
- team links "/team/<digits>/<slug>" (first two distinct links)
- series score text like "2 : 0"
- status texts "Match over", "Match canceled", "Match postponed"
- date text like "9th of September 2026"

The displayed start *time* on HLTV is rendered in the viewer's local timezone
(the same page rendered "07:15" for a 13:15 CEST start), so clock time is
NEVER parsed from HLTV. Date agreement is checked at UTC calendar-day
granularity against Liquipedia's explicit-UTC template date. No field is
inferred from banners, ads or bracket context; anything unparsable is
reported as unknown rather than guessed.
"""
from __future__ import annotations

import re


class SourceError(ValueError):
    """A source-content problem that must be shown publicly (mirrors collect.SourceError)."""

HLTV_MATCH_URL = "https://www.hltv.org/matches/{match_id}"
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def hltv_match_url(match_id: str) -> str:
    if not re.fullmatch(r"\d{6,9}", str(match_id)):
        raise SourceError("invalid HLTV match id")
    return HLTV_MATCH_URL.format(match_id=match_id)


def parse_hltv_match(html: str, match_id: str) -> dict:
    """Extract verified text markers from an HLTV match page.

    Raises SourceError when the page identity cannot be established, and
    returns explicit None/unknown values for anything not found.
    """
    if not isinstance(html, str) or not html:
        raise SourceError("HLTV page was empty")
    title = re.search(r"<title>([^<]+)</title>", html)
    if not title:
        raise SourceError("HLTV page has no title")
    expected = re.compile(rf"\bvs\.?\b.*\|\s*HLTV\.org")
    if not expected.search(title.group(1)):
        raise SourceError("HLTV page title does not look like a match page")
    url_match = re.search(rf"/matches/{re.escape(str(match_id))}/", html)
    if not url_match:
        raise SourceError("HLTV page does not reference the requested match id")

    # First two distinct /team/<id>/<slug> links, in page order (team1, team2).
    teams: list[str] = []
    for m in re.finditer(r"/team/(\d+)/([a-z0-9-]+)", html):
        token = m.group(1) + "/" + m.group(2)
        if token not in teams:
            teams.append(token)
    if len(teams) < 2:
        raise SourceError("HLTV page does not name two distinct teams")

    score = re.search(r">\s*(\d{1,2})\s*:\s*(\d{1,2})\s*<", html) or re.search(r"\b(\d{1,2}) : (\d{1,2})\b", html)
    scores = (int(score.group(1)), int(score.group(2))) if score else None
    if scores and max(scores) > 3:  # CS2 series scores are best-of-3/5
        raise SourceError("implausible HLTV series score")

    if "Match canceled" in html or "match canceled" in html.lower():
        status = "canceled"
    elif "Match postponed" in html or "match postponed" in html.lower():
        status = "postponed"
    elif "Match over" in html:
        status = "finished"
    elif re.search(r">\s*LIVE\s*<", html):
        status = "live"
    else:
        status = "scheduled-or-unknown"  # includes localized start-time countdowns

    day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th) of (" + "|".join(MONTHS) + r") (\d{4})\b", html, re.I)
    date_utc = None
    if day:
        date_utc = f"{int(day.group(3)):04d}-{MONTHS[day.group(2).lower()]:02d}-{int(day.group(1)):02d}"

    return {
        "match_id": str(match_id),
        "team1": teams[0],  # "4914/3dmax" style token
        "team2": teams[1],
        "score_team1": scores[0] if scores else None,
        "score_team2": scores[1] if scores else None,
        "status": status,
        "date_utc": date_utc,
        "url": hltv_match_url(match_id),
        "note": "Parsed from verified plain-text markers only; HLTV start clock is viewer-localized and is not used.",
    }
