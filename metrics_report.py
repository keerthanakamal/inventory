"""Metrics reporting script for warehouse placement optimization.

Computes key KPIs from current placement & layout data and appends results to metrics_history.csv.

KPIs:
  - avg_distance: Mean distance of placed items
  - unplaced_rate: Fraction of rows with UNPLACED
  - avg_cube_utilization: Mean utilization across shelves with any allocation
  - fragmentation_rate: % shelves with 0 < util < 0.1
  - total_allocated_volume: Sum of allocated_volume (non-null rows)
  - capacity_ratio: total_allocated_volume / total_capacity
  - free_effective_capacity_ratio: sum remaining_size / total_capacity (latest residual snapshot only)
  - placements_with_capacity_cols_ratio: share of placement rows with allocated_volume not null
  - weighted_distance (optional, requires demand_frequency join if inventory file present)

Usage:
  python metrics_report.py            # auto-detect layout file
  python metrics_report.py --layout locations_data_extended.csv
  python metrics_report.py --once      # run once (default)

Outputs/Side-effects:
  - metrics_history.csv (append or create)
  - Prints KPI summary to stdout.

Limitations:
  - Weighted distance requires inventory_data.csv with demand_frequency & item_id.
  - Remaining_size accuracy depends on recent rows including residual values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from typing import List, Optional

import numpy as np
import pandas as pd

PLACEMENTS_FILE = "placement_recommendations.csv"
LAYOUT_CANDIDATE_FILENAMES = ["locations_data_extended.csv", "warehouse_layout.csv", "locations_data.csv"]
INVENTORY_FILE = "inventory_data.csv"
METRICS_FILE = "metrics_history.csv"


def _pick_layout(layout_override: Optional[str]) -> str:
    if layout_override:
        if not os.path.exists(layout_override):
            raise FileNotFoundError(f"Layout file not found: {layout_override}")
        return layout_override
    for f in LAYOUT_CANDIDATE_FILENAMES:
        if os.path.exists(f):
            return f
    raise FileNotFoundError("No layout file found.")


def load_data(layout_override: Optional[str]) -> tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    if not os.path.exists(PLACEMENTS_FILE):
        raise FileNotFoundError("placement_recommendations.csv not found")
    placements = pd.read_csv(PLACEMENTS_FILE)
    layout_path = _pick_layout(layout_override)
    layout = pd.read_csv(layout_path)
    inventory = None
    if os.path.exists(INVENTORY_FILE):
        try:
            inventory = pd.read_csv(INVENTORY_FILE)
        except Exception:  # noqa: BLE001
            pass
    return placements, layout, inventory


def compute_kpis(placements: pd.DataFrame, layout: pd.DataFrame, inventory: Optional[pd.DataFrame]):
    now = dt.datetime.utcnow().isoformat()
    # Distance join
    if {"x_coord", "y_coord"}.issubset(layout.columns):
        layout = layout.copy()
        layout["distance"] = np.sqrt(layout["x_coord"] ** 2 + layout["y_coord"] ** 2)
    else:
        layout["distance"] = np.nan

    # Ensure columns
    for col in ["allocated_volume", "allocated_weight", "remaining_size", "remaining_weight"]:
        if col not in placements.columns:
            placements[col] = np.nan

    merged = placements.merge(layout[["location_id", "distance", "max_size", "max_weight"]], left_on="recommended_location", right_on="location_id", how="left")

    # Placed subset (with a real location id)
    placed = merged[(merged["recommended_location"].notna()) & (merged["recommended_location"] != "UNPLACED")]

    avg_distance = placed["distance"].mean() if not placed.empty else np.nan
    unplaced_rate = (merged["recommended_location"] == "UNPLACED").mean() if not merged.empty else np.nan

    # Shelf utilization (aggregate allocated volume by location)
    alloc_rows = placed[placed["allocated_volume"].notna()]
    shelf_util = None
    avg_cube_util = np.nan
    fragmentation_rate = np.nan
    total_allocated_volume = float(alloc_rows["allocated_volume"].sum()) if not alloc_rows.empty else 0.0
    if not alloc_rows.empty:
        shelf_util = alloc_rows.groupby("recommended_location").agg({
            "allocated_volume": "sum",
            "max_size": "first"
        })
        shelf_util["utilization"] = shelf_util["allocated_volume"] / shelf_util["max_size"].replace(0, np.nan)
        avg_cube_util = shelf_util["utilization"].mean()
        fragmentation_rate = (shelf_util[(shelf_util["utilization"] > 0) & (shelf_util["utilization"] < 0.1)].shape[0] / shelf_util.shape[0]) if shelf_util.shape[0] else np.nan

    total_capacity = float(layout["max_size"].sum()) if "max_size" in layout.columns else np.nan
    capacity_ratio = (total_allocated_volume / total_capacity) if total_capacity and total_capacity > 0 else np.nan

    # Effective free capacity (approx): use latest remaining_size per location (last occurrence in placements)
    latest = placements.copy()
    if "remaining_size" in latest.columns:
        latest = latest[latest["remaining_size"].notna()].copy()
        latest = latest.sort_index()  # ensure order
        latest_last = latest.groupby("recommended_location").tail(1)
        free_effective_capacity_ratio = latest_last["remaining_size"].sum() / total_capacity if total_capacity and total_capacity > 0 and not latest_last.empty else np.nan
    else:
        free_effective_capacity_ratio = np.nan

    placements_with_capacity_cols_ratio = (placements["allocated_volume"].notna().mean()) if not placements.empty else np.nan

    # Weighted distance (if inventory provides demand_frequency)
    weighted_distance = np.nan
    if inventory is not None and "demand_frequency" in inventory.columns:
        placed_inv = placed.merge(inventory[["item_id", "demand_frequency"]], on="item_id", how="left")
        placed_inv = placed_inv[placed_inv["demand_frequency"].notna()]
        if not placed_inv.empty:
            num = (placed_inv["distance"] * placed_inv["demand_frequency"]).sum()
            den = placed_inv["demand_frequency"].sum()
            if den > 0:
                weighted_distance = num / den

    return {
        "timestamp": now,
        "rows": int(len(placements)),
        "placed_rows": int(len(placed)),
        "avg_distance": avg_distance,
        "weighted_distance": weighted_distance,
        "unplaced_rate": unplaced_rate,
        "avg_cube_utilization": avg_cube_util,
        "fragmentation_rate": fragmentation_rate,
        "total_allocated_volume": total_allocated_volume,
        "capacity_ratio": capacity_ratio,
        "free_effective_capacity_ratio": free_effective_capacity_ratio,
        "placements_with_capacity_cols_ratio": placements_with_capacity_cols_ratio,
    }


def append_metrics(row: dict):
    df_row = pd.DataFrame([row])
    if os.path.exists(METRICS_FILE):
        existing = pd.read_csv(METRICS_FILE)
        combined = pd.concat([existing, df_row], ignore_index=True)
        combined.to_csv(METRICS_FILE, index=False)
    else:
        df_row.to_csv(METRICS_FILE, index=False)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(description="Compute and append warehouse optimization KPIs")
    parser.add_argument("--layout", help="Explicit layout file")
    parser.add_argument("--print-only", action="store_true", help="Print KPIs without appending")
    args = parser.parse_args()

    placements, layout, inventory = load_data(args.layout)
    metrics = compute_kpis(placements, layout, inventory)
    if not args.print_only:
        append_metrics(metrics)
    # Pretty print
    print("KPI Summary:")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}" if v == v else f"  {k}: NaN")  # NaN check (v==v fails if NaN)
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":  # pragma: no cover
    main()
