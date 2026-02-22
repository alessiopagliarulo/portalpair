#!/usr/bin/env python3
"""Coach chatbot: uses ChromaDB vector store + LLM to recommend players.

Coaches chat with the bot; it searches the player database and uses an LLM
to generate personalized recommendations.

Run: python -m scripts.coach_chat
     python -m scripts.coach_chat "I need a quarterback who throws accurately"
     python -m scripts.coach_chat --json "query"  # for server API

Requires: CEREBRAS_API_KEY in .env
Uses ChromaDB when USE_CHROMADB=1 (default).
"""

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ["USE_CHROMADB"] = "1"  # Coach chatbot always uses ChromaDB
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer

from scripts.config import CEREBRAS_API_KEY
from scripts.vector_store import COLLECTION, get_vector_store


SYSTEM_PROMPT = """You are a college football recruiting assistant. You help coaches find players
that match their needs. The player list below comes from semantic search—these are the best-matching
players in the database for the coach's request.

When the coach specifies filters (position, weight, height), only players meeting those criteria
are included. Use this to give precise recommendations.

ALWAYS recommend from the players provided. Never say "no relevant players" or "refine the search."
Infer fit from position (WR/TE = pass-catchers), height, weight, usage, and team. Be concise and actionable.

CRITICAL: Never mention any year or season (e.g. 2024, 2025, 2023) in your response. Do not write "BYU 2024" or similar—use only the team name and player info. Omit year/season entirely."""


def _pct(v) -> str:
    """Format usage value as percentage."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        return f"{f:.1%}"
    except (ValueError, TypeError):
        return str(v)


def _format_players_for_llm(results: list) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        p = r.get("payload", {})
        name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
        pos = p.get("position", "")
        team = p.get("team", "")
        height = p.get("height", "")
        weight = p.get("weight", "")
        parts = [f"{i}. {name} ({pos}) - {team}, Ht:{height} Wt:{weight}"]
        u = []
        if p.get("overall") is not None:
            u.append(f"overall {_pct(p['overall'])}")
        if p.get("pass") is not None:
            u.append(f"pass {_pct(p['pass'])}")
        if p.get("rush") is not None:
            u.append(f"rush {_pct(p['rush'])}")
        if p.get("firstDown") is not None:
            u.append(f"1st {_pct(p['firstDown'])}")
        if p.get("secondDown") is not None:
            u.append(f"2nd {_pct(p['secondDown'])}")
        if p.get("thirdDown") is not None:
            u.append(f"3rd {_pct(p['thirdDown'])}")
        if p.get("standardDowns") is not None:
            u.append(f"std {_pct(p['standardDowns'])}")
        if p.get("passingDowns") is not None:
            u.append(f"passDown {_pct(p['passingDowns'])}")
        if u:
            parts.append(" | usage: " + ", ".join(u))
        lines.append("".join(parts))
    return "\n".join(lines) if lines else "No players found in database."


def _format_players_for_llm_from_matches(matches: list) -> str:
    """Format match dicts for LLM context."""
    lines = []
    for i, m in enumerate(matches, 1):
        name = m.get("name", "").strip()
        pos = m.get("position", "")
        team = m.get("team", "")
        height = m.get("height", "")
        weight = m.get("weight", "")
        parts = [f"{i}. {name} ({pos}) - {team}, Ht:{height} Wt:{weight}"]
        u = []
        for k, label in [
            ("overall", "overall"), ("pass", "pass"), ("rush", "rush"),
            ("firstDown", "1st"), ("secondDown", "2nd"), ("thirdDown", "3rd"),
            ("standardDowns", "std"), ("passingDowns", "passDown"),
        ]:
            v = m.get(k)
            if v is not None:
                u.append(f"{label} {_pct(v)}")
        if u:
            parts.append(" | usage: " + ", ".join(u))
        lines.append("".join(parts))
    return "\n".join(lines) if lines else "No players found in database."


def _results_to_matches(results: list) -> list:
    matches = []
    for r in results:
        p = r.get("payload", {})
        score = r.get("score", 0)
        doc_id = r.get("id", "")
        name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
        try:
            height = int(p.get("height") or 0)
        except (ValueError, TypeError):
            height = None
        try:
            weight = int(p.get("weight") or 0)
        except (ValueError, TypeError):
            weight = None
        matches.append({
            "name": name or "Unknown",
            "firstName": p.get("firstName", ""),
            "lastName": p.get("lastName", ""),
            "team": p.get("team", ""),
            "position": p.get("position", ""),
            "height": height,
            "weight": weight,
            "matchPct": round(score * 100) if isinstance(score, (int, float)) else None,
            "season": p.get("season", ""),
            "docId": doc_id,
            "athlete_id": p.get("athlete_id", ""),
            "overall": p.get("overall"),
            "pass": p.get("pass"),
            "rush": p.get("rush"),
            "firstDown": p.get("firstDown"),
            "secondDown": p.get("secondDown"),
            "thirdDown": p.get("thirdDown"),
            "standardDowns": p.get("standardDowns"),
            "passingDowns": p.get("passingDowns"),
        })
    return _deduplicate_matches(matches)


def _deduplicate_matches(matches: list) -> list:
    """Keep one match per (name, team), preferring highest matchPct then most recent season."""
    by_key = {}
    for m in matches:
        key = (m.get("name") or "").strip(), (m.get("team") or "").strip()
        if not key[0]:
            continue
        prev = by_key.get(key)
        score = m.get("matchPct") or 0
        season = m.get("season") or ""
        keep = prev is None or (
            score > (prev.get("matchPct") or 0)
            or (score == (prev.get("matchPct") or 0) and str(season) > str(prev.get("season") or ""))
        )
        if keep:
            by_key[key] = m
    out = list(by_key.values())
    out.sort(key=lambda x: ((x.get("matchPct") or 0), str(x.get("season") or "")), reverse=True)
    return out


def _call_llm(query: str, context: str) -> str:
    user_content = f"Coach request: {query}\n\nRelevant players from database:\n{context}"

    # Cerebras (fast)
    if CEREBRAS_API_KEY:
        try:
            from cerebras.cloud.sdk import Cerebras
            client = Cerebras(api_key=CEREBRAS_API_KEY)
            resp = client.chat.completions.create(
                model="llama3.1-8b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=512,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"Cerebras error: {e}"

    return "Add CEREBRAS_API_KEY to .env (https://cloud.cerebras.ai/)"


# Map coach query keywords to CFBD position codes (exact match in DB)
POSITION_KEYWORDS = {
    "QB": ["quarterback", "quarterbacks", "qb", "qbs", "signal caller", "passer"],
    "RB": ["running back", "running backs", "rb", "rbs", "tailback", "halfback", "tailbacks", "halfbacks"],
    "WR": ["wide receiver", "wide receivers", "wr", "wrs", "receiver", "receivers"],
    "TE": ["tight end", "tight ends", "te", "tes"],
    "OL": ["offensive line", "o-line", "ol", "offensive lineman", "offensive linemen"],
    "OT": ["offensive tackle", "tackle", "ot", "ots"],
    "OG": ["offensive guard", "guard", "og", "ogs"],
    "C": ["center", "centers"],
    "DE": ["defensive end", "d-end", "de", "des"],
    "DT": ["defensive tackle", "d-tackle", "dt", "dts"],
    "NT": ["nose tackle", "nose guard", "nt", "nts"],
    "LB": ["linebacker", "linebackers", "lb", "lbs"],
    "CB": ["cornerback", "cornerbacks", "cb", "cbs", "corner", "corners"],
    "S": ["safety", "safeties", "db", "dbs", "defensive back"],
    "K": ["kicker", "kickers", "placekicker"],
    "P": ["punter", "punters"],
}


def _detect_position_filter(query: str) -> str | None:
    """If coach mentions a specific position, return the DB position code. Else None."""
    q = query.lower().strip()
    for pos_code, keywords in POSITION_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                return pos_code
    return None


def _detect_weight_constraint(query: str) -> tuple[int | None, int | None]:
    """Return (min_lbs, max_lbs) when coach mentions weight. (None, None) otherwise."""
    q = query.lower()
    min_w, max_w = None, None
    # "over 200", "200+", "at least 200", "200 lbs or more"
    m = re.search(r'(?:over|at least|above|minimum|min)\s*(\d+)(?:\s*lbs?|\s*pounds?)?', q)
    if m:
        min_w = int(m.group(1))
    m = re.search(r'(\d+)\s*\+\s*(?:lbs?|pounds?)?', q)
    if m and min_w is None:
        min_w = int(m.group(1))
    # "under 180", "below 180", "max 200"
    m = re.search(r'(?:under|below|max|maximum|less than)\s*(\d+)(?:\s*lbs?|\s*pounds?)?', q)
    if m:
        max_w = int(m.group(1))
    # "around 200", "about 200" -> 190-210
    m = re.search(r'(?:around|about|~)\s*(\d+)(?:\s*lbs?|\s*pounds?)?', q)
    if m and min_w is None and max_w is None:
        v = int(m.group(1))
        min_w, max_w = max(0, v - 15), v + 15
    # "heavy" / "light" as heuristics
    if 'heavy' in q and min_w is None:
        min_w = 220
    if 'light' in q and max_w is None:
        max_w = 200
    return (min_w, max_w) if (min_w is not None or max_w is not None) else (None, None)


def _detect_height_constraint(query: str) -> tuple[int | None, int | None]:
    """Return (min_inches, max_inches) when coach mentions height. (None, None) otherwise."""
    q = query.lower()
    min_h, max_h = None, None
    # 6'2", 6'2, 6 foot 2, 6-2
    m = re.search(r"(\d)\s*['\-]?\s*(\d{1,2})(?:\s*(?:inches?|\")?|$)", q)
    if m:
        ft, inc = int(m.group(1)), int(m.group(2))
        total = ft * 12 + (inc if inc < 12 else inc)
        min_h = max_h = total
    # "over 6 feet", "at least 6'", "6 foot or taller"
    m = re.search(r'(?:over|at least|above|minimum)\s*(\d)\s*(?:feet?|ft|[\'"])', q)
    if m:
        min_h = int(m.group(1)) * 12
    # "under 6 feet", "below 6'"
    m = re.search(r'(?:under|below|max|less than)\s*(\d)\s*(?:feet?|ft|[\'"])', q)
    if m:
        max_h = int(m.group(1)) * 12 - 1
    # "tall" / "short"
    if 'tall' in q and min_h is None:
        min_h = 72  # 6'
    if 'short' in q and max_h is None:
        max_h = 70  # ~5'10"
    return (min_h, max_h) if (min_h is not None or max_h is not None) else (None, None)


def _apply_constraints(
    results: list,
    min_weight: int | None,
    max_weight: int | None,
    min_height: int | None,
    max_height: int | None,
) -> list:
    """Filter results by weight/height when constraints are specified."""
    if min_weight is None and max_weight is None and min_height is None and max_height is None:
        return results
    out = []
    for r in results:
        p = r.get("payload", {})
        try:
            w = int(p.get("weight") or 0)
        except (ValueError, TypeError):
            w = 0
        try:
            h = int(p.get("height") or 0)
        except (ValueError, TypeError):
            h = 0
        if min_weight is not None and (not w or w < min_weight):
            continue
        if max_weight is not None and (not w or w > max_weight):
            continue
        if min_height is not None and (not h or h < min_height):
            continue
        if max_height is not None and (not h or h > max_height):
            continue
        out.append(r)
    return out


def chat_with_matches(query: str) -> tuple[str, list]:
    store = get_vector_store()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vec = model.encode([query], convert_to_numpy=True)[0].tolist()

    position_filter = _detect_position_filter(query)
    filter_metadata = {"position": position_filter} if position_filter else None
    min_w, max_w = _detect_weight_constraint(query)
    min_h, max_h = _detect_height_constraint(query)
    has_constraints = min_w is not None or max_w is not None or min_h is not None or max_h is not None

    top_k = 40 if has_constraints else 24
    results = store.search(COLLECTION, query_vec, top_k=top_k, filter_metadata=filter_metadata)
    if not results and filter_metadata:
        results = store.search(COLLECTION, query_vec, top_k=top_k, filter_metadata=None)

    results = _apply_constraints(results, min_w, max_w, min_h, max_h)
    if not results and has_constraints:
        results = store.search(COLLECTION, query_vec, top_k=24, filter_metadata=filter_metadata or None)
        results = results[:24]
    else:
        results = results[:24]

    matches = _results_to_matches(results)[:8]
    context = _format_players_for_llm_from_matches(matches)
    response = _call_llm(query, context)
    return response, matches


def main():
    json_mode = "--json" in sys.argv
    query = os.environ.get("COACH_QUERY", "").strip()
    if not query:
        args = [a for a in sys.argv[1:] if a != "--json"]
        query = " ".join(args).strip() if args else ""

    if not query:
        if json_mode:
            print(json.dumps({"response": "Please enter a question.", "matches": []}))
        else:
            print("Usage: python -m scripts.coach_chat \"Your question about players\"")
        return

    response, matches = chat_with_matches(query)

    if json_mode:
        out = json.dumps({"response": response, "matches": matches})
        print(out, flush=True)
    else:
        print(response)
        for m in matches[:5]:
            print(f"  - {m['name']} ({m['position']}, {m['team']})")


if __name__ == "__main__":
    main()
