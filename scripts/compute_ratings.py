#!/usr/bin/env python3
"""Compute overall ratings (0-100) for all players and store in ChromaDB.

Uses the methodology from how-we-calculate.html (adapted to available data):
  - P_phys (15%): physical fit via height/weight regression by position
  - P_composite (85%): percentile rank of exponentially-decayed stats within
    the same position group, so players are compared to peers at the same position.

Stats where lower = better (e.g. interceptions for QBs, sacks_allowed for OL)
are inverted before ranking. Recent seasons are weighted more heavily via
exponential decay (λ=0.3).

Run: python -m scripts.compute_ratings
"""

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TQDM_DISABLE", "1")

from scripts.expand_seasons import POSITION_STATS, POSITION_MAP

DECAY_LAMBDA = 0.3
REFERENCE_SEASON = 2025

INVERTED_BY_GROUP = {
    "QB": {"interceptions"},
    "OL": {"sacks_allowed", "pressures_allowed", "penalties"},
    "DB": {"completion_pct_allowed", "yards_allowed"},
    "P": {"touchbacks"},
}

IDEAL_BUILD = {
    "QB": (75, 220), "RB": (70, 215), "WR_TE": (74, 215),
    "OL": (76, 310), "DL": (75, 280), "LB": (73, 235),
    "DB": (71, 195), "K": (72, 190), "P": (73, 200),
    "Returner": (70, 190),
}
HT_SIGMA = 2.5
WT_SIGMA = 20.0


def _get_group(pos):
    pos = (pos or "").strip().upper()
    return POSITION_MAP.get(pos, "Returner")


def _parse_num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _decay_weight(season):
    try:
        dt = REFERENCE_SEASON - int(season)
    except (ValueError, TypeError):
        dt = 5
    return math.exp(-DECAY_LAMBDA * max(0, dt))


def _compute_phys(height, weight, group):
    ideal_h, ideal_w = IDEAL_BUILD.get(group, (73, 220))
    h = _parse_num(height)
    w = _parse_num(weight)
    if h is None or w is None:
        return 50.0
    z_h = abs(h - ideal_h) / HT_SIGMA
    z_w = abs(w - ideal_w) / WT_SIGMA
    z = (z_h + z_w) / 2
    return max(0, min(100, 100 * (1 - z / 2)))


def _percentile_rank(values):
    n = len(values)
    if n <= 1:
        return [50.0] * n
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    for rank_pos, (orig_idx, _) in enumerate(indexed):
        ranks[orig_idx] = (rank_pos / (n - 1)) * 100
    return ranks


def main():
    from scripts.config import CHROMA_PERSIST_DIRECTORY
    from scripts.vector_store import COLLECTION
    import chromadb

    root = Path(__file__).parent.parent
    p = CHROMA_PERSIST_DIRECTORY
    if not os.path.isabs(p):
        p = str((root / p).resolve())

    print("Loading ChromaDB...", flush=True)
    client = chromadb.PersistentClient(path=p)
    coll = client.get_collection(COLLECTION)
    result = coll.get(include=["metadatas"])
    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []

    players = {}
    for doc_id, meta in zip(ids, metadatas):
        meta = meta or {}
        first = (meta.get("firstName") or "").strip()
        last = (meta.get("lastName") or "").strip()
        team = (meta.get("team") or "").strip()
        name = f"{first} {last}".strip()
        key = f"{name}::{team}"
        if key not in players:
            players[key] = []
        players[key].append((doc_id, meta))

    print(f"Found {len(players)} unique players across {len(ids)} records.", flush=True)

    player_stats = {}
    for key, records in players.items():
        pos = (records[0][1].get("position") or "").strip().upper()
        group = _get_group(pos)
        stat_defs = POSITION_STATS.get(group, {})

        stat_sums = {s: 0.0 for s in stat_defs}
        weight_sums = {s: 0.0 for s in stat_defs}
        latest_ht, latest_wt = None, None
        latest_season = 0

        for _, meta in records:
            season = meta.get("season")
            w = _decay_weight(season)
            try:
                s_int = int(season)
            except (ValueError, TypeError):
                s_int = 0
            if s_int >= latest_season:
                latest_season = s_int
                ht = _parse_num(meta.get("height"))
                wt = _parse_num(meta.get("weight"))
                if ht:
                    latest_ht = ht
                if wt:
                    latest_wt = wt
            for stat_name in stat_defs:
                v = _parse_num(meta.get(stat_name))
                if v is not None:
                    stat_sums[stat_name] += v * w
                    weight_sums[stat_name] += w

        weighted_avgs = {}
        for stat_name in stat_defs:
            if weight_sums[stat_name] > 0:
                weighted_avgs[stat_name] = stat_sums[stat_name] / weight_sums[stat_name]
            else:
                weighted_avgs[stat_name] = 0
        player_stats[key] = {
            "stats": weighted_avgs,
            "height": latest_ht,
            "weight": latest_wt,
            "group": group,
        }

    by_group = {}
    for key, pdata in player_stats.items():
        g = pdata["group"]
        if g not in by_group:
            by_group[g] = []
        by_group[g].append(key)

    ratings = {}
    for group, player_keys in by_group.items():
        stat_defs = POSITION_STATS.get(group, {})
        inverted = INVERTED_BY_GROUP.get(group, set())

        if not stat_defs or not player_keys:
            for key in player_keys:
                ratings[key] = 50
            continue

        stat_percentiles = {s: {} for s in stat_defs}
        for stat_name in stat_defs:
            values = []
            keys_ordered = []
            for key in player_keys:
                v = player_stats[key]["stats"].get(stat_name, 0)
                if stat_name in inverted:
                    v = -v
                values.append(v)
                keys_ordered.append(key)
            pctiles = _percentile_rank(values)
            for k, pctile in zip(keys_ordered, pctiles):
                stat_percentiles[stat_name][k] = pctile

        for key in player_keys:
            p_phys = _compute_phys(
                player_stats[key]["height"],
                player_stats[key]["weight"],
                group,
            )
            scores = [stat_percentiles[s][key] for s in stat_defs]
            p_composite = sum(scores) / len(scores) if scores else 50
            final = 0.15 * p_phys + 0.85 * p_composite
            ratings[key] = max(0, min(100, round(final)))

        below = [(k, ratings[k]) for k in player_keys if ratings[k] < 51]
        if below:
            below.sort(key=lambda x: x[1])
            n = len(below)
            for i, (k, _) in enumerate(below):
                ratings[k] = 51 + round(i * 13 / max(1, n - 1)) if n > 1 else 57

    print(f"Computed ratings for {len(ratings)} players.", flush=True)
    for group in sorted(by_group.keys()):
        group_ratings = [ratings[k] for k in by_group[group]]
        if group_ratings:
            avg = sum(group_ratings) / len(group_ratings)
            mn, mx = min(group_ratings), max(group_ratings)
            print(f"  {group}: {len(group_ratings)} players, avg={avg:.1f}, min={mn}, max={mx}")

    print("Updating ChromaDB with ratings...", flush=True)
    batch_size = 500
    update_ids = []
    update_metas = []

    for doc_id, meta in zip(ids, metadatas):
        meta = meta or {}
        first = (meta.get("firstName") or "").strip()
        last = (meta.get("lastName") or "").strip()
        team = (meta.get("team") or "").strip()
        name = f"{first} {last}".strip()
        key = f"{name}::{team}"
        rating = ratings.get(key, 50)
        new_meta = dict(meta)
        new_meta["overall_rating"] = rating
        update_ids.append(doc_id)
        update_metas.append(new_meta)

    for i in range(0, len(update_ids), batch_size):
        batch_ids = update_ids[i : i + batch_size]
        batch_metas = update_metas[i : i + batch_size]
        coll.update(ids=batch_ids, metadatas=batch_metas)
        print(f"  Updated {min(i + batch_size, len(update_ids))}/{len(update_ids)}", flush=True)

    print(f"Done. All {len(update_ids)} records now have overall_rating.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
