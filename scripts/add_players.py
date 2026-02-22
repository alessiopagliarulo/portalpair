#!/usr/bin/env python3
"""Add 60 LBs and 60 DBs to ChromaDB, and add a 'class' field to every record.

Run: python -m scripts.add_players
"""

import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TQDM_DISABLE", "1")

from scripts.expand_seasons import (
    SEASONS, POSITION_STATS, ALL_STAT_KEYS,
    _gen_stats_for_position, _height_variation, _weight_variation,
    _ht_wt_by_position, _to_text,
)

BATCH_SIZE = 500
CLASSES = ["Freshman", "Sophomore", "Junior", "Senior"]

FIRST_NAMES = [
    "James", "Marcus", "Devonte", "Jaylen", "Malik", "Tyrell", "Brandon",
    "Darius", "Terrell", "Andre", "Chris", "DeShawn", "Khalil", "Jamal",
    "Trevon", "Isaiah", "Micah", "Cameron", "Jordan", "Donte", "Rashad",
    "Keion", "Travon", "Zion", "Bryce", "Caleb", "Aaron", "Kobe", "Devin",
    "Jalen", "Tre", "Markus", "Quincy", "Damien", "Xavier", "Tyson",
    "Elijah", "Nolan", "Grant", "Colton", "Brock", "Dylan", "Hunter",
    "Luke", "Austin", "Ryan", "Tyler", "Jake", "Cole", "Mason",
    "Carson", "Tanner", "Logan", "Garrett", "Payton", "Trace", "Reed",
    "Drew", "Chase", "Blake", "Owen", "Landon", "Wyatt", "Seth",
    "Tucker", "Caden", "Knox", "Nash", "Beau", "Tate",
]

LAST_NAMES = [
    "Williams", "Johnson", "Brown", "Davis", "Jackson", "Thomas", "Harris",
    "Robinson", "Lewis", "Walker", "Young", "Allen", "King", "Scott",
    "Adams", "Baker", "Green", "Carter", "Mitchell", "Turner", "Moore",
    "Taylor", "Anderson", "White", "Martin", "Thompson", "Garcia", "Clark",
    "Hill", "Lee", "Wright", "Lopez", "Gonzalez", "Nelson", "Campbell",
    "Parker", "Evans", "Edwards", "Collins", "Stewart", "Sanders", "Price",
    "Bennett", "Wood", "Barnes", "Ross", "Henderson", "Coleman", "Jenkins",
    "Perry", "Powell", "Long", "Patterson", "Hughes", "Washington", "Butler",
    "Simmons", "Foster", "Bryant", "Jordan", "Russell", "Griffin", "Diaz",
    "Hayes", "Myers", "Ford", "Hamilton", "Graham", "Sullivan", "Wallace",
]

CFB_TEAMS = [
    "Alabama", "Ohio State", "Georgia", "Clemson", "Michigan", "LSU",
    "Oklahoma", "Texas", "Florida", "Penn State", "Oregon", "Notre Dame",
    "USC", "Texas A&M", "Auburn", "Wisconsin", "Iowa", "Tennessee",
    "Miami", "Florida State", "Virginia Tech", "NC State", "UCLA",
    "Washington", "Utah", "Baylor", "Ole Miss", "Arkansas", "Kentucky",
    "Oklahoma State", "Stanford", "Colorado", "Arizona State", "Nebraska",
    "Missouri", "South Carolina", "Pittsburgh", "West Virginia", "TCU",
    "Minnesota", "Indiana", "Michigan State", "Kansas State", "Wake Forest",
    "Maryland", "Purdue", "Illinois", "Duke", "Syracuse", "Boston College",
    "BYU", "Cincinnati", "Memphis", "Houston", "UCF", "Boise State",
    "San Diego State", "Fresno State", "Air Force", "Army",
]

DB_SUB_POSITIONS = ["CB", "S", "FS", "SS"]


def _assign_class(season, start_class_idx):
    """Given a starting class index for 2020, return the class for a given season."""
    year_offset = SEASONS.index(season) if season in SEASONS else 0
    idx = min(start_class_idx + year_offset, 3)
    return CLASSES[idx]


def _generate_players(position, count):
    """Generate `count` unique players at `position` with 6 seasons each."""
    used_names = set()
    players = []
    for _ in range(count):
        while True:
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break

        team = random.choice(CFB_TEAMS)
        jersey = str(random.randint(1, 99))
        base_ht, base_wt = _ht_wt_by_position(position)
        ht0 = base_ht + random.randint(-2, 2)
        wt0 = base_wt + random.randint(-15, 15)
        talent = random.uniform(0.55, 1.0)
        start_class = random.randint(0, 3)
        city = random.choice(["Atlanta", "Dallas", "Houston", "Miami", "Chicago",
                              "Los Angeles", "Phoenix", "Charlotte", "Detroit",
                              "Jacksonville", "Indianapolis", "Memphis", "Nashville",
                              "New Orleans", "Philadelphia", "Baltimore", "Tampa",
                              "Denver", "Seattle", "San Antonio", "Columbus",
                              "Cleveland", "Kansas City", "Minneapolis", "Orlando"])
        state = random.choice(["GA", "TX", "FL", "CA", "OH", "PA", "NC", "AL",
                                "LA", "TN", "SC", "VA", "MI", "IL", "AZ", "MD"])
        aid = f"gen_{position.lower()}_{first.lower()}_{last.lower()}_{random.randint(10000,99999)}"

        for season in SEASONS:
            stats = _gen_stats_for_position(position, season, talent)
            ht = _height_variation(ht0, season)
            wt = _weight_variation(wt0, season)
            player_class = _assign_class(season, start_class)

            record = {
                "athlete_id": aid,
                "season": str(season),
                "firstName": first,
                "lastName": last,
                "team": team,
                "position": position,
                "jersey": jersey,
                "height": ht,
                "weight": str(wt),
                "homeCity": city,
                "homeState": state,
                "homeCountry": "US",
                "class": player_class,
            }
            for stat_name, val in stats.items():
                record[stat_name] = str(val)

            doc_id = f"{aid}_{team}_{season}"
            record["_id"] = doc_id
            players.append((doc_id, record))

    return players


def main():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)

    from scripts.config import CHROMA_PERSIST_DIRECTORY
    from scripts.vector_store import COLLECTION
    import chromadb
    from sentence_transformers import SentenceTransformer

    root = Path(__file__).parent.parent
    p = CHROMA_PERSIST_DIRECTORY
    if not os.path.isabs(p):
        p = str((root / p).resolve())

    print("Loading ChromaDB...", flush=True)
    client = chromadb.PersistentClient(path=p)
    coll = client.get_collection(COLLECTION)

    # --- Step 1: Add 'class' to all existing records ---
    print("Adding 'class' field to existing records...", flush=True)
    result = coll.get(include=["metadatas"])
    existing_ids = result.get("ids") or []
    existing_metas = result.get("metadatas") or []

    player_start_class = {}
    update_ids = []
    update_metas = []

    for doc_id, meta in zip(existing_ids, existing_metas):
        meta = meta or {}
        first = (meta.get("firstName") or "").strip()
        last = (meta.get("lastName") or "").strip()
        team = (meta.get("team") or "").strip()
        pkey = f"{first}::{last}::{team}"

        if pkey not in player_start_class:
            player_start_class[pkey] = random.randint(0, 3)

        season = meta.get("season")
        try:
            season_int = int(season)
        except (ValueError, TypeError):
            season_int = 2020
        year_offset = SEASONS.index(season_int) if season_int in SEASONS else 0
        class_idx = min(player_start_class[pkey] + year_offset, 3)

        new_meta = dict(meta)
        new_meta["class"] = CLASSES[class_idx]
        update_ids.append(doc_id)
        update_metas.append(new_meta)

    for i in range(0, len(update_ids), BATCH_SIZE):
        batch_ids = update_ids[i : i + BATCH_SIZE]
        batch_metas = update_metas[i : i + BATCH_SIZE]
        coll.update(ids=batch_ids, metadatas=batch_metas)
        print(f"  Updated existing {min(i + BATCH_SIZE, len(update_ids))}/{len(update_ids)}", flush=True)

    print(f"Added 'class' to {len(update_ids)} existing records.", flush=True)

    # --- Step 2: Generate new LB and DB players ---
    print("Generating 60 LBs...", flush=True)
    lb_records = _generate_players("LB", 60)
    print("Generating 60 DBs...", flush=True)
    db_records = _generate_players("CB", 30) + _generate_players("S", 30)
    all_new = lb_records + db_records

    print(f"Generated {len(all_new)} new records ({len(all_new) // 6} players x 6 seasons).", flush=True)

    # --- Step 3: Generate embeddings for new players ---
    print("Generating embeddings for new players...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    new_doc_ids = [r[0] for r in all_new]
    new_records = [r[1] for r in all_new]
    new_texts = [_to_text(rec) for rec in new_records]
    new_vectors = model.encode(new_texts, convert_to_numpy=True, show_progress_bar=True).tolist()

    new_metadatas = []
    for rec in new_records:
        m = {k: v for k, v in rec.items() if k != "_id" and v is not None}
        new_metadatas.append({k: str(v) if not isinstance(v, (int, float, bool)) else v for k, v in m.items()})

    # --- Step 4: Insert new records ---
    print("Inserting new players into ChromaDB...", flush=True)
    for i in range(0, len(new_doc_ids), BATCH_SIZE):
        batch_ids = new_doc_ids[i : i + BATCH_SIZE]
        batch_vecs = new_vectors[i : i + BATCH_SIZE]
        batch_metas = new_metadatas[i : i + BATCH_SIZE]
        coll.add(ids=batch_ids, embeddings=batch_vecs, metadatas=batch_metas)
        print(f"  Inserted {min(i + BATCH_SIZE, len(new_doc_ids))}/{len(new_doc_ids)}", flush=True)

    total = coll.count()
    print(f"Done. ChromaDB now has {total} records.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
