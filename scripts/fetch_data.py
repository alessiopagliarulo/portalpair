"""Fetch player roster and usage data from College Football Data API.

API docs: https://apinext.collegefootballdata.com/

Profile fields: firstName, lastName, team, height, weight, jersey, position,
                homeCity, homeState, homeCountry
Usage metrics: passingDowns, standardDowns, thirdDown, secondDown, firstDown,
               rush, pass, overall
"""

import time
import requests
from typing import Optional
from .config import CFBD_BASE_URL, CFBD_API_KEY

_MAX_429_RETRIES = 5
_INITIAL_429_WAIT = 60


def _get_with_retry(url: str, params: dict = None, **kwargs) -> requests.Response:
    """GET with retry on 429 (rate limit). Waits Retry-After or exponential backoff."""
    last_err = None
    wait = _INITIAL_429_WAIT
    for attempt in range(_MAX_429_RETRIES):
        resp = requests.get(url, params=params, **kwargs)
        if resp.status_code != 429:
            return resp
        last_err = resp
        retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            wait = int(retry_after)
        print(f"  429 rate limit (attempt {attempt + 1}/{_MAX_429_RETRIES}). Waiting {wait}s...", flush=True)
        time.sleep(wait)
        wait = min(wait * 2, 300)
    return last_err

DEFAULT_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]  # past 5 years (2020-2025)


def _headers() -> dict:
    """Build request headers with API key."""
    return {
        "Authorization": f"Bearer {CFBD_API_KEY}",
        "Accept": "application/json",
    }


def fetch_roster(team: str, year: int = 2024) -> list[dict]:
    """Fetch roster (profile) data for a team for a single year.

    Returns: firstName, lastName, athlete_id, team, height, weight,
             jersey, position, home_city, home_state, home_country, season
    """
    url = f"{CFBD_BASE_URL}/roster"
    params = {"team": team, "year": year}
    resp = _get_with_retry(url, params=params, headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Normalize to camelCase for consistency with frontend
    result = []
    for p in data:
        # API may use first_name/last_name or name split
        first = p.get("first_name") or p.get("firstName", "")
        last = p.get("last_name") or p.get("lastName", "")
        if not first and not last and p.get("name"):
            parts = str(p["name"]).split(" ", 1)
            first = parts[0] if parts else ""
            last = parts[1] if len(parts) > 1 else ""

        result.append({
            "athlete_id": p.get("id") or p.get("athlete_id"),
            "firstName": first,
            "lastName": last,
            "team": p.get("team", team),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "jersey": p.get("jersey"),
            "position": p.get("position"),
            "homeCity": p.get("home_city") or p.get("homeCity"),
            "homeState": p.get("home_state") or p.get("homeState"),
            "homeCountry": p.get("home_country") or p.get("homeCountry"),
            "season": year,
        })
    return result


def fetch_roster_multi_year(team: str, years: list[int] = None) -> list[dict]:
    """Fetch roster for multiple years. Returns combined list with season per record."""
    years = years or DEFAULT_YEARS
    all_roster = []
    for year in years:
        for r in fetch_roster(team, year):
            all_roster.append(r)
    return all_roster


def fetch_player_usage(
    year: int = 2024,
    team: Optional[str] = None,
    conference: Optional[str] = None,
    position: Optional[str] = None,
) -> list[dict]:
    """Fetch player usage metrics.

    Returns: overall, pass, rush, firstDown, secondDown, thirdDown,
             standardDowns, passingDowns
    """
    url = f"{CFBD_BASE_URL}/player/usage"
    params = {"year": year}
    if team:
        params["team"] = team
    if conference:
        params["conference"] = conference
    if position:
        params["position"] = position

    resp = _get_with_retry(url, params=params, headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()

    result = []
    for p in data:
        result.append({
            "athlete_id": p.get("athlete_id") or p.get("id"),
            "name": p.get("name"),
            "team": p.get("team"),
            "position": p.get("position"),
            "season": p.get("season", year),
            "overall": p.get("usg_overall"),
            "pass": p.get("usg_pass"),
            "rush": p.get("usg_rush"),
            "firstDown": p.get("usg_1st_down"),
            "secondDown": p.get("usg_2nd_down"),
            "thirdDown": p.get("usg_3rd_down"),
            "standardDowns": p.get("usg_standard_downs"),
            "passingDowns": p.get("usg_passing_downs"),
        })
    return result


def fetch_player_usage_multi_year(
    years: list[int] = None,
    team: Optional[str] = None,
    conference: Optional[str] = None,
    position: Optional[str] = None,
) -> list[dict]:
    """Fetch player usage for multiple years. Returns combined list with season per record."""
    years = years or DEFAULT_YEARS
    all_usage = []
    for year in years:
        for u in fetch_player_usage(year=year, team=team, conference=conference, position=position):
            all_usage.append(u)
    return all_usage


def fetch_teams() -> list[dict]:
    """Fetch list of FBS teams for iteration."""
    url = f"{CFBD_BASE_URL}/teams/fbs"
    params = {"year": 2024}
    resp = _get_with_retry(url, params=params, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def merge_roster_and_usage(roster: list[dict], usage: list[dict]) -> list[dict]:
    """Merge roster (profile) and usage into unified player records.
    Match by (athlete_id, season) when both have season; else by athlete_id."""
    usage_by_key = {}
    for u in usage:
        if u.get("athlete_id") is None:
            continue
        aid = str(u["athlete_id"])
        season = u.get("season")
        key = (aid, season) if season is not None else (aid, None)
        usage_by_key[key] = u

    merged = []
    for r in roster:
        aid = str(r.get("athlete_id") or "")
        season = r.get("season")
        key = (aid, season) if season is not None else (aid, None)
        u = usage_by_key.get(key) or usage_by_key.get((aid, None)) or {}

        rec = {
            **r,
            "overall": u.get("overall"),
            "pass": u.get("pass"),
            "rush": u.get("rush"),
            "firstDown": u.get("firstDown"),
            "secondDown": u.get("secondDown"),
            "thirdDown": u.get("thirdDown"),
            "standardDowns": u.get("standardDowns"),
            "passingDowns": u.get("passingDowns"),
        }
        merged.append(rec)
    return merged


def fetch_players_multi_year(
    team: str,
    years: list[int] = None,
) -> list[dict]:
    """Fetch roster + usage for multiple years and merge. One record per (player, season)."""
    years = years or DEFAULT_YEARS
    roster = fetch_roster_multi_year(team, years)
    usage = fetch_player_usage_multi_year(years=years, team=team)
    return merge_roster_and_usage(roster, usage)
