#!/usr/bin/env python3
"""Expand ChromaDB so each player has position-specific stats for seasons 2020-2025.

Reads all players from Chroma, dedupes by (athlete_id, team), then generates
6 records per player (one per season) with position-appropriate random stats.
Height/weight vary slightly by season (e.g. freshman smaller, progression).

Run: python -m scripts.expand_seasons
"""

import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TQDM_DISABLE", "1")

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]
BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# Position-specific stat definitions: {stat_name: (min, max, type)}
# type is "int" or "float"
# ---------------------------------------------------------------------------
POSITION_STATS = {
    "QB": {
        "passing_yards":     (0, 5000, "int"),
        "passing_tds":       (0, 50, "int"),
        "interceptions":     (0, 20, "int"),
        "completion_pct":    (40.0, 80.0, "float"),
        "yards_per_attempt": (5.0, 12.0, "float"),
        "rushing_yards":     (0, 1000, "int"),
        "rushing_tds":       (0, 15, "int"),
    },
    "RB": {
        "rushing_attempts":  (0, 350, "int"),
        "rushing_yards":     (0, 2000, "int"),
        "yards_per_carry":   (2.0, 8.0, "float"),
        "rushing_tds":       (0, 25, "int"),
        "receptions":        (0, 80, "int"),
        "receiving_yards":   (0, 800, "int"),
    },
    "WR_TE": {
        "targets":           (0, 150, "int"),
        "receptions":        (0, 120, "int"),
        "receiving_yards":   (0, 1800, "int"),
        "yards_per_catch":   (8.0, 25.0, "float"),
        "receiving_tds":     (0, 20, "int"),
    },
    "OL": {
        "sacks_allowed":       (0, 15, "int"),
        "pressures_allowed":   (0, 40, "int"),
        "penalties":           (0, 15, "int"),
        "run_block_win_rate":  (50.0, 95.0, "float"),
        "pass_block_win_rate": (50.0, 95.0, "float"),
    },
    "DL": {
        "total_tackles": (0, 100, "int"),
        "tfl":           (0, 25, "int"),
        "sacks":         (0, 20, "int"),
        "qb_hits":       (0, 30, "int"),
        "pressures":     (0, 60, "int"),
    },
    "LB": {
        "total_tackles":  (0, 150, "int"),
        "tfl":            (0, 25, "int"),
        "sacks":          (0, 15, "int"),
        "interceptions":  (0, 5, "int"),
    },
    "DB": {
        "tackles":                (0, 100, "int"),
        "interceptions":          (0, 10, "int"),
        "passes_defended":        (0, 25, "int"),
        "completion_pct_allowed": (30.0, 80.0, "float"),
        "yards_allowed":          (0, 1000, "int"),
    },
    "K": {
        "field_goal_pct":   (50.0, 100.0, "float"),
        "longest_fg":       (30, 65, "int"),
        "extra_point_pct":  (80.0, 100.0, "float"),
    },
    "P": {
        "punt_average": (35.0, 55.0, "float"),
        "inside_20":    (0, 40, "int"),
        "touchbacks":   (0, 15, "int"),
    },
    "Returner": {
        "kick_return_avg": (15.0, 35.0, "float"),
        "punt_return_avg": (5.0, 20.0, "float"),
        "return_tds":      (0, 5, "int"),
    },
}

POSITION_MAP = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR_TE", "TE": "WR_TE",
    "OL": "OL", "OT": "OL", "OG": "OL", "C": "OL",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB",
    "K": "K",
    "P": "P",
    "KR": "Returner", "PR": "Returner",
}

ALL_STAT_KEYS = set()
for _defs in POSITION_STATS.values():
    ALL_STAT_KEYS.update(_defs.keys())


def _parse_int(v):
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _parse_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _get_stat_group(pos: str) -> str:
    pos = (pos or "Unknown").strip().upper()
    return POSITION_MAP.get(pos, "Returner")


def _get_stat_defs(pos: str) -> dict:
    return POSITION_STATS[_get_stat_group(pos)]


def _career_multiplier(year_idx: int, talent: float) -> float:
    """Career arc multiplier. year_idx 0-5 maps to 2020-2025.
    Peak at index 3 (2023). talent in [0.55, 1.0] scales the ceiling."""
    arc = [0.55, 0.70, 0.85, 1.0, 0.93, 0.87]
    return arc[min(year_idx, 5)] * talent


def _gen_stat_value(lo, hi, typ, multiplier, noise_pct=0.08):
    """Generate a single stat value within [lo, hi] scaled by multiplier."""
    span = hi - lo
    base = lo + span * multiplier
    noise = random.gauss(0, span * noise_pct)
    val = base + noise
    val = max(lo, min(hi, val))
    if typ == "int":
        return int(round(val))
    return round(val, 1)


def _gen_stats_for_position(pos: str, season: int, talent: float) -> dict:
    """Generate position-appropriate stats for a season."""
    defs = _get_stat_defs(pos)
    year_idx = SEASONS.index(season) if season in SEASONS else 0
    mult = _career_multiplier(year_idx, talent)
    stats = {}
    for stat_name, (lo, hi, typ) in defs.items():
        stats[stat_name] = _gen_stat_value(lo, hi, typ, mult)
    _apply_consistency(stats, pos)
    return stats


def _apply_consistency(stats: dict, pos: str):
    """Enforce logical consistency between related stats."""
    group = _get_stat_group(pos)
    if group == "QB":
        if stats.get("passing_yards", 0) < stats.get("passing_tds", 0) * 10:
            stats["passing_yards"] = max(stats["passing_yards"], stats["passing_tds"] * 18)
        if stats.get("interceptions", 0) > stats.get("passing_tds", 0):
            stats["interceptions"] = max(0, stats["passing_tds"] - random.randint(0, 5))
    elif group == "RB":
        if stats.get("rushing_attempts", 0) > 0 and stats.get("rushing_yards", 0) > 0:
            stats["yards_per_carry"] = round(stats["rushing_yards"] / max(1, stats["rushing_attempts"]), 1)
            stats["yards_per_carry"] = max(2.0, min(8.0, stats["yards_per_carry"]))
        if stats.get("receiving_yards", 0) > stats.get("rushing_yards", 0):
            stats["receiving_yards"] = int(stats["rushing_yards"] * random.uniform(0.15, 0.45))
    elif group == "WR_TE":
        if stats.get("receptions", 0) > stats.get("targets", 0):
            stats["targets"] = stats["receptions"] + random.randint(5, 30)
        if stats.get("receptions", 0) > 0 and stats.get("receiving_yards", 0) > 0:
            stats["yards_per_catch"] = round(stats["receiving_yards"] / max(1, stats["receptions"]), 1)
            stats["yards_per_catch"] = max(8.0, min(25.0, stats["yards_per_catch"]))
    elif group == "OL":
        if stats.get("sacks_allowed", 0) > stats.get("pressures_allowed", 0):
            stats["pressures_allowed"] = stats["sacks_allowed"] + random.randint(5, 20)
    elif group == "DL":
        if stats.get("sacks", 0) > stats.get("tfl", 0):
            stats["tfl"] = stats["sacks"] + random.randint(1, 8)
        if stats.get("sacks", 0) > stats.get("qb_hits", 0):
            stats["qb_hits"] = stats["sacks"] + random.randint(2, 10)
    elif group == "DB":
        if stats.get("passes_defended", 0) < stats.get("interceptions", 0):
            stats["passes_defended"] = stats["interceptions"] + random.randint(2, 10)


def _ht_wt_by_position(pos: str) -> tuple:
    base = {
        "QB": (74, 215), "RB": (70, 210), "WR": (72, 195), "TE": (76, 250),
        "OL": (76, 310), "OT": (76, 310), "OG": (76, 310), "C": (76, 305),
        "DE": (75, 265), "DT": (75, 300), "NT": (75, 315), "DL": (75, 285),
        "LB": (73, 235), "CB": (71, 195), "S": (71, 200), "DB": (71, 195),
        "K": (72, 190), "P": (73, 200),
    }
    pos = (pos or "Unknown").strip().upper() or "Unknown"
    return base.get(pos, base.get(pos[:2], (72, 220)))


def _height_variation(base_ht: int, season: int) -> int:
    year_idx = SEASONS.index(season) if season in SEASONS else 0
    delta = year_idx * random.uniform(-0.5, 1.5)
    return max(66, min(80, int(round(base_ht + delta))))


def _weight_variation(base_wt: int, season: int) -> int:
    year_idx = SEASONS.index(season) if season in SEASONS else 0
    delta = year_idx * random.uniform(0, 4)
    return max(170, min(350, int(round(base_wt + delta))))


def _to_text(meta: dict) -> str:
    """Build text representation for semantic embedding."""
    parts = [
        f"{meta.get('firstName', '')} {meta.get('lastName', '')}".strip(),
        meta.get("position", ""),
        meta.get("team", ""),
        str(meta.get("season", "")),
        str(meta.get("height", "")),
        str(meta.get("weight", "")) + " lbs" if meta.get("weight") else "",
        f"Jersey {meta.get('jersey')}" if meta.get("jersey") else "",
    ]
    stat_parts = []
    for k in sorted(ALL_STAT_KEYS):
        v = meta.get(k)
        if v is not None:
            label = k.replace("_", " ")
            stat_parts.append(f"{label} {v}")
    if stat_parts:
        parts.append(" ".join(stat_parts))
    return " | ".join(str(x) for x in parts if x)


def main():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)

    from scripts.config import CHROMA_PERSIST_DIRECTORY
    from scripts.vector_store import COLLECTION
    import chromadb
    from sentence_transformers import SentenceTransformer

    print("Loading ChromaDB...", flush=True)
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    try:
        coll = client.get_collection(COLLECTION)
    except Exception as e:
        print(f"Collection '{COLLECTION}' not found: {e}")
        return 1

    result = coll.get(include=["metadatas"])
    ids_raw = result.get("ids") or []
    metadatas = result.get("metadatas") or []

    seen = {}
    for doc_id, meta in zip(ids_raw, metadatas):
        meta = meta or {}
        aid = str(meta.get("athlete_id") or "").strip()
        team = (meta.get("team") or "").strip()
        if not aid:
            aid = f"{meta.get('firstName','')}_{meta.get('lastName','')}_{team}".strip("_")
        key = (aid or doc_id, team or "Unknown")
        if key not in seen:
            seen[key] = meta

    unique_players = list(seen.values())
    print(f"Found {len(unique_players)} unique players. Expanding to 6 seasons each...", flush=True)

    all_records = []
    for meta in unique_players:
        pos = (meta.get("position") or "Unknown").strip().upper() or "Unknown"
        base_ht, base_wt = _ht_wt_by_position(pos)
        ht0 = _parse_int(meta.get("height")) or base_ht
        wt0 = _parse_int(meta.get("weight")) or base_wt
        talent = random.uniform(0.55, 1.0)

        for season in SEASONS:
            stats = _gen_stats_for_position(pos, season, talent)
            ht = _height_variation(ht0, season)
            wt = _weight_variation(wt0, season)

            record = {
                "athlete_id": str(meta.get("athlete_id") or ""),
                "season": str(season),
                "firstName": (meta.get("firstName") or "Unknown").strip() or "Unknown",
                "lastName": (meta.get("lastName") or "").strip(),
                "team": (meta.get("team") or "Unknown").strip() or "Unknown",
                "position": pos or "N/A",
                "jersey": str(meta.get("jersey") or "0"),
                "height": ht,
                "weight": str(wt),
                "homeCity": meta.get("homeCity") or "",
                "homeState": meta.get("homeState") or "",
                "homeCountry": meta.get("homeCountry") or "",
            }
            for stat_name, val in stats.items():
                record[stat_name] = str(val)

            aid = record["athlete_id"] or f"{record['firstName']}_{record['lastName']}"
            doc_id = f"{aid}_{record['team']}_{season}"
            record["_id"] = doc_id
            all_records.append((doc_id, record))

    print(f"Generated {len(all_records)} records ({len(unique_players)} x 6 seasons).", flush=True)
    print("Generating embeddings...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    doc_ids = [r[0] for r in all_records]
    records = [r[1] for r in all_records]
    texts = [_to_text(rec) for rec in records]
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=True).tolist()

    metadatas_out = []
    for rec in records:
        m = {k: v for k, v in rec.items() if k != "_id" and v is not None}
        metadatas_out.append({k: str(v) if not isinstance(v, (int, float, bool)) else v for k, v in m.items()})

    print("Replacing Chroma collection...", flush=True)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    coll = client.create_collection(name=COLLECTION, metadata={"hnsw:space": "cosine"})

    for i in range(0, len(doc_ids), BATCH_SIZE):
        batch_ids = doc_ids[i : i + BATCH_SIZE]
        batch_vecs = vectors[i : i + BATCH_SIZE]
        batch_metas = metadatas_out[i : i + BATCH_SIZE]
        coll.add(ids=batch_ids, embeddings=batch_vecs, metadatas=batch_metas)
        print(f"  Inserted {min(i + BATCH_SIZE, len(doc_ids))}/{len(doc_ids)}", flush=True)

    print(f"Done. ChromaDB now has {len(doc_ids)} records (2020-2025 per player).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
