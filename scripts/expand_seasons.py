#!/usr/bin/env python3
"""Expand ChromaDB so each player has usage stats for seasons 2020-2025.

Reads all players from Chroma, dedupes by (athlete_id, team), then generates
6 records per player (one per season) with position-appropriate random usage.
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


# Position-appropriate usage ranges (min, max) as decimal fractions
# overall, pass, rush, firstDown, secondDown, thirdDown, standardDowns, passingDowns
POSITION_USAGE = {
    "QB": {
        "overall": (0.32, 0.52),
        "pass": (0.28, 0.48),
        "rush": (0.02, 0.12),
        "firstDown": (0.25, 0.45),
        "secondDown": (0.30, 0.50),
        "thirdDown": (0.25, 0.48),
        "standardDowns": (0.28, 0.48),
        "passingDowns": (0.35, 0.55),
    },
    "RB": {
        "overall": (0.15, 0.38),
        "pass": (0.01, 0.06),
        "rush": (0.14, 0.35),
        "firstDown": (0.12, 0.35),
        "secondDown": (0.15, 0.38),
        "thirdDown": (0.10, 0.32),
        "standardDowns": (0.14, 0.35),
        "passingDowns": (0.08, 0.25),
    },
    "WR": {
        "overall": (0.08, 0.26),
        "pass": (0.09, 0.24),
        "rush": (0.0, 0.03),
        "firstDown": (0.06, 0.22),
        "secondDown": (0.08, 0.24),
        "thirdDown": (0.07, 0.22),
        "standardDowns": (0.07, 0.22),
        "passingDowns": (0.12, 0.30),
    },
    "TE": {
        "overall": (0.05, 0.18),
        "pass": (0.04, 0.16),
        "rush": (0.0, 0.02),
        "firstDown": (0.04, 0.15),
        "secondDown": (0.05, 0.17),
        "thirdDown": (0.04, 0.14),
        "standardDowns": (0.04, 0.15),
        "passingDowns": (0.06, 0.20),
    },
    "OL": {"overall": (0.0, 0.02), "pass": (0.0, 0.01), "rush": (0.0, 0.01),
          "firstDown": (0.0, 0.01), "secondDown": (0.0, 0.01), "thirdDown": (0.0, 0.01),
          "standardDowns": (0.0, 0.01), "passingDowns": (0.0, 0.01)},
    "OT": {"overall": (0.0, 0.02), "pass": (0.0, 0.01), "rush": (0.0, 0.01),
           "firstDown": (0.0, 0.01), "secondDown": (0.0, 0.01), "thirdDown": (0.0, 0.01),
           "standardDowns": (0.0, 0.01), "passingDowns": (0.0, 0.01)},
    "OG": {"overall": (0.0, 0.02), "pass": (0.0, 0.01), "rush": (0.0, 0.01),
           "firstDown": (0.0, 0.01), "secondDown": (0.0, 0.01), "thirdDown": (0.0, 0.01),
           "standardDowns": (0.0, 0.01), "passingDowns": (0.0, 0.01)},
    "C": {"overall": (0.0, 0.02), "pass": (0.0, 0.01), "rush": (0.0, 0.01),
          "firstDown": (0.0, 0.01), "secondDown": (0.0, 0.01), "thirdDown": (0.0, 0.01),
          "standardDowns": (0.0, 0.01), "passingDowns": (0.0, 0.01)},
    "DE": {"overall": (0.02, 0.12), "pass": (0.0, 0.03), "rush": (0.01, 0.06),
           "firstDown": (0.02, 0.10), "secondDown": (0.02, 0.10), "thirdDown": (0.01, 0.08),
           "standardDowns": (0.02, 0.10), "passingDowns": (0.01, 0.08)},
    "DT": {"overall": (0.02, 0.10), "pass": (0.0, 0.02), "rush": (0.01, 0.05),
           "firstDown": (0.02, 0.08), "secondDown": (0.02, 0.08), "thirdDown": (0.01, 0.06),
           "standardDowns": (0.02, 0.08), "passingDowns": (0.01, 0.06)},
    "NT": {"overall": (0.02, 0.10), "pass": (0.0, 0.02), "rush": (0.01, 0.05),
           "firstDown": (0.02, 0.08), "secondDown": (0.02, 0.08), "thirdDown": (0.01, 0.06),
           "standardDowns": (0.02, 0.08), "passingDowns": (0.01, 0.06)},
    "DL": {"overall": (0.02, 0.11), "pass": (0.0, 0.02), "rush": (0.01, 0.05),
           "firstDown": (0.02, 0.09), "secondDown": (0.02, 0.09), "thirdDown": (0.01, 0.07),
           "standardDowns": (0.02, 0.09), "passingDowns": (0.01, 0.07)},
    "LB": {"overall": (0.03, 0.14), "pass": (0.0, 0.04), "rush": (0.01, 0.06),
           "firstDown": (0.03, 0.12), "secondDown": (0.03, 0.12), "thirdDown": (0.02, 0.10),
           "standardDowns": (0.03, 0.12), "passingDowns": (0.02, 0.09)},
    "CB": {"overall": (0.02, 0.12), "pass": (0.0, 0.04), "rush": (0.0, 0.03),
           "firstDown": (0.02, 0.10), "secondDown": (0.02, 0.10), "thirdDown": (0.01, 0.08),
           "standardDowns": (0.02, 0.10), "passingDowns": (0.01, 0.08)},
    "S": {"overall": (0.02, 0.12), "pass": (0.0, 0.04), "rush": (0.0, 0.03),
          "firstDown": (0.02, 0.10), "secondDown": (0.02, 0.10), "thirdDown": (0.01, 0.08),
          "standardDowns": (0.02, 0.10), "passingDowns": (0.01, 0.08)},
    "DB": {"overall": (0.02, 0.12), "pass": (0.0, 0.04), "rush": (0.0, 0.03),
           "firstDown": (0.02, 0.10), "secondDown": (0.02, 0.10), "thirdDown": (0.01, 0.08),
           "standardDowns": (0.02, 0.10), "passingDowns": (0.01, 0.08)},
    "K": {"overall": (0.0, 0.02), "pass": (0.0, 0.0), "rush": (0.0, 0.0),
          "firstDown": (0.0, 0.01), "secondDown": (0.0, 0.01), "thirdDown": (0.0, 0.01),
          "standardDowns": (0.0, 0.01), "passingDowns": (0.0, 0.01)},
    "P": {"overall": (0.0, 0.02), "pass": (0.0, 0.0), "rush": (0.0, 0.0),
          "firstDown": (0.0, 0.01), "secondDown": (0.0, 0.01), "thirdDown": (0.0, 0.01),
          "standardDowns": (0.0, 0.01), "passingDowns": (0.0, 0.01)},
}


def _get_ranges(pos: str):
    pos = (pos or "Unknown").strip().upper() or "Unknown"
    return POSITION_USAGE.get(pos, POSITION_USAGE.get(pos[:2], POSITION_USAGE["RB"]))


def _rand_in_range(lo: float, hi: float, drift: float = 0.0) -> float:
    """Random value in [lo, hi] with optional drift for career progression."""
    mid = (lo + hi) / 2
    r = random.gauss(mid + drift, (hi - lo) / 4)
    return round(max(lo, min(hi, r)), 4)


def _gen_usage_for_position(pos: str, season: int) -> dict:
    """Generate position-appropriate usage stats for a season."""
    ranges = _get_ranges(pos)
    # Slight career arc: 2020 = early, 2025 = later (small positive drift for "improvement")
    year_idx = SEASONS.index(season) if season in SEASONS else 0
    drift = (year_idx - 2.5) * 0.015  # peak around 2022-2023
    return {
        k: _rand_in_range(r[0], r[1], drift) for k, r in ranges.items()
    }


def _ht_wt_by_position(pos: str) -> tuple[int, int]:
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
    """Slight height change by season (e.g. freshman year vs senior)."""
    year_idx = SEASONS.index(season) if season in SEASONS else 0
    delta = year_idx * random.uniform(-0.5, 1.5)  # can grow ~1 inch over career
    return max(66, min(80, int(round(base_ht + delta))))


def _weight_variation(base_wt: int, season: int) -> int:
    """Weight progression (typically gain from 2020 to 2025)."""
    year_idx = SEASONS.index(season) if season in SEASONS else 0
    delta = year_idx * random.uniform(0, 4)
    return max(170, min(350, int(round(base_wt + delta))))


def _to_text(meta: dict) -> str:
    parts = [
        f"{meta.get('firstName', '')} {meta.get('lastName', '')}".strip(),
        meta.get("position", ""),
        meta.get("team", ""),
        str(meta.get("season", "")),
        str(meta.get("height", "")),
        str(meta.get("weight", "")) + " lbs" if meta.get("weight") else "",
        f"Jersey {meta.get('jersey')}" if meta.get("jersey") else "",
    ]
    u = []
    for k, label in [
        ("overall", "usage"), ("pass", "pass"), ("rush", "rush"),
        ("firstDown", "1st"), ("secondDown", "2nd"), ("thirdDown", "3rd"),
        ("standardDowns", "std"), ("passingDowns", "passDown"),
    ]:
        v = meta.get(k)
        if v is not None:
            try:
                f = float(v)
                u.append(f"{label} {f:.2%}")
            except (ValueError, TypeError):
                pass
    if u:
        parts.append(" ".join(u))
    return " | ".join(str(x) for x in parts if x)


def main():
    # Use cached model when proxy blocks Hugging Face
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

    # Dedupe: one template per (athlete_id, team)
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

    # Build 6 records per player
    all_records = []
    for meta in unique_players:
        pos = (meta.get("position") or "Unknown").strip().upper() or "Unknown"
        base_ht, base_wt = _ht_wt_by_position(pos)
        ht0 = _parse_int(meta.get("height")) or base_ht
        wt0 = _parse_int(meta.get("weight")) or base_wt

        for season in SEASONS:
            usage = _gen_usage_for_position(pos, season)
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
                "overall": f"{usage['overall']:.4f}",
                "pass": f"{usage['pass']:.4f}",
                "rush": f"{usage['rush']:.4f}",
                "firstDown": f"{usage['firstDown']:.4f}",
                "secondDown": f"{usage['secondDown']:.4f}",
                "thirdDown": f"{usage['thirdDown']:.4f}",
                "standardDowns": f"{usage['standardDowns']:.4f}",
                "passingDowns": f"{usage['passingDowns']:.4f}",
            }
            aid = record["athlete_id"] or f"{record['firstName']}_{record['lastName']}"
            doc_id = f"{aid}_{record['team']}_{season}"
            record["_id"] = doc_id
            all_records.append((doc_id, record))

    print(f"Generated {len(all_records)} records ({len(unique_players)} × 6 seasons).", flush=True)
    print("Generating embeddings...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    doc_ids = [r[0] for r in all_records]
    records = [r[1] for r in all_records]
    texts = [_to_text(rec) for rec in records]
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=True).tolist()

    # Build Chroma metadatas (exclude _id, use id as Chroma id)
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
