#!/usr/bin/env python3
"""Use PyTorch to forecast 2026 stats for every player based on 2020-2025 data.

For each player and each position-specific stat, fits a weighted linear trend
model using PyTorch (recent seasons weighted more heavily) and extrapolates to
2026. Predictions are clamped to valid position ranges. A predicted 2026 overall
rating is computed via percentile ranking within position group.

Stores pred_{stat_name} and pred_2026_overall in every player's ChromaDB records.

Run: python -m scripts.forecast_2026
"""

import hashlib
import math
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TQDM_DISABLE", "1")

import torch
import torch.nn as nn

from scripts.expand_seasons import POSITION_STATS, POSITION_MAP, SEASONS
from scripts.compute_ratings import (
    INVERTED_BY_GROUP, IDEAL_BUILD, HT_SIGMA, WT_SIGMA, DECAY_LAMBDA,
    _compute_phys, _percentile_rank, _get_group,
)

BATCH_SIZE = 500
YEAR_INDICES = torch.tensor([float(i) for i in range(len(SEASONS))], dtype=torch.float32)
PRED_INDEX = torch.tensor([float(len(SEASONS))], dtype=torch.float32)  # index 6 = 2026
TEMPORAL_WEIGHTS = torch.tensor([0.5, 0.6, 0.75, 0.9, 1.0, 1.0], dtype=torch.float32)

CLASS_BIAS = {
    "Freshman": 1.0,
    "Sophomore": 0.4,
    "Junior": -0.2,
    "Senior": -0.8,
}


def _parse_num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class TrendModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.w = nn.Parameter(torch.zeros(1))
        self.b = nn.Parameter(torch.zeros(1))

    def forward(self, x):
        return self.w * x + self.b


def _predict_stat(values, lo, hi, typ, seed=0, class_factor=0.0, player_bias=0.0):
    """Fit a weighted linear trend via PyTorch, blend with recent average,
    then add class-based bias, player-level momentum, and noise."""
    clean = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(clean) < 2:
        if clean:
            return max(lo, min(hi, clean[0][1]))
        return (lo + hi) / 2

    rng = random.Random(seed)

    xs = torch.tensor([c[0] for c in clean], dtype=torch.float32)
    ys = torch.tensor([c[1] for c in clean], dtype=torch.float32)
    ws = torch.tensor([TEMPORAL_WEIGHTS[c[0]].item() for c in clean], dtype=torch.float32)

    y_mean = ys.mean().item()
    y_std = ys.std().item()
    if y_std < 1e-6:
        y_std = 1.0
    ys_norm = (ys - y_mean) / y_std
    xs_norm = xs / 5.0

    model = TrendModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.05)
    loss_fn = nn.MSELoss(reduction="none")

    for _ in range(400):
        pred = model(xs_norm)
        loss = (loss_fn(pred, ys_norm) * ws).mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    with torch.no_grad():
        x_pred = torch.tensor([6.0 / 5.0], dtype=torch.float32)
        forecast_norm = model(x_pred).item()
    trend_forecast = forecast_norm * y_std + y_mean

    recent_vals = [v for _, v in clean[-3:]]
    recent_ws = [0.2, 0.3, 0.5][-len(recent_vals):]
    recent_avg = sum(v * w for v, w in zip(recent_vals, recent_ws)) / sum(recent_ws)

    forecast = 0.6 * trend_forecast + 0.4 * recent_avg

    forecast += class_factor * y_std * 0.45
    forecast += player_bias * y_std * 0.5
    forecast += rng.gauss(0, y_std * 0.25)

    last_val = clean[-1][1]
    max_delta = max(abs(last_val) * 0.40, y_std * 2.5, 1.0)
    forecast = max(last_val - max_delta, min(last_val + max_delta, forecast))

    forecast = max(lo, min(hi, forecast))
    if typ == "int":
        forecast = int(round(forecast))
    else:
        forecast = round(forecast, 1)
    return forecast


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

    print(f"Found {len(players)} unique players. Forecasting 2026 stats...", flush=True)

    player_predictions = {}  # key -> {stat: predicted_value}
    player_info = {}  # key -> {group, height, weight}

    for i, (key, records) in enumerate(players.items()):
        pos = (records[0][1].get("position") or "").strip().upper()
        group = _get_group(pos)
        stat_defs = POSITION_STATS.get(group, {})

        by_season = {}
        latest_ht, latest_wt = None, None
        latest_class = None
        latest_season_num = 0
        for _, meta in records:
            season = meta.get("season")
            try:
                s_int = int(season)
            except (ValueError, TypeError):
                continue
            if s_int in SEASONS:
                by_season[s_int] = meta
                ht = _parse_num(meta.get("height"))
                wt = _parse_num(meta.get("weight"))
                if ht:
                    latest_ht = ht
                if wt:
                    latest_wt = wt
                if s_int >= latest_season_num:
                    latest_season_num = s_int
                    c = (meta.get("class") or "").strip()
                    if c:
                        latest_class = c

        cf = CLASS_BIAS.get(latest_class, 0.0)
        seed_base = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

        player_rng = random.Random(seed_base)
        player_bias = max(-1.5, min(1.5, player_rng.gauss(0, 0.7)))

        preds = {}
        for stat_name, (lo, hi, typ) in stat_defs.items():
            values = []
            for season in SEASONS:
                m = by_season.get(season)
                if m:
                    values.append(_parse_num(m.get(stat_name)))
                else:
                    values.append(None)
            stat_seed = seed_base ^ hash(stat_name)
            preds[stat_name] = _predict_stat(
                values, lo, hi, typ,
                seed=stat_seed, class_factor=cf, player_bias=player_bias,
            )

        player_predictions[key] = preds
        player_info[key] = {"group": group, "height": latest_ht, "weight": latest_wt}

        if (i + 1) % 100 == 0:
            print(f"  Forecasted {i + 1}/{len(players)} players...", flush=True)

    print(f"Forecasted all {len(players)} players.", flush=True)

    # --- Compute pred_2026_overall by ranking predicted stats against each other ---
    print("Computing predicted 2026 overall ratings...", flush=True)
    by_group = {}
    for key in player_info:
        g = player_info[key]["group"]
        if g not in by_group:
            by_group[g] = []
        by_group[g].append(key)

    pred_overalls = {}
    for group, player_keys in by_group.items():
        stat_defs = POSITION_STATS.get(group, {})
        inverted = INVERTED_BY_GROUP.get(group, set())

        if not stat_defs or not player_keys:
            for k in player_keys:
                pred_overalls[k] = 50
            continue

        stat_percentiles = {s: {} for s in stat_defs}
        for stat_name in stat_defs:
            values = []
            keys_ordered = []
            for k in player_keys:
                v = player_predictions[k].get(stat_name, 0)
                if stat_name in inverted:
                    v = -v
                values.append(v)
                keys_ordered.append(k)
            pctiles = _percentile_rank(values)
            for k, pctile in zip(keys_ordered, pctiles):
                stat_percentiles[stat_name][k] = pctile

        for k in player_keys:
            p_phys = _compute_phys(
                player_info[k]["height"], player_info[k]["weight"], group
            )
            scores = [stat_percentiles[s][k] for s in stat_defs]
            p_composite = sum(scores) / len(scores) if scores else 50
            raw = 0.15 * p_phys + 0.85 * p_composite
            pred_overalls[k] = max(0, min(100, round(raw)))

    for group, player_keys in by_group.items():
        below = [(k, pred_overalls[k]) for k in player_keys if pred_overalls[k] < 51]
        if below:
            below.sort(key=lambda x: x[1])
            n = len(below)
            for i, (k, _) in enumerate(below):
                pred_overalls[k] = 51 + round(i * 13 / max(1, n - 1)) if n > 1 else 57

    for group in sorted(by_group.keys()):
        vals = [pred_overalls[k] for k in by_group[group]]
        if vals:
            print(f"  {group}: avg={sum(vals)/len(vals):.1f}, min={min(vals)}, max={max(vals)}")

    # --- Update ChromaDB ---
    print("Updating ChromaDB with predictions...", flush=True)
    update_ids = []
    update_metas = []

    for doc_id, meta in zip(ids, metadatas):
        meta = meta or {}
        first = (meta.get("firstName") or "").strip()
        last = (meta.get("lastName") or "").strip()
        team = (meta.get("team") or "").strip()
        name = f"{first} {last}".strip()
        key = f"{name}::{team}"

        preds = player_predictions.get(key, {})
        ovr = pred_overalls.get(key, 50)

        new_meta = dict(meta)
        for stat_name, val in preds.items():
            new_meta[f"pred_{stat_name}"] = val
        new_meta["pred_2026_overall"] = ovr
        update_ids.append(doc_id)
        update_metas.append(new_meta)

    for i in range(0, len(update_ids), BATCH_SIZE):
        batch_ids = update_ids[i : i + BATCH_SIZE]
        batch_metas = update_metas[i : i + BATCH_SIZE]
        coll.update(ids=batch_ids, metadatas=batch_metas)
        print(f"  Updated {min(i + BATCH_SIZE, len(update_ids))}/{len(update_ids)}", flush=True)

    print(f"Done. All {len(update_ids)} records now have 2026 predictions.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
