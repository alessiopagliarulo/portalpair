"""Export first 500 players from CFBD API to a text file for use as a knowledge base."""

import time

from .config import TEAM_LIMIT, FETCH_DELAY, PLAYER_LIMIT, API_CALL_LIMIT
from .fetch_data import fetch_teams, fetch_players_multi_year, DEFAULT_YEARS

_CALLS_PER_TEAM = 12


def _player_to_text(p: dict) -> str:
    """Format a single player record as readable text."""
    lines = [
        f"{p.get('firstName', '')} {p.get('lastName', '')}".strip() or "Unknown",
        f"  Team: {p.get('team', '')}",
        f"  Position: {p.get('position', '')}",
        f"  Season: {p.get('season', '')}",
        f"  Jersey: {p.get('jersey', '')}",
        f"  Height: {p.get('height', '')}",
        f"  Weight: {p.get('weight', '')} lbs" if p.get("weight") else "  Weight:",
    ]
    loc = []
    if p.get("homeCity"):
        loc.append(str(p["homeCity"]))
    if p.get("homeState"):
        loc.append(str(p["homeState"]))
    if p.get("homeCountry"):
        loc.append(str(p["homeCountry"]))
    if loc:
        lines.append(f"  Hometown: {', '.join(loc)}")
    usage = []
    if p.get("overall") is not None:
        usage.append(f"overall {p['overall']:.1%}")
    if p.get("pass") is not None:
        usage.append(f"pass {p['pass']:.1%}")
    if p.get("rush") is not None:
        usage.append(f"rush {p['rush']:.1%}")
    if usage:
        lines.append(f"  Usage: {' | '.join(usage)}")
    return "\n".join(lines)


def export_players_txt(output_path: str = "players_500.txt", limit: int = 500) -> int:
    """Fetch first N players from CFBD API and write to text file. Returns count written."""
    print("Fetching FBS teams...", flush=True)
    try:
        teams_data = fetch_teams()
        teams = [t.get("school") or t.get("team") or t.get("name") for t in teams_data if t]
        teams = [t for t in teams if t]
    except Exception as e:
        if "429" in str(e):
            print("  429 rate limit - using fallback teams.", flush=True)
            teams = ["Alabama", "Ohio State", "Georgia"]
        else:
            raise

    if API_CALL_LIMIT:
        max_teams = (API_CALL_LIMIT - 1) // _CALLS_PER_TEAM
        teams = teams[:max_teams]
    if TEAM_LIMIT:
        teams = teams[:TEAM_LIMIT]

    all_players = []
    for i, team in enumerate(teams):
        if len(all_players) >= limit:
            break
        try:
            players = fetch_players_multi_year(team, years=DEFAULT_YEARS)
            all_players.extend(players)
            if len(all_players) >= limit:
                all_players = all_players[:limit]
            if (i + 1) % 20 == 0 or i == 0:
                print(f"  [{i+1}/{len(teams)}] {team}: {len(players)} | total: {len(all_players)}", flush=True)
        except Exception as e:
            print(f"  [{i+1}/{len(teams)}] {team}: ERROR - {e}", flush=True)
            if "429" in str(e):
                break
        time.sleep(FETCH_DELAY)

    all_players = all_players[:limit]
    print(f"Writing {len(all_players)} players to {output_path}...", flush=True)

    docs = [_player_to_text(p) for p in all_players]
    content = "\n\n---\n\n".join(docs)

    with open(output_path, "w") as f:
        f.write(content)

    return len(all_players)


if __name__ == "__main__":
    n = export_players_txt("players_500.txt", limit=500)
    print(f"Exported {n} players to players_500.txt")
